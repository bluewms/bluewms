import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .guard import ERP_TOKEN


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    blue_erp_document_id = fields.Many2one('blue.erp.document', 'ERP 来源单据', readonly=True,
                                           copy=True, check_company=True, ondelete='restrict')
    blue_erp_event_ids = fields.One2many('blue.erp.event', 'picking_id', 'ERP 同步记录')

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('blue_erp_document_id') for v in vals_list) and self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            raise AccessError(self.env._('ERP 单据关联由接口生成.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'blue_erp_document_id' in vals and self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            raise AccessError(self.env._('ERP 来源关联不能直接修改.'))
        return super().write(vals)

    def copy_data(self, default=None):
        data = super().copy_data(default)
        if self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            for vals in data:
                vals['blue_erp_document_id'] = False
        return data

    def _action_done(self):
        pending = self.filtered(lambda p: p.blue_erp_document_id and p.state != 'done')
        for picking in pending:
            document = picking.blue_erp_document_id
            self.env.cr.execute('SELECT id FROM blue_erp_document WHERE id=%s FOR UPDATE', [document.id])
            planned = {row['external_line_id']: row for row in document.normalized['lines']}
            scope = json.loads(document.release_id.snapshot)['scope']['erp_scope']
            if picking.company_id != document.company_id or picking.picking_type_id.id != scope['picking_type_id']:
                raise ValidationError(self.env._('ERP 公司及作业类型关联已变化.'))
            for field, root in [('location_id', scope['source_id']), ('location_dest_id', scope['destination_id'])]:
                locations = picking.move_line_ids.mapped(field)
                allowed = self.env['stock.location'].search([('id', 'in', locations.ids), ('id', 'child_of', root),
                    ('active', '=', True), ('company_id', 'in', [False, document.company_id.id])])
                if locations != allowed and set(locations.ids) != set(allowed.ids):
                    raise ValidationError(self.env._('实际作业位置超出 ERP 接口批准范围.'))
            totals = {}
            for completed in document.picking_ids.filtered(lambda p: p.state == 'done') | picking:
                for line in completed.move_line_ids.filtered(lambda l: l.quantity > 0):
                    source = planned.get(line.move_id.blue_erp_line_id)
                    if not source or line.product_id.default_code != source['product_code']:
                        raise ValidationError(self.env._('ERP 商品及行关联不一致.'))
                    if source['lot'] and line.lot_id.name != source['lot']:
                        raise ValidationError(self.env._('实际批次与 ERP 指定批次不一致.'))
                    key = source['external_line_id']
                    quantity = line.uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
                    totals[key] = totals.get(key, 0) + quantity
                    if line.product_id.uom_id.compare(totals[key], source['quantity']) > 0:
                        raise ValidationError(self.env._('累计完成数量超过 ERP 计划量.'))
        # The token follows only the native completion/split flow, preserving backorder bindings.
        result = super(StockPicking, self.with_context(blue_erp_token=ERP_TOKEN))._action_done()
        for picking in pending.filtered(lambda p: p.state == 'done'):
            picking._erp_enqueue_completion()
        return result

    def _erp_enqueue_completion(self):
        self.ensure_one()
        document = self.blue_erp_document_id
        if self.state != 'done' or not document:
            return
        planned = {row['external_line_id']: row for row in document.normalized['lines']}
        cumulative, acknowledged = {}, {}
        for picking in document.picking_ids.filtered(lambda p: p.state == 'done'):
            for line in picking.move_line_ids:
                key = line.move_id.blue_erp_line_id
                cumulative[key] = cumulative.get(key, 0) + line.uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
        for event in document.event_ids.filtered(lambda e: e.state == 'done'):
            for line in event.input_snapshot['candidates']:
                key = line['external_line_id']
                acknowledged[key] = acknowledged.get(key, 0) + line['quantity']
        rows = []
        for line in self.move_line_ids.filtered(lambda l: l.quantity > 0):
            key = line.move_id.blue_erp_line_id
            rows.append({'external_line_id': key, 'product_code': line.product_id.default_code,
                'quantity': line.uom_id._compute_quantity(line.quantity, line.product_id.uom_id),
                'cumulative_quantity': cumulative[key], 'acknowledged_quantity': acknowledged.get(key, 0),
                'planned_quantity': planned[key]['quantity'], 'uom': line.product_id.uom_id.with_context(lang=None).name,
                'lot': line.lot_id.name or '', 'source_code': line.location_id.barcode or '',
                'destination_code': line.location_dest_id.barcode or '',
                'package': (line.result_package_id or line.package_id).name or ''})
        if rows:
            self.env['blue.erp.event']._enqueue(document.interface_id, document.release_id, 'complete', rows,
                'picking:%s' % self.id, document=document, picking=self)
