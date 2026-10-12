from odoo import api, fields, models
from odoo.exceptions import UserError


class StockLocationCoordinate(models.Model):
    _name = 'stock.location.coordinate'
    _description = '库位容量位置'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char('序号', required=True)
    sequence = fields.Integer(default=10)
    location_name = fields.Char('名称')
    location_code = fields.Char('编号')
    location_id = fields.Many2one('stock.location', string='位置', required=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='location_id.company_id', store=True, index=True)

    _unique_position = models.Constraint('UNIQUE(location_id, name)', 'Capacity position numbers must be unique within a location.')

    def _is_in_use(self):
        """Device bridges must additionally check their pending tasks."""
        self.ensure_one()
        return bool(self.env['stock.quant'].search([
            ('location_id', '=', self.location_id.id),
            ('package_removal_priority', 'in', [code for code in (self.name, self.location_code) if code]),
            '|', ('quantity', '!=', 0), ('reserved_quantity', '!=', 0),
        ], limit=1))

    def write(self, values):
        if {'name', 'location_id', 'location_code'} & values.keys():
            if any(coordinate._is_in_use() for coordinate in self):
                raise UserError(self.env._('An occupied capacity position cannot be renumbered or moved.'))
        return super().write(values)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_occupied(self):
        if any(coordinate._is_in_use() for coordinate in self):
            raise UserError(self.env._('An occupied capacity position cannot be removed.'))
