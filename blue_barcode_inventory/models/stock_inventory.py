from odoo import models


class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    def action_blue_barcode(self):
        self.ensure_one()
        self._counter()
        return {'type': 'ir.actions.client', 'tag': 'blue_barcode.workspace',
                'target': 'fullscreen', 'name': self.env._('扫码盘库'), 'params': {'kind': 'inventory', 'record_id': self.id}}
