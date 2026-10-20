from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_blue_barcode(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.client', 'tag': 'blue_barcode.workspace',
                'name': self.env._('条码作业'), 'params': {'kind': 'picking', 'record_id': self.id}}
