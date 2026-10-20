from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .guard import trusted


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    to_do = fields.Boolean('盘点待办', default=False, copy=False)
    current_inventory_id = fields.Many2one('stock.inventory', '当前盘点单', copy=False, check_company=True, ondelete='restrict')
    stock_inventory_ids = fields.Many2many('stock.inventory', 'blue_inventory_quant_rel', 'quant_id', 'inventory_id', string='盘点历史')

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'to_do', 'current_inventory_id', 'stock_inventory_ids'}
        if not trusted(self) and (any(protected.intersection(v) for v in vals_list)
                or any(self.env.context.get('default_' + key) for key in protected)):
            raise AccessError(self.env._('盘点关联只能由盘点单维护.'))
        return super().create(vals_list)

    def write(self, vals):
        if not trusted(self):
            if {'to_do', 'current_inventory_id', 'stock_inventory_ids'}.intersection(vals):
                raise AccessError(self.env._('盘点关联只能由盘点单维护.'))
            if {'inventory_quantity', 'inventory_quantity_auto_apply', 'inventory_diff_quantity'}.intersection(vals) and self.filtered('current_inventory_id'):
                raise UserError(self.env._('此库存正在盘点,请在盘点单明细录入实盘.'))
        return super().write(vals)

    def _apply_inventory(self, date=None):
        inventory_id = self.env.context.get('blue_stock_inventory_id') if trusted(self) else False
        for quant in self:
            # Scope admission protects new/merged quants, not just existing UI markers.
            active = self.env['stock.inventory'].search([('state', '=', 'in_progress'), ('company_id', '=', quant.company_id.id)])
            blocking = active.filtered(lambda i: i.id != inventory_id and self.search_count(i._quant_domain() & fields.Domain('id', '=', quant.id)))
            if (quant.current_inventory_id and quant.current_inventory_id.id != inventory_id) or blocking:
                raise UserError(self.env._('此库存属于进行中的盘点,请通过对应盘点单应用.'))
        return super()._apply_inventory(date=date)

    def _get_inventory_move_values(self, qty, location_id, location_dest_id, package_id=False, package_dest_id=False):
        values = super()._get_inventory_move_values(qty, location_id, location_dest_id, package_id, package_dest_id)
        if trusted(self) and self.env.context.get('blue_stock_inventory_id'):
            inventory_id = self.env.context['blue_stock_inventory_id']
            line_id = self.env.context.get('blue_stock_inventory_line_by_quant', {}).get(str(self.id))
            line = self.env['stock.inventory.line'].browse(line_id).exists() if line_id else self.env['stock.inventory.line']
            if not line or line.inventory_id.id != inventory_id or self not in line._quants():
                raise UserError(self.env._('盘点流水关联未通过校验.'))
            values['inventory_adjustment_id'] = inventory_id
            for command in values.get('move_line_ids', []):
                if command[0] == 0:
                    command[2]['inventory_adjustment_id'] = inventory_id
                    command[2]['inventory_line_id'] = line.id
        return values
