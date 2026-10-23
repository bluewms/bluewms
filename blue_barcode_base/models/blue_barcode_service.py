from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .guard import TOKEN, identifier, scan_text


class BlueBarcodeService(models.AbstractModel):
    _name = 'blue.barcode.service'
    _description = '固定条码入口服务'

    @api.model
    def _authorize(self):
        if not self.env.user.has_group('stock.group_stock_user'):
            raise AccessError(self.env._('条码功能需要库存作业权限.'))

    @api.model
    def _target(self, kind, record_id):
        self._authorize()
        if kind not in ('picking', 'batch') or type(record_id) is not int or record_id <= 0:
            raise ValidationError(self.env._('无效的作业单据.'))
        target = self.env['stock.picking' if kind == 'picking' else 'stock.picking.batch'].browse(record_id).exists()
        target.ensure_one()
        target.check_access('write')
        if target.company_id != self.env.company:
            raise AccessError(self.env._('请切换至单据所属公司.'))
        pickings = target if kind == 'picking' else target.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        pickings.check_access('write')
        if not pickings or any(p.company_id != self.env.company or p.state not in ('waiting', 'confirmed', 'assigned') for p in pickings):
            raise UserError(self.env._('请选择尚未结束且已经确认的作业单据.'))
        return target, pickings

    @api.model
    def _policy_snapshot(self, target, kind):
        return {}

    @api.model
    def _open_values(self, kind, target, pickings):
        return {'kind': kind, 'picking_id': target.id if kind == 'picking' else False,
                'batch_id': target.id if kind == 'batch' else False,
                'picking_ids': [Command.set(pickings.ids)]}

    @api.model
    def _occupancy_domain(self, kind, target, pickings):
        return [('picking_ids', 'in', pickings.ids)]

    @api.model
    def _lock_target(self, kind, target, pickings):
        if kind == 'batch':
            self.env.cr.execute('UPDATE stock_picking_batch SET write_date=write_date WHERE id=%s RETURNING id', [target.id])
            self.env.cr.fetchone()
            target.invalidate_recordset()
        if pickings:
            pickings.flush_recordset()
            self.env.cr.execute('UPDATE stock_picking SET write_date=write_date WHERE id IN %s RETURNING id', [tuple(sorted(pickings.ids))])
            self.env.cr.fetchall()
            pickings.invalidate_recordset()

    @api.model
    def open_session(self, kind, record_id, client_key, takeover=False):
        identifier(client_key)
        if type(takeover) is not bool:
            raise ValidationError('Invalid takeover flag.')
        target, pickings = self._target(kind, record_id)
        self._lock_target(kind, target, pickings)
        target, pickings = self._target(kind, record_id)
        # Only occupancy metadata for an already authorized target is elevated.
        # Business rows and all returned session data use the calling user's ACL.
        occupied = self.env['blue.barcode.session'].sudo().search(
            fields.Domain(self._occupancy_domain(kind, target, pickings))
            & fields.Domain('company_id', '=', self.env.company.id)
            & fields.Domain('state', '=', 'active'))
        for session in occupied:
            if session.expires_at > fields.Datetime.now():
                same = session.user_id.id == self.env.uid
                if same and session.client_key == client_key:
                    return self.env['blue.barcode.session'].browse(session.id)._view()
                if not takeover or not (same or self.env.user.has_group('stock.group_stock_manager')):
                    raise UserError(self.env._('此作业已被另一终端占用. 请先释放会话或明确接管.'))
            session.with_context(blue_barcode_token=TOKEN).write({'state': 'closed', 'revision': session.revision + 1})
        session = self.env['blue.barcode.session'].with_context(blue_barcode_token=TOKEN).create({
            **self._open_values(kind, target, pickings), 'name': target.display_name,
            'company_id': self.env.company.id, 'user_id': self.env.uid, 'client_key': client_key,
            'expires_at': fields.Datetime.now() + timedelta(minutes=30), 'fingerprint': 'initializing',
            'policy_snapshot': self._policy_snapshot(target, kind),
            'state': 'active', 'revision': 0, 'scan_context': {}, 'expected': {},
        })
        rows = session._rows()
        session.write({'expected': {r['key']: r['expected'] for r in rows}})
        session.write({'fingerprint': session._fingerprint()})
        return session._view()

    @api.model
    def menu_entries(self):
        self._authorize()
        return [{'kind': 'operations', 'name': self.env._('作业'), 'icon': 'exchange'},
                {'kind': 'inventory', 'name': self.env._('盘库'), 'icon': 'check-square-o'},
                {'kind': 'product', 'name': self.env._('产品'), 'icon': 'cube'},
                {'kind': 'location', 'name': self.env._('位置'), 'icon': 'map-marker'}]

    @api.model
    def operation_types(self):
        self._authorize()
        domain = [('company_id', '=', self.env.company.id),
                  ('state', 'in', ['waiting', 'confirmed', 'assigned'])]
        # Aggregate visible pickings, so a type badge never counts inaccessible work.
        grouped = self.env['stock.picking']._read_group(domain, ['picking_type_id'], ['__count'])
        return [{'id': operation.id, 'name': operation.name,
                 'warehouse': operation.warehouse_id.display_name or self.env._('其他作业'),
                 'count': count, 'kind': 'operation_type'} for operation, count in grouped]

    @api.model
    def list_records(self, kind, term='', offset=0, operation_type_id=False):
        self._authorize()
        if type(term) is not str or len(term) > 256 or type(offset) is not int or not 0 <= offset <= 100000:
            raise ValidationError('Invalid search arguments.')
        if operation_type_id is not False and (type(operation_type_id) is not int or operation_type_id <= 0):
            raise ValidationError('Invalid operation type.')
        models_by_kind = {'operations': 'stock.picking', 'batch': 'stock.picking.batch',
                          'product': 'product.product', 'location': 'stock.location'}
        if kind == 'inventory':
            return {'items': [], 'more': False, 'message': self.env._('请先安装条码盘库模块,并开始一张盘库单.')}
        if kind not in models_by_kind:
            raise ValidationError('Unsupported lookup type.')
        domain = fields.Domain('company_id', 'in', [False, self.env.company.id])
        if kind == 'operations':
            domain &= fields.Domain('state', 'in', ['waiting', 'confirmed', 'assigned'])
            if operation_type_id:
                domain &= fields.Domain('picking_type_id', '=', operation_type_id)
        elif kind == 'batch':
            domain &= fields.Domain('state', 'in', ['draft', 'in_progress'])
        elif kind == 'location':
            domain &= fields.Domain('usage', '=', 'internal')
        if term:
            domain &= fields.Domain('display_name', 'ilike', term)
        records = self.env[models_by_kind[kind]].search(domain, limit=51, offset=offset)
        items = []
        for record in records[:50]:
            item = {'id': record.id, 'name': record.display_name,
                    'kind': 'picking' if kind == 'operations' else kind}
            if kind == 'operations':
                item.update(partner=record.partner_id.display_name or '',
                    origin=record.origin or '', date=str(record.scheduled_date or ''),
                    state=dict(record._fields['state']._description_selection(self.env)).get(record.state))
            elif kind == 'product':
                item.update(barcode=record.barcode or '', reference=record.default_code or '')
            elif kind == 'location':
                item.update(barcode=record.barcode or '')
            items.append(item)
        return {'items': items, 'more': len(records) > 50}

    @api.model
    def lookup(self, raw, kind=False):
        self._authorize()
        scan_text(raw)
        if kind not in (False, 'product', 'location'):
            raise ValidationError('Unsupported lookup scope.')
        matches = []
        for item_kind, model, field in [('picking', 'stock.picking', 'name'), ('batch', 'stock.picking.batch', 'name'),
                ('product', 'product.product', 'barcode'), ('location', 'stock.location', 'barcode')]:
            if kind and kind != item_kind:
                continue
            records = self.env[model].search(fields.Domain(field, '=', raw)
                & fields.Domain('company_id', 'in', [False, self.env.company.id]), limit=51)
            matches.extend({'id': r.id, 'kind': item_kind, 'name': r.display_name} for r in records[:50])
            if len(records) > 50:
                raise UserError(self.env._('编码匹配过多,请进入对应查询入口缩小范围.'))
        units = self.env['product.uom'].search([
            ('barcode', '=', raw), ('company_id', 'in', [False, self.env.company.id])], limit=2)
        for product in units.product_id if kind in (False, 'product') else []:
            if not any(m['kind'] == 'product' and m['id'] == product.id for m in matches):
                matches.append({'id': product.id, 'kind': 'product', 'name': product.display_name})
        return [item for item in matches if not kind or item['kind'] == kind]

    @api.model
    def details(self, kind, record_id, offset=0):
        self._authorize()
        if (kind not in ('product', 'location') or type(record_id) is not int
                or type(offset) is not int or not 0 <= offset <= 100000):
            raise ValidationError('Unsupported details request.')
        record = self.env['product.product' if kind == 'product' else 'stock.location'].browse(record_id).exists()
        record.ensure_one()
        record.check_access('read')
        if record.company_id and record.company_id != self.env.company:
            raise AccessError(self.env._('此记录属于其他公司.'))
        domain = [('company_id', '=', self.env.company.id), ('location_id.usage', '=', 'internal'),
            ('product_id' if kind == 'product' else 'location_id', '=' if kind == 'product' else 'child_of', record.id)]
        quants = self.env['stock.quant'].search(domain, limit=201, offset=offset, order='location_id,product_id,id')
        result = {'id': record.id, 'name': record.display_name, 'barcode': record.barcode or '', 'kind': kind,
                'offset': offset, 'count': self.env['stock.quant'].search_count(domain),
                'more': len(quants) > 200,
                'rows': [{'id': q.id, 'product_id': q.product_id.id, 'location_id': q.location_id.id,
                    'product': q.product_id.display_name, 'location': q.location_id.display_name,
                    'quantity': q.quantity, 'available': q.quantity - q.reserved_quantity,
                    'reserved': q.reserved_quantity,
                    'uom': q.product_id.uom_id.display_name, 'lot': q.lot_id.name or '',
                    'package': q.package_id.name or '', 'owner': q.owner_id.display_name or ''} for q in quants[:200]]}
        if kind == 'product':
            quantity, reserved = self.env['stock.quant']._read_group(domain, [], ['quantity:sum', 'reserved_quantity:sum'])[0]
            result.update(reference=record.default_code or '', category=record.categ_id.display_name or '未设置',
                uom=record.uom_id.display_name, weight=record.weight, volume=record.volume,
                weight_uom=record.weight_uom_name, volume_uom=record.volume_uom_name,
                tracking={'lot': '批次', 'serial': '序列号'}.get(record.tracking, '不追踪'),
                description=record.description_sale or '', storable=record.is_storable,
                image_url='/web/image/product.product/%s/image_256' % record.id,
                quantity=quantity, reserved=reserved, available=quantity-reserved)
        else:
            children = self.env['stock.location'].search([
                ('location_id', '=', record.id), ('usage', 'in', ['internal', 'view']),
                ('company_id', 'in', [False, self.env.company.id])], limit=51)
            result.update(parent_id=record.location_id.id, parent=record.location_id.display_name or '',
                usage=dict(record._fields['usage']._description_selection(self.env)).get(record.usage, record.usage),
                children=[{'id': c.id, 'name': c.display_name, 'kind': 'location'} for c in children[:50]],
                more_children=len(children)>50)
        return result
