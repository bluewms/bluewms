from odoo import fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    partner_ref = fields.Char('客户订单号')
