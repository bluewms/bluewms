from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    agv_map_point = fields.Char('AGV地图坐标点')
