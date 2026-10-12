from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    package_removal_priority = fields.Char('子位置', related='package_id.package_removal_priority', store=True)

    def write(self, values):
        packages = self.package_id if {'quantity', 'reserved_quantity', 'package_id'} & values.keys() else self.env['stock.package']
        result = super().write(values)
        if packages:
            (packages | self.package_id)._blue_reset_empty_priority()
        return result

    def unlink(self):
        packages = self.package_id
        result = super().unlink()
        packages._blue_reset_empty_priority()
        return result
