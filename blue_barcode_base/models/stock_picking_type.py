from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    blue_barcode_grouping = fields.Selection([
        ('location', '来源与目的位置'), ('source_package', '源包裹'),
        ('destination_package', '目的包裹')], string='扫码分页分组', default='location', required=True)
    blue_barcode_allow_overquantity = fields.Boolean('允许条码超量', default=False)
    blue_barcode_allow_new_lot = fields.Boolean('允许扫码创建批次/序列号', default=False)
    blue_barcode_allow_pack = fields.Boolean('允许条码装箱', default=False)
