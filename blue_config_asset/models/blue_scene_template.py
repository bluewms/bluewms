from odoo import fields, models


class BlueSceneTemplate(models.Model):
    _name = 'blue.scene.template'
    _description = 'Approved Blue scene example'

    name = fields.Char('模板名称', required=True)
    hook_code = fields.Selection([('putaway_policy', '上架策略')], required=True, default='putaway_policy')
    contract = fields.Char('接口版本', required=True, default='putaway_policy/1')
    requirements = fields.Text('业务说明', required=True)
    code_text = fields.Text('示例代码', required=True)
    test_cases = fields.Text('示例试算数据', required=True)
