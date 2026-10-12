# Copyright 2026 宁波宝蓝物流科技有限公司
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import models

from .stock_quant import _SAME_LOCATION_MOVE_TOKEN


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _synchronize_quant(self, quantity, location, action='available', in_date=False, **quants_value):
        self.ensure_one()
        if (action == 'available' and isinstance(self.id, int)
                and self.location_id == self.location_dest_id == location):
            self = self.with_context(
                blue_stock_same_location_token=_SAME_LOCATION_MOVE_TOKEN,
                blue_stock_move_line_id=self.id,
            )
        return super()._synchronize_quant(quantity, location, action=action, in_date=in_date, **quants_value)
