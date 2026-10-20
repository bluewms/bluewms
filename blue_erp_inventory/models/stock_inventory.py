from odoo import fields, models


class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    erp_event_ids = fields.One2many('blue.erp.event', 'inventory_id', 'ERP 差异同步记录')
