from odoo import fields, models


class UomUom(models.Model):
    _inherit = 'uom.uom'

    barcode = fields.Char('编码')
