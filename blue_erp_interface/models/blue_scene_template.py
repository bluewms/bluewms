from odoo import fields, models


class BlueSceneTemplate(models.Model):
    _inherit = 'blue.scene.template'

    hook_code = fields.Selection(selection_add=[('erp_mapping', 'ERP 接口')], ondelete={'erp_mapping': 'cascade'})
