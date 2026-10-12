from odoo import api, fields, models


class StockStorageCategory(models.Model):
    _inherit = 'stock.storage.category'

    capacity_qty = fields.Float(
        string='单一包裹类型数量', compute='_compute_capacity_qty', store=True,
    )

    @api.depends('capacity_ids', 'capacity_ids.quantity', 'capacity_ids.package_type_id')
    def _compute_capacity_qty(self):
        for category in self:
            capacities = category.capacity_ids.filtered('package_type_id')
            category.capacity_qty = capacities.quantity if len(capacities) == 1 else 0
