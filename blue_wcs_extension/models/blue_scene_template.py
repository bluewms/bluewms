from odoo import fields, models


class BlueSceneTemplate(models.Model):
    _inherit = 'blue.scene.template'

    hook_code = fields.Selection(selection_add=[('wcs_creation', 'WCS创建策略')], ondelete={'wcs_creation': 'cascade'})
