from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .guard import trusted


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    inventory_adjustment_id = fields.Many2one('stock.inventory', '盘点单', check_company=True, copy=False, ondelete='restrict')
    inventory_line_id = fields.Many2one('stock.inventory.line', '盘点明细', check_company=True, copy=False, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        if not trusted(self) and (any(v.get('inventory_adjustment_id') or v.get('inventory_line_id') for v in vals_list)
                or self.env.context.get('default_inventory_adjustment_id') or self.env.context.get('default_inventory_line_id')):
            raise AccessError(self.env._('盘点流水关联由系统生成.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'inventory_adjustment_id', 'inventory_line_id'}.intersection(vals) and not trusted(self):
            raise AccessError(self.env._('盘点流水关联不可修改.'))
        physical = {'product_id', 'uom_id', 'quantity', 'location_id', 'location_dest_id', 'lot_id', 'package_id', 'result_package_id', 'owner_id', 'move_id'}
        if not trusted(self) and physical.intersection(vals) and self.filtered(lambda l: l.inventory_line_id.applied):
            raise UserError(self.env._('已记账盘点流水不可修改,请用新的库存调整记录更正.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_inventory_history(self):
        if self.filtered(lambda l: l.inventory_line_id.applied):
            raise UserError(self.env._('已记账盘点流水必须保留.'))
