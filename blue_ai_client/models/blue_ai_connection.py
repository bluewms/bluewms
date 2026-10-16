from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..guard import TASK_NAME, TEAM_NAME


class BlueAIConnection(models.Model):
    _name = 'blue.ai.connection'
    _description = '宝蓝 AI 用户连接'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='Odoo 用户', required=True,
                             default=lambda self: self.env.user, ondelete='cascade', index=True)
    active = fields.Boolean(default=True)
    agent_name = fields.Char('云端 Agent 名称', help='与云端名称完全一致，不填写 Agent ID。')
    api_key = fields.Char('业务用户 API Key', groups='base.group_system', copy=False)
    team_name = fields.Char('固定团队', compute='_compute_fixed_names')
    task_name = fields.Char('普通聊天任务', compute='_compute_fixed_names')

    _unique_user = models.Constraint('unique(user_id)', '每个 Odoo 用户只能有一份云端连接。')

    def _compute_fixed_names(self):
        for record in self:
            record.team_name = TEAM_NAME
            record.task_name = TASK_NAME

    @api.constrains('agent_name', 'api_key', 'user_id')
    def _check_binding(self):
        for record in self:
            if record.user_id.share:
                raise ValidationError(self.env._('只允许为内部用户配置云端连接。'))
            if record.agent_name and (record.agent_name != record.agent_name.strip()
                                      or len(record.agent_name) > 128 or '\n' in record.agent_name):
                raise ValidationError(self.env._('Agent 名称必须是最多 128 字符的单行文本，不能有首尾空格。'))
            if record.api_key and (len(record.api_key) > 512 or any(c.isspace() for c in record.api_key)):
                raise ValidationError(self.env._('API Key 格式无效。'))

    @api.model
    def _for_current_user(self):
        connection = self.search([
            ('user_id', '=', self.env.uid), ('active', '=', True), ('user_id.active', '=', True),
        ], limit=1)
        if not connection:
            raise UserError(self.env._('请让管理员为当前 Odoo 用户配置云端 Agent 和业务用户 Key。'))
        return connection

    def action_test_connection(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._('只有管理员可以测试或配置用户连接。'))
        self.check_access('read')
        # Administrator deliberately tests this user's credential and scope.
        provider = self.env.ref('blue_ai_client.provider_blue_cloud').with_user(self.user_id)
        provider._get_client().test_connection()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': self.env._('连接成功'),
            'message': self.env._('已完成固定团队、指定 Agent、日常任务选择，并收到模型回复。'),
            'type': 'success',
        }}
