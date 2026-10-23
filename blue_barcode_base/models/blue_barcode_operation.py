from odoo import models
from odoo.exceptions import AccessError, UserError, ValidationError


class BlueBarcodeSession(models.Model):
    _inherit = 'blue.barcode.session'

    def _scope_changed(self):
        if self.kind != 'batch':
            return False
        current = self.batch_id.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        return set(current.ids) != set(self.picking_ids.ids)

    def _operation_status(self, rows):
        if self.kind not in ('picking', 'batch'):
            return {}
        lines = []
        unstarted = []
        for picking in self.picking_ids:
            processed = False
            for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                unit = move.product_id.uom_id
                expected = move.uom_id._compute_quantity(move.product_uom_qty, unit)
                actual = sum(line.quantity_product_uom for line in move.move_line_ids if line.picked)
                processed = processed or unit.compare(actual, 0) > 0
                lines.append({'id': move.id, 'picking': picking.name, 'product': move.product_id.display_name,
                    'expected': expected, 'quantity': actual, 'remaining': max(0, unit.round(expected - actual)),
                    'uom': unit.display_name, 'complete': unit.compare(actual, expected) >= 0,
                    'backorder': picking.picking_type_id.create_backorder})
            if not processed and picking.state not in ('done', 'cancel'):
                unstarted.append(picking.name)
        pending = bool((self.scan_context or {}).get('pending'))
        started = any(row['counted'] and row['quantity'] > 0 for row in rows)
        reason = (self.env._('请先补扫批次/序列号或取消待补扫产品.') if pending
            else self.env._('尚未录入有效作业数量,不能将预留量作为已扫描量验证.') if not started else '')
        active = self.state == 'active' and not self._is_ended()
        return {'validate': active and not reason, 'validate_reason': reason,
                'complete': bool(lines) and all(line['complete'] for line in lines),
                'lines': lines, 'unstarted': unstarted,
                'pack': active and not pending and any(row['quantity'] > 0 and row['counted']
                    and not row['destination_package_id'] for row in rows),
                'wcs': active and started and not pending,
                'primary': 'validate', 'pending': pending}

    def _document_options(self):
        if self.kind not in ('picking', 'batch'):
            return []
        options = [
            {'key': 'document', 'name': self.env._('查看单据'), 'icon': 'description'},
            {'key': 'print_operations', 'name': self.env._('打印批次作业单') if self.kind == 'batch'
                else self.env._('打印拣货作业单'), 'icon': 'print'},
            {'key': 'print_delivery', 'name': self.env._('打印送货单'), 'icon': 'local_shipping'},
            {'key': 'labels', 'name': self.env._('打印产品/批次标签'), 'icon': 'barcode'},
        ]
        if self.env.user.has_group('stock.group_tracking_lot'):
            options.append({'key': 'print_packages', 'name': self.env._('打印包裹标签'), 'icon': 'inventory_2'})
        if self.kind == 'picking' and self.picking_id.state == 'done' and self.picking_id.show_return:
            options.append({'key': 'return_document', 'name': self.env._('退货'), 'icon': 'assignment_return'})
        return options

    def _outcome(self):
        if self.kind not in ('picking', 'batch'):
            return {'ended': self._is_ended(), 'cancelled': False}
        backorders = self.picking_ids.backorder_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        backorders.check_access('read')
        return {'pickings': [{'id': p.id, 'name': p.name, 'kind': 'picking', 'state': p.state}
                    for p in self.picking_ids],
                'backorders': [{'id': p.id, 'name': p.name, 'kind': 'picking'} for p in backorders],
                'pending_pickings': [{'id': p.id, 'name': p.name, 'kind': 'picking'}
                    for p in self.picking_ids if p.state not in ('done', 'cancel')],
                'ended': self._is_ended(),
                'cancelled': self.batch_id.state == 'cancel' if self.kind == 'batch'
                    else self.picking_id.state == 'cancel'}

    def _view(self):
        view = super()._view()
        view.update(operation=self._operation_status(view['rows']), documents=self._document_options(),
                    outcome=self._outcome())
        return view

    def _check_operation(self, action, group_key=''):
        if (self.scan_context or {}).get('pending'):
            raise UserError(self.env._('请先补扫批次/序列号或取消待补扫产品.'))
        status = self._operation_status(self._rows())
        if action == 'validate' and not status.get('validate'):
            raise UserError(status.get('validate_reason') or self.env._('当前作业不能验证.'))
        if action == 'pack' and not status.get('pack'):
            raise UserError(self.env._('没有已扫描且未装箱的货物.'))
        if action == 'wcs' and not status.get('wcs'):
            raise UserError(self.env._('请先录入有效作业数量再申请 WCS.'))

    def action_validation_review(self, client_key, revision):
        self._check_client(client_key)
        self._check_target()
        if type(revision) is not int or revision != self.revision or self.fingerprint != self._fingerprint():
            raise UserError(self.env._('作业已变化,请核对后再验证.'))
        self._check_operation('validate')
        return {'name': self.name, 'kind': self.kind, 'revision': self.revision,
                **self._operation_status(self._rows())}

    def action_document(self, client_key, action, picking_id=False):
        self._check_client(client_key, active=False)
        self._read_target()
        if action not in {option['key'] for option in self._document_options()}:
            raise AccessError(self.env._('不支持此单据操作.'))
        if picking_id is not False and (type(picking_id) is not int or picking_id <= 0):
            raise ValidationError('Invalid picking identity.')
        target = self.picking_id if self.kind == 'picking' else self.batch_id
        if picking_id:
            allowed = self.picking_ids | self.picking_ids.backorder_ids
            if picking_id not in allowed.ids or action != 'document':
                raise AccessError(self.env._('只能查看本次作业及其欠单.'))
            target = self.env['stock.picking'].browse(picking_id)
        target.check_access('read')
        if target.company_id != self.env.company:
            raise AccessError(self.env._('请切换至单据所属公司.'))
        if action in ('document', 'return_document'):
            # Odoo 20 starts a return from the completed native form, where the
            # operator chooses return quantities. Merely opening it creates nothing.
            title = self.env._('退货: %(name)s (更多 - 退回)', name=target.display_name) if action == 'return_document' else target.display_name
            return {'type': 'ir.actions.act_window', 'name': title,
                    'res_model': target._name, 'res_id': target.id, 'views': [(False, 'form')],
                    'target': 'new'}
        if action == 'labels':
            return target.action_open_label_layout()
        report = {'print_operations': 'stock.action_report_picking_batch' if self.kind == 'batch'
                    else 'stock.action_report_picking', 'print_delivery': 'stock.action_report_delivery',
                  'print_packages': 'stock.action_report_picking_packages'}[action]
        records = target if action == 'print_operations' and self.kind == 'batch' else self.picking_ids
        return self.env.ref(report).report_action(records, config=False)
