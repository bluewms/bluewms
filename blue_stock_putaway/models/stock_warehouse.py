from odoo import api, fields, models
from odoo.exceptions import AccessError


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    blue_putaway_revision = fields.Integer(readonly=True, default=0, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any('blue_putaway_revision' in vals for vals in vals_list):
            raise AccessError(self.env._('Allocation revisions are maintained by the server.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'blue_putaway_revision' in vals:
            raise AccessError(self.env._('Allocation revisions are maintained by the server.'))
        return super().write(vals)

    def _blue_lock_putaway(self):
        self.ensure_one()
        self.check_access('read')
        self.flush_recordset(['blue_putaway_revision'])
        # A row lock alone is not sufficient with REPEATABLE READ snapshots.
        # Updating only this private counter forces concurrent stale transactions
        # to serialize or retry through Odoo's normal transaction retry service.
        # This narrowly scoped SQL operation changes no warehouse business setting.
        self.env.cr.execute(
            'UPDATE stock_warehouse SET blue_putaway_revision = CASE WHEN blue_putaway_revision >= 2000000000 THEN 0 ELSE blue_putaway_revision + 1 END WHERE id = %s',
            [self.id],
        )
        self.invalidate_recordset(['blue_putaway_revision'])
