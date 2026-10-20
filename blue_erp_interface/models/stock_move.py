from odoo import api, fields, models
from odoo.exceptions import AccessError

from .guard import ERP_TOKEN


class StockMove(models.Model):
    _inherit = 'stock.move'

    blue_erp_line_id = fields.Char('ERP 行 ID', copy=True, readonly=True, index=True)
    blue_erp_lot_id = fields.Many2one('stock.lot', 'ERP 指定批次', copy=True, check_company=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('blue_erp_line_id') for v in vals_list) and self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            raise AccessError(self.env._('ERP 行关联由接口生成.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'blue_erp_line_id' in vals and self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            raise AccessError(self.env._('ERP 行关联不能直接修改.'))
        return super().write(vals)

    def copy_data(self, default=None):
        data = super().copy_data(default)
        if self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            for vals in data:
                vals['blue_erp_line_id'] = False
                vals['blue_erp_lot_id'] = False
        return data
