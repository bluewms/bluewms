from odoo import fields, models
from odoo.exceptions import AccessError
from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN


class StockPackage(models.Model):
    _inherit = 'stock.package'

    blue_wcs_generation = fields.Integer(copy=False)

    def _wcs_lock_carrier(self):
        self.ensure_one()
        self.check_access('read')
        # Narrow fixed-column update serializes this physical carrier across pickings.
        self.env.cr.execute('UPDATE stock_package SET blue_wcs_generation = COALESCE(blue_wcs_generation, 0) + 1 WHERE id = %s', [self.id])
        self.invalidate_recordset(['blue_wcs_generation'])

    def write(self, vals):
        if 'blue_wcs_generation' in vals and self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('Carrier counters require the planning service.'))
        return super().write(vals)
