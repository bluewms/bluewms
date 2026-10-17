from odoo import models
from odoo.exceptions import UserError
from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def write(self, vals):
        protected = {'quantity', 'product_id', 'lot_id', 'uom_id', 'location_id', 'location_dest_id', 'package_id', 'result_package_id', 'owner_id', 'picking_id', 'move_id'}
        if protected & set(vals) and self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            rows = self.env['wcs.plan.line'].search([('move_line_id', 'in', self.ids)])
            if any(any(task.state != 'cancelled' for task in row.plan_id.request_ids) for row in rows):
                raise UserError(self.env._('Reconcile the fixed WCS plan before changing its goods or locations.'))
        return super().write(vals)

    def unlink(self):
        rows = self.env['wcs.plan.line'].search([('move_line_id', 'in', self.ids)])
        if any(any(task.state != 'cancelled' for task in row.plan_id.request_ids) for row in rows):
            raise UserError(self.env._('Keep stock lines referenced by active WCS plans.'))
        return super().unlink()
