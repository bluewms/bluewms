from odoo import api, fields, models

from .guard import PROTOCOL_TOKEN


class WcsEvent(models.Model):
    _inherit = 'wcs.event'

    protocol_report = fields.Json('设备原始回报', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_protocol_token') is PROTOCOL_TOKEN:
            vals_list = [dict(vals, protocol_report=self.env.context.get('blue_protocol_report')) for vals in vals_list]
        return super().create(vals_list)
