from odoo import fields, models


class BlueSceneTemplate(models.Model):
    _name = 'blue.scene.template'
    _description = 'Blue policy runtime definition and legacy example compatibility'

    name = fields.Char('策略接口名称', required=True)
    active = fields.Boolean(default=True)
    hook_code = fields.Selection([('putaway_policy', '上架策略')], required=True, default='putaway_policy')
    contract = fields.Char('接口版本', required=True, default='putaway_policy/1')
    cloud_managed = fields.Boolean('示例由云端维护', default=False)
    requirements = fields.Text('旧版本示例说明')
    code_text = fields.Text('旧版本示例代码')
    test_cases = fields.Text('旧版本示例试算数据')
