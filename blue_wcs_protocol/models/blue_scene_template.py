from odoo import fields, models


class BlueSceneTemplate(models.Model):
    _inherit = 'blue.scene.template'

    hook_code = fields.Selection(selection_add=[('device_protocol', '设备连接接口')],
                                 ondelete={'device_protocol': 'cascade'})
