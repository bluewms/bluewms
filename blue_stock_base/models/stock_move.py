from odoo import models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        values = super()._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        operation = self.picking_type_id or self.picking_id.picking_type_id
        if operation.code == 'internal' and values.get('package_id') and not values.get('result_package_id'):
            values['result_package_id'] = values['package_id']
        return values


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _put_in_pack(self, package_id=False, package_type_id=False, package_name=False):
        if not package_id and not package_type_id:
            operations = self.picking_type_id or self.picking_id.picking_type_id
            defaults = operations.default_package_type
            if defaults:
                if len(defaults) != 1 or any(operation.default_package_type != defaults for operation in operations):
                    raise UserError(self.env._('Selected lines have different default package types. Select a package type explicitly.'))
                package_type_id = defaults.id
        return super()._put_in_pack(package_id=package_id, package_type_id=package_type_id, package_name=package_name)
