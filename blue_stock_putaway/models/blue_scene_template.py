from odoo import fields, models


class BlueSceneTemplate(models.Model):
    _inherit = 'blue.scene.template'

    requires_batch_names = fields.Boolean('补充规则需要批次号', default=False)
