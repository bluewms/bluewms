from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    default_package_type = fields.Many2one('stock.package.type', string='默认包裹类型')
    not_all_package = fields.Boolean('移动不是整个包裹提醒(API)')
    is_auto_lot = fields.Boolean('自动生成批次号(API)')
