from odoo import api, fields, models
from odoo.exceptions import AccessError

from .asset_guard import check_internal


class BlueCustomizationVersion(models.Model):
    _name = 'blue.customization.version'
    _description = 'Immutable validated Blue policy version'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char('版本名称', required=True)
    profile_id = fields.Many2one('blue.config.profile', required=True, ondelete='restrict', check_company=True, index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='restrict', index=True)
    template_id = fields.Many2one('blue.scene.template', required=True, ondelete='restrict')
    contract = fields.Char('接口版本', required=True)
    code_text = fields.Text('准确代码', required=True)
    requirements = fields.Text('需求说明')
    test_cases = fields.Text('试算输入', required=True)
    test_result = fields.Text('验证结果', required=True)
    content_hash = fields.Char('内容校验值', required=True)
    source = fields.Selection([('manual', '人工编辑'), ('example', '标准示例'), ('ai', 'AI生成')], required=True)
    conversation_ref = fields.Char('AI会话引用')
    base_release_id = fields.Many2one('blue.config.release', ondelete='restrict', check_company=True)

    @api.model_create_multi
    def create(self, vals_list):
        check_internal(self)
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('Validated versions are immutable. Create a new draft.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_immutable(self):
        raise AccessError(self.env._('Validated versions must be retained for audit and rollback.'))
