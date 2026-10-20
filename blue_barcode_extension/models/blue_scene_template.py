from odoo import fields, models


class BlueSceneTemplate(models.Model):
    _inherit = 'blue.scene.template'

    hook_code = fields.Selection(selection_add=[('barcode_policy', '条码扫描策略')],
                                 ondelete={'barcode_policy': 'cascade'})
