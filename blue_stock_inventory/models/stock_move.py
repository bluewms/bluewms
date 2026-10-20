from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .guard import trusted


class StockMove(models.Model):
    _inherit = 'stock.move'

    inventory_adjustment_id = fields.Many2one('stock.inventory', '盘点单', check_company=True, copy=False, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        if not trusted(self) and (any(v.get('inventory_adjustment_id') for v in vals_list)
                or self.env.context.get('default_inventory_adjustment_id')):
            raise AccessError(self.env._('盘点流水关联由系统生成.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'inventory_adjustment_id' in vals and not trusted(self):
            raise AccessError(self.env._('盘点流水关联不可修改.'))
        if not trusted(self) and {'product_id', 'uom_id', 'quantity', 'product_uom_qty', 'location_id', 'location_dest_id', 'state'}.intersection(vals):
            if self.filtered(lambda m: m.inventory_adjustment_id and m.state == 'done'):
                raise UserError(self.env._('已记账盘点流水不可修改,请用新的库存调整记录更正.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_inventory_history(self):
        if self.filtered(lambda m: m.inventory_adjustment_id and m.state == 'done'):
            raise UserError(self.env._('已记账盘点流水必须保留.'))
