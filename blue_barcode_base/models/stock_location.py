from odoo import api, fields, models
from odoo.tools import BinaryBytes


class StockLocation(models.Model):
    _inherit = 'stock.location'

    barcode_img = fields.Binary('条码预览', compute='_compute_barcode_img')

    @api.depends('barcode')
    def _compute_barcode_img(self):
        for location in self:
            location.barcode_img = False
            if not location.barcode:
                continue
            try:
                image = self.env['ir.actions.report'].barcode(
                    'Code128', location.barcode, width=300, height=100, humanreadable=True,
                )
            except ValueError:
                # An unsupported value must not prevent editing the location.
                continue
            location.barcode_img = BinaryBytes(image)
