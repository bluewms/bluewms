from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .guard import ERP_TOKEN, internal


class BlueErpDocument(models.Model):
    _name = 'blue.erp.document'
    _description = 'ERP 来源单据'
    _check_company_auto = True
    _rec_name = 'number'

    interface_id = fields.Many2one('blue.erp.interface', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True)
    external_id = fields.Char('ERP 单据 ID', required=True, index=True)
    number = fields.Char('ERP 单号', required=True)
    normalized = fields.Json('标准化原始单据', required=True)
    content_hash = fields.Char(required=True)
    release_id = fields.Many2one('blue.config.release', '固定代码版本', required=True, check_company=True, ondelete='restrict')
    picking_ids = fields.One2many('stock.picking', 'blue_erp_document_id', 'WMS 单据')
    event_ids = fields.One2many('blue.erp.event', 'document_id', '完成反馈')
    _unique_source = models.Constraint('UNIQUE(interface_id, external_id)', 'ERP 来源单据已存在.')

    @api.model_create_multi
    def create(self, vals_list):
        internal(self)
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('来源单据及固定版本不可修改.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_history(self):
        raise AccessError(self.env._('ERP 来源单据须保留追溯.'))

    def _location(self, root, code):
        if not code:
            return root
        records = self.env['stock.location'].search([
            ('barcode', '=', code), ('id', 'child_of', root.id), ('active', '=', True),
            ('company_id', 'in', [False, self.company_id.id])], limit=2)
        if len(records) != 1:
            raise ValidationError(self.env._('库位编码未知、重复或超出接口允许范围: %s', code))
        return records

    def _create_pickings(self):
        self.ensure_one()
        internal(self)
        interface = self.interface_id
        data = self.normalized
        partner = self.env['res.partner']
        if data['partner_code']:
            partner = partner.search([('ref', '=', data['partner_code']), ('company_id', 'in', [False, self.company_id.id])], limit=2)
            if len(partner) != 1:
                raise ValidationError(self.env._('往来单位编码不存在或不唯一.'))
        groups = {}
        for row in data['lines']:
            product = self.env['product.product'].search([('default_code', '=', row['product_code']),
                ('is_storable', '=', True), ('company_id', 'in', [False, self.company_id.id])], limit=2)
            if len(product) != 1 or row['uom'] != product.uom_id.with_context(lang=None).name:
                raise ValidationError(self.env._('物料不存在、不唯一或单位与库存单位不符: %s', row['product_code']))
            lot = self.env['stock.lot']
            if row['lot']:
                lot = lot.search([('name', '=', row['lot']), ('product_id', '=', product.id),
                                  ('company_id', '=', self.company_id.id)], limit=2)
                if len(lot) != 1:
                    raise ValidationError(self.env._('批次不存在或不唯一.'))
            source = self._location(interface.location_src_id, row['source_code'])
            destination = self._location(interface.location_dest_id, row['destination_code'])
            key = (row['group'], source.id, destination.id)
            if key not in groups:
                groups[key] = self.env['stock.picking'].with_context(blue_erp_token=ERP_TOKEN).create({
                    'company_id': self.company_id.id, 'picking_type_id': interface.picking_type_id.id,
                    'partner_id': partner.id, 'location_id': source.id, 'location_dest_id': destination.id,
                    'origin': self.number, 'blue_erp_document_id': self.id})
            move = self.env['stock.move'].with_context(blue_erp_token=ERP_TOKEN).create({
                'company_id': self.company_id.id, 'picking_id': groups[key].id,
                'product_id': product.id, 'uom_id': product.uom_id.id, 'product_uom_qty': row['quantity'],
                'location_id': source.id, 'location_dest_id': destination.id,
                'blue_erp_line_id': row['external_line_id']})
            if lot:
                move.blue_erp_lot_id = lot
        pickings = self.picking_ids
        pickings.action_confirm()
        # Native reservation and putaway retain the authoritative stock rules.
        pickings.action_assign()
