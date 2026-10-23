from odoo import models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def action_blue_barcode(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.client', 'tag': 'blue_barcode.workspace',
                'target': 'fullscreen', 'name': self.env._('批次扫码'), 'params': {'kind': 'batch', 'record_id': self.id}}
