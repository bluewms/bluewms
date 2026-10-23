from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .guard import TOKEN, digest, identifier, protect, quantity, scan_text


class BlueBarcodeSession(models.Model):
    _name = 'blue.barcode.session'
    _description = '条码作业会话'
    _check_company_auto = True

    name = fields.Char(required=True)
    kind = fields.Selection([('picking', '作业单'), ('batch', '批次作业')], required=True)
    picking_id = fields.Many2one('stock.picking', ondelete='restrict', check_company=True)
    batch_id = fields.Many2one('stock.picking.batch', ondelete='restrict', check_company=True)
    picking_ids = fields.Many2many('stock.picking', string='固定作业范围', check_company=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, index=True)
    client_key = fields.Char(required=True)
    state = fields.Selection([('active', '作业中'), ('closed', '已释放')], default='active', required=True)
    revision = fields.Integer(default=0, required=True)
    expires_at = fields.Datetime(required=True)
    fingerprint = fields.Char(required=True)
    expected = fields.Json(default=dict)
    scan_context = fields.Json(default=dict)
    policy_snapshot = fields.Json(default=dict)
    event_ids = fields.One2many('blue.barcode.event', 'session_id')

    @api.model_create_multi
    def create(self, vals_list):
        protect(self)
        return super().create(vals_list)

    def write(self, vals):
        protect(self)
        return super().write(vals)

    def unlink(self):
        protect(self)
        return super().unlink()

    def _internal(self):
        return self.with_context(blue_barcode_token=TOKEN)

    def _lock(self):
        self.ensure_one()
        self.check_access('write')
        self.flush_recordset()
        # A write lock also detects stale REPEATABLE READ snapshots on retry.
        self.env.cr.execute('UPDATE blue_barcode_session SET revision=revision WHERE id=%s RETURNING id', [self.id])
        self.env.cr.fetchone()
        self.invalidate_recordset()

    def _check_client(self, client_key, active=True):
        self.ensure_one()
        self.check_access('write')
        if (self.user_id != self.env.user or self.company_id != self.env.company
                or self.client_key != identifier(client_key)):
            raise AccessError(self.env._('请使用当前公司、用户和原终端恢复条码会话.'))
        if active and (self.state != 'active' or self.expires_at <= fields.Datetime.now()):
            raise UserError(self.env._('扫描会话已释放或过期,请重新进入作业.'))

    def _check_target(self):
        if self.kind not in ('picking', 'batch'):
            raise ValidationError(self.env._('不支持此作业类型.'))
        pickings = self.picking_id if self.kind == 'picking' else self.batch_id.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        pickings.check_access('write')
        if (not pickings or set(pickings.ids) != set(self.picking_ids.ids)
                or any(p.company_id != self.company_id or p.state not in ('confirmed', 'waiting', 'assigned') for p in pickings)):
            raise UserError(self.env._('作业范围或状态已变化,请释放会话后重新核对.'))
        if self.kind == 'batch':
            self.batch_id.check_access('write')
            if self.batch_id.state not in ('draft', 'in_progress'):
                raise UserError(self.env._('批次已结束.'))
        return pickings

    def _rows(self):
        rows = []
        for picking in self.picking_ids:
            for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                demand = move.uom_id._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
                lines = move.move_line_ids
                for line in lines or [None]:
                    key = 'line:%s' % line.id if line else 'move:%s' % move.id
                    source = line.location_id if line else move.location_id
                    destination = line.location_dest_id if line else move.location_dest_id
                    package = line.package_id if line else self.env['stock.package']
                    result_package = line.result_package_id if line else self.env['stock.package']
                    done = line.quantity_product_uom if line and line.picked else 0
                    expected = demand if len(lines) <= 1 else (self.expected or {}).get(key, line.quantity_product_uom)
                    grouping = picking.picking_type_id.blue_barcode_grouping
                    part = (['source_package', package.id] if grouping == 'source_package'
                        else ['destination_package', result_package.id] if grouping == 'destination_package'
                        else ['location', source.id, destination.id])
                    rows.append({'key': key, 'picking_id': picking.id, 'picking': picking.name,
                        'move_id': move.id, 'line_id': line.id if line else False,
                        'product_id': move.product_id.id, 'product': move.product_id.display_name,
                        'barcode': move.product_id.barcode or '', 'tracking': move.product_id.tracking,
                        'lot_id': line.lot_id.id if line else False, 'lot': line.lot_id.name or '' if line else '',
                        'owner_id': line.owner_id.id if line else False,
                        'location_id': source.id, 'source': source.display_name,
                        'destination_id': destination.id, 'destination': destination.display_name,
                        'package_id': package.id, 'package': package.name or '',
                        'destination_package_id': result_package.id, 'destination_package': result_package.name or '',
                        'uom': move.product_id.uom_id.display_name, 'uom_id': move.product_id.uom_id.id,
                        'expected': expected, 'quantity': done, 'counted': bool(line and line.picked),
                        'group': ':'.join(str(value) for value in [picking.id, *part]),
                        'stamp': str(line.write_date if line else move.write_date)})
        return rows

    def _fingerprint(self):
        return digest({'rows': self._rows(), 'moves': [(m.id, m.state, m.product_uom_qty, m.uom_id.id)
            for m in self.picking_ids.move_ids], 'scope': self.picking_ids.ids, 'configuration': self._configuration()})

    def _configuration(self):
        nomenclature = self.company_id.nomenclature_id
        return {'operations': [(p.id, p.blue_barcode_grouping, p.blue_barcode_allow_overquantity,
            p.blue_barcode_allow_new_lot, p.blue_barcode_allow_pack) for p in self.picking_ids.picking_type_id],
            'nomenclature': nomenclature.id, 'nomenclature_stamp': str(nomenclature.write_date),
            'rules': [(rule.id, str(rule.write_date)) for rule in nomenclature.rule_ids]}

    def _view(self):
        self.check_access('read')
        self._read_target()
        return {'id': self.id, 'name': self.name, 'kind': self.kind, 'revision': self.revision,
                'state': self.state, 'rows': self._rows(), 'context': self.scan_context or {},
                'actions': self._actions(), 'record_id': self._record_id()}

    def _read_target(self):
        self.picking_ids.check_access('read')
        if self.batch_id:
            self.batch_id.check_access('read')

    def _record_id(self):
        return self.picking_id.id if self.kind == 'picking' else self.batch_id.id

    def _is_ended(self):
        if self.kind == 'batch' and self.batch_id.state in ('done', 'cancel'):
            return True
        return bool(self.picking_ids) and all(p.state in ('done', 'cancel') for p in self.picking_ids)

    def _actions(self):
        actions = ['validate'] if self.kind in ('picking', 'batch') else []
        if self.picking_ids and all(p.picking_type_id.blue_barcode_allow_pack for p in self.picking_ids):
            actions.append('pack')
        return actions

    def _decode(self, raw):
        scan_text(raw)
        standard = self._standard_decode(raw)
        if standard:
            return standard
        rows = self._rows()
        possibilities = []
        if any(r['barcode'] == raw for r in rows):
            possibilities.append('product')
        if self.env['stock.location'].search_count([
                ('barcode', '=', raw), ('id', 'in', list({r['location_id'] for r in rows}
                    | {r['destination_id'] for r in rows if r['destination_id']}))], limit=1):
            possibilities.append('location')
        if any(r['package'] == raw for r in rows):
            possibilities.append('package')
        pending = (self.scan_context or {}).get('pending')
        if pending and not possibilities:
            possibilities.append('lot')
        elif any(r['lot'] == raw for r in rows):
            possibilities.append('lot')
        if len(possibilities) > 1:
            raise UserError(self.env._('编码匹配多种类型,请使用明确的解析策略.'))
        return {'kind': possibilities[0] if possibilities else 'product', 'code': raw, 'quantity': 1, 'lot': '', 'uom': '',
                'location': '', 'package': '', 'reason': ''}

    def _standard_decode(self, raw):
        nomenclature = self.company_id.nomenclature_id
        if not nomenclature:
            return None
        value = nomenclature.parse_barcode(raw)
        if isinstance(value, list):
            by_type = {}
            for item in value:
                if item['type'] in by_type:
                    raise UserError(self.env._('GS1 内同类字段重复,请使用明确解析策略.'))
                by_type[item['type']] = item
            if 'product' not in by_type:
                raise UserError(self.env._('此 GS1 缺少商品编码,不能作为商品计数.'))
            qty = by_type.get('quantity', {})
            return {'kind': 'product', 'code': by_type['product']['value'],
                'quantity': quantity(qty.get('value', 1)),
                'lot': by_type.get('lot', {}).get('value', ''),
                'location': by_type.get('location', {}).get('value', ''),
                'package': by_type.get('package', {}).get('value', ''),
                'uom': qty['rule'].associated_uom_id.name or '' if qty else '', 'reason': 'GS1'}
        if nomenclature.is_gs1_nomenclature and (raw.startswith((']C1', ']d2', ']Q3')) or '\x1d' in raw):
            raise UserError(self.env._('GS1 格式或校验未通过,请核对标签和命名规则.'))
        if type(value) is dict and value.get('type') == 'product' and value.get('base_code') != raw:
            return {'kind': 'product', 'code': value['base_code'], 'quantity': 1,
                'lot': '', 'location': '', 'package': '', 'uom': '', 'reason': 'EAN alias'}
        return None

    def _decide(self, parsed, candidates):
        if parsed['kind'] != 'product':
            return {'action': 'select', 'keys': [], 'reason': ''}
        return {'action': 'count', 'keys': [candidates[0]['key']], 'reason': ''} if len(candidates) == 1 else {
            'action': 'prompt', 'keys': [], 'reason': self.env._('存在多个匹配明细,请先选择位置或明细.')}

    def _select_candidates(self, parsed, row_key, group_key):
        rows = self._rows()
        products = self._products_for_code(parsed['code'])
        if len(products) != 1:
            raise UserError(self.env._('商品码无匹配或不唯一,请核对产品条码.'))
        candidates = [r for r in rows if r['product_id'] == products.id]
        context = self.scan_context or {}
        if group_key:
            group_rows = [r for r in rows if r['group'] == group_key]
            if (context.get('location_id') and not parsed.get('location')
                    and group_rows and all(r['location_id'] != context['location_id'] for r in group_rows)):
                raise UserError(self.env._('当前页与已确认来源位置不同,请先扫描本组位置.'))
            if (context.get('destination_id') and group_rows
                    and all(r['destination_id'] != context['destination_id'] for r in group_rows)):
                raise UserError(self.env._('当前页与已确认目的位置不同,请先扫描本组目的位置.'))
        location_code = parsed.get('location')
        if location_code:
            locations = self.env['stock.location'].search([
                ('barcode', '=', location_code), ('company_id', 'in', [False, self.company_id.id])], limit=2)
            if len(locations) != 1:
                raise UserError(self.env._('二维码位置不能唯一识别.'))
            candidates = [r for r in candidates if r['location_id'] == locations.id]
        elif context.get('location_id'):
            candidates = [r for r in candidates if r['location_id'] == context['location_id']]
        if parsed.get('lot'):
            candidates = [r for r in candidates if r['lot'] == parsed['lot'] or not r['lot_id']]
        elif context.get('lot'):
            candidates = [r for r in candidates if r['lot'] == context['lot'] or not r['lot_id']]
        if context.get('destination_id'):
            candidates = [r for r in candidates if r['destination_id'] == context['destination_id']]
        if context.get('package_id'):
            candidates = [r for r in candidates if r['package_id'] == context['package_id']]
        if parsed.get('package'):
            candidates = [r for r in candidates if r['package'] == parsed['package']]
        if row_key:
            selected = [r for r in rows if r['key'] == row_key]
            if not selected:
                raise UserError(self.env._('所选明细已变化,请重新选择.'))
            if selected[0]['product_id'] == products.id:
                candidates = [r for r in candidates if r['key'] == row_key]
        if group_key and not (row_key and selected[0]['product_id'] == products.id):
            current = [r for r in candidates if r['group'] == group_key]
            if current:
                candidates = current
        if not candidates:
            raise UserError(self.env._('此商品不在当前允许的作业明细或库存维度内.'))
        return candidates

    def _products_for_code(self, code):
        company = fields.Domain('company_id', 'in', [False, self.company_id.id])
        products = self.env['product.product'].search(fields.Domain('barcode', '=', code) & company, limit=201)
        units = self.env['product.uom'].search(fields.Domain('barcode', '=', code) & company, limit=2)
        return products | units.product_id

    def _quantity_in_product_uom(self, product, parsed, total=False):
        amount = quantity(parsed['quantity'], zero=total)
        if total:
            return amount
        units = product._get_available_uoms() | self.env['product.uom'].search([
            ('product_id', '=', product.id), ('company_id', 'in', [False, self.company_id.id])]).uom_id
        if parsed.get('uom'):
            chosen = units.filtered(lambda unit: unit.name == parsed['uom'] or unit.display_name == parsed['uom'])
        else:
            chosen = self.env['product.uom'].search([
                ('barcode', '=', parsed.get('code')), ('product_id', '=', product.id),
                ('company_id', 'in', [False, self.company_id.id])], limit=2).uom_id or product.uom_id
        if len(chosen) != 1:
            raise UserError(self.env._('数量单位不能唯一匹配产品允许的单位.'))
        converted = chosen._compute_quantity(amount, product.uom_id, round=False)
        return quantity(converted)

    def _apply_count(self, row, parsed, total=False):
        move = self.env['stock.move'].browse(row['move_id'])
        move.check_access('write')
        product = move.product_id
        amount = self._quantity_in_product_uom(product, parsed, total)
        new_quantity = amount if total else row['quantity'] + amount
        quantity(new_quantity, zero=True)
        if product.uom_id.compare(product.uom_id.round(new_quantity), new_quantity):
            raise ValidationError(self.env._('数量不符合产品单位精度.'))
        lot = self.env['stock.lot']
        if product.tracking in ('lot', 'serial'):
            lot_name = parsed.get('lot') or row['lot'] or (self.scan_context or {}).get('lot')
            lot = self.env['stock.lot'].search([
                ('product_id', '=', product.id), ('company_id', '=', self.company_id.id), ('name', '=', lot_name)], limit=2)
            if (not lot and lot_name and move.picking_type_id.blue_barcode_allow_new_lot
                    and move.picking_type_id.use_create_lots):
                lot = self.env['stock.lot'].create({'name': lot_name, 'product_id': product.id, 'company_id': self.company_id.id})
            if len(lot) != 1:
                raise UserError(self.env._('请扫描或选择与产品匹配的已有批次/序列号.'))
            if row['lot_id'] and row['lot_id'] != lot.id:
                raise UserError(self.env._('批次与当前明细不同.'))
            if product.tracking == 'serial' and new_quantity not in (0, 1):
                raise UserError(self.env._('序列号不能重复扫描,数量只能为 0 或 1.'))
            if product.tracking == 'serial' and any(
                    other.picked and other.lot_id == lot and other.id != row['line_id']
                    for other in self.picking_ids.move_line_ids):
                raise UserError(self.env._('此序列号已在作业中确认.'))
        actual = sum(l.quantity_product_uom for l in move.move_line_ids if l.picked)
        demand = move.uom_id._compute_quantity(move.product_uom_qty, product.uom_id)
        if (not move.picking_type_id.blue_barcode_allow_overquantity
                and product.uom_id.compare(actual - row['quantity'] + new_quantity, demand) > 0):
            raise UserError(self.env._('扫描数量超过单据需求.'))
        line = self.env['stock.move.line'].browse(row['line_id'])
        values = {'quantity': product.uom_id._compute_quantity(new_quantity, line.uom_id if line else move.uom_id),
                  'picked': True}
        if lot:
            values['lot_id'] = lot.id
        if line:
            line.write(values)
        else:
            line = self.env['stock.move.line'].create({**values, 'move_id': move.id, 'picking_id': move.picking_id.id,
                'product_id': product.id, 'uom_id': move.uom_id.id,
                'location_id': move.location_id.id, 'location_dest_id': move.location_dest_id.id})
        expected = dict(self.expected or {})
        expected['line:%s' % line.id] = row['expected']
        self._internal().write({'expected': expected, 'scan_context': {k: v for k, v in (self.scan_context or {}).items() if k != 'lot'}})
        return {'key': 'line:%s' % line.id, 'group': row['group'], 'old': row['quantity'], 'quantity': new_quantity}

    def _consume_product(self, parsed, row_key, group_key):
        candidates = self._select_candidates(parsed, row_key, group_key)
        decision = self._decide(parsed, candidates)
        if decision['action'] != 'count' or len(decision['keys']) != 1:
            raise UserError(decision.get('reason') or self.env._('请补充扫描信息或选择唯一明细.'))
        chosen = [r for r in candidates if r['key'] == decision['keys'][0]]
        if len(chosen) != 1:
            raise ValidationError(self.env._('扫描策略选择了范围之外的明细.'))
        row = chosen[0]
        if (row['tracking'] in ('lot', 'serial') and not parsed.get('lot')
                and not row['lot'] and not (self.scan_context or {}).get('lot')):
            self._internal().write({'scan_context': {**(self.scan_context or {}),
                'pending': {'parsed': parsed, 'key': row['key'], 'group': row['group']}}})
            return {'pending': True, 'group': row['group'], 'selected': self.env._('已选择产品,请扫描批次/序列号;尚未计数.')}
        result = self._apply_count(row, parsed)
        return self._followup(decision, result)

    def _followup(self, decision, result):
        after = decision.get('after', '')
        if after and after not in (self._actions() + ['next_group']):
            raise ValidationError(self.env._('扫描策略请求了未授权的后续动作.'))
        if after:
            result['after'] = after
        return result

    def _consume_scan(self, raw, row_key, group_key):
        parsed = self._decode(raw)
        if (self.scan_context or {}).get('pending') and parsed['kind'] != 'lot':
            raise UserError(self.env._('请先补扫当前产品的批次/序列号,或明确取消待补扫产品.'))
        if parsed['kind'] == 'product':
            if (self.scan_context or {}).get('pending'):
                raise UserError(self.env._('上一产品尚缺批次/序列号,请先补扫或取消待补扫产品.'))
            return self._consume_product(parsed, row_key, group_key)
        decision = self._decide(parsed, [])
        if decision['action'] != 'select':
            raise UserError(decision.get('reason') or self.env._('当前步骤不能选择此编码.'))
        rows = self._rows()
        context = dict(self.scan_context or {})
        if parsed['kind'] == 'location':
            locations = self.env['stock.location'].search([
                ('barcode', '=', parsed['code']), ('id', 'in', list({r['location_id'] for r in rows}
                    | {r['destination_id'] for r in rows if r['destination_id']}))], limit=2)
            if len(locations) != 1:
                raise UserError(self.env._('位置不在本单范围或编码不唯一.'))
            source = any(r['location_id'] == locations.id for r in rows)
            context = {'location_id' if source else 'destination_id': locations.id}
            result = {'selected': locations.display_name}
            matching_groups = {r['group'] for r in rows
                if r['location_id' if source else 'destination_id'] == locations.id}
        elif parsed['kind'] == 'package':
            packages = {r['package_id'] for r in rows if r['package'] == parsed['code'] and r['package_id']}
            if len(packages) != 1:
                raise UserError(self.env._('源包裹不在本单范围或不唯一.'))
            context = {**{k: v for k, v in context.items() if k not in ('lot', 'pending')}, 'package_id': packages.pop()}
            result = {'selected': parsed['code']}
            matching_groups = {r['group'] for r in rows if r['package_id'] == context['package_id']}
        elif parsed['kind'] == 'lot':
            pending = context.pop('pending', None)
            if pending:
                self._internal().write({'scan_context': context})
                result = self._consume_product({**pending['parsed'], 'lot': parsed['code']}, pending['key'], pending['group'])
                return result
            lots = {r['lot_id'] for r in rows if r['lot'] == parsed['code'] and r['lot_id']}
            if not lots:
                raise UserError(self.env._('请先选择产品,再扫描批次/序列号.'))
            context['lot'] = parsed['code']
            result = {'selected': parsed['code']}
        else:
            raise ValidationError(self.env._('不支持的扫描类型.'))
        if parsed['kind'] in ('location', 'package') and len(matching_groups) == 1:
            result['group'] = matching_groups.pop()
        self._internal().write({'scan_context': context})
        return self._followup(decision, result)

    def cancel_pending_product(self, client_key, revision):
        self._lock()
        self._check_client(client_key)
        self._check_target()
        if type(revision) is not int or revision != self.revision:
            raise UserError(self.env._('会话版本已变化.'))
        context = dict(self.scan_context or {})
        context.pop('pending', None)
        self._internal().write({'scan_context': context, 'revision': self.revision + 1})
        return self._view()

    def action_view(self, client_key):
        self._check_client(client_key, active=False)
        if self._is_ended():
            self._lock()
            if self.state != 'closed':
                self._internal().write({'state': 'closed', 'revision': self.revision + 1})
            return self._view()
        self._check_target()
        return self._view()

    def action_release(self, client_key):
        self._lock()
        self._check_client(client_key, active=False)
        self._internal().write({'state': 'closed', 'revision': self.revision + 1})
        return True

    def event_status(self, client_key, event_key):
        self._check_client(client_key, active=False)
        identifier(event_key)
        event = self.env['blue.barcode.event'].search([
            ('session_id', '=', self.id), ('event_key', '=', event_key)], limit=1)
        return {'found': bool(event), 'event': event.result or {}, 'view': self._view()}

    def action_event(self, client_key, event_key, revision, payload):
        with self.env.cr.savepoint():
            return self._event(client_key, event_key, revision, payload)

    def _event(self, client_key, event_key, revision, payload):
        self._lock()
        self._check_client(client_key)
        identifier(event_key)
        if (type(payload) is not dict or set(payload) - {'raw', 'row_key', 'group', 'total'}
                or type(payload.get('row_key', '')) is not str or type(payload.get('group', '')) is not str
                or len(payload.get('row_key', '')) > 128 or len(payload.get('group', '')) > 256
                or ('raw' in payload and (type(payload['raw']) is not str or len(payload['raw']) > 8192))
                or ('raw' in payload and 'total' in payload)):
            raise ValidationError(self.env._('无效的扫描事件.'))
        if 'total' in payload:
            # Reject invalid numbers before canonical JSON hashing, so the client
            # receives a definite business rejection instead of an unknown error.
            quantity(payload['total'], zero=True)
        event_hash = digest(payload)
        events = self.env['blue.barcode.event'].search([('session_id', '=', self.id), ('event_key', '=', event_key)], limit=1)
        if events:
            if events.payload_hash != event_hash:
                raise ValidationError(self.env._('同一事件编号不能更换扫描内容.'))
            return {'event': events.result, 'view': self._view(), 'replayed': True}
        self._check_target()
        if type(revision) is not int or revision != self.revision or self.fingerprint != self._fingerprint():
            raise UserError(self.env._('作业数据已变化,请重新核对会话,不要重复扫描.'))
        if 'total' in payload:
            rows = [r for r in self._rows() if r['key'] == payload.get('row_key')]
            if len(rows) != 1:
                raise ValidationError(self.env._('请先选择一条明细再设置总数.'))
            result = self._apply_count(rows[0], {'quantity': quantity(payload['total'], zero=True)}, total=True)
        else:
            raw = scan_text(payload.get('raw'))
            result = self._consume_scan(raw, payload.get('row_key'), payload.get('group'))
        self._internal().write({'revision': self.revision + 1, 'expires_at': fields.Datetime.now() + timedelta(minutes=30)})
        self._internal().write({'fingerprint': self._fingerprint()})
        self.env['blue.barcode.event'].with_context(blue_barcode_token=TOKEN).create({
            'session_id': self.id, 'event_key': event_key, 'payload_hash': event_hash,
            'result': {**result, 'revision': self.revision}})
        return {'event': {**result, 'revision': self.revision}, 'view': self._view(), 'replayed': False}

    def action_execute(self, client_key, revision, action, group_key=''):
        self._lock()
        self._check_client(client_key)
        self._check_target()
        if type(revision) is not int or revision != self.revision or self.fingerprint != self._fingerprint():
            raise UserError(self.env._('作业已变化,请核对后再执行.'))
        if action not in ('validate', 'pack') or action not in self._actions():
            raise AccessError(self.env._('此作业不允许该动作.'))
        if action == 'pack':
            if type(group_key) is not str or not group_key or len(group_key) > 256:
                raise ValidationError(self.env._('请先选择需要装箱的业务组.'))
            rows = [r for r in self._rows() if r['group'] == group_key and r['quantity'] > 0 and not r['destination_package_id']]
            lines = self.env['stock.move.line'].browse([r['line_id'] for r in rows if r['line_id']])
            if not lines:
                raise UserError(self.env._('当前组没有已确认且尚未装箱的货物.'))
            # Native hooks retain package constraints and return their wizard.
            result = lines.with_context(all_move_line_ids=False, force_move_lines=False).action_put_in_pack()
            self._internal().write({'revision': self.revision + 1, 'fingerprint': self._fingerprint()})
            return {'action': result if isinstance(result, dict) else False, 'view': self._view()}
        # Native validation owns warnings, backorders and stock accounting.
        result = self.picking_id.button_validate() if self.kind == 'picking' else self.batch_id.action_done()
        self._internal().write({'revision': self.revision + 1, 'fingerprint': self._fingerprint()})
        if self._is_ended():
            self._internal().write({'state': 'closed'})
        return {'action': result if isinstance(result, dict) else False, 'view': self._view()}
