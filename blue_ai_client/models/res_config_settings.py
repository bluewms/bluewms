from odoo import api, fields, models
from odoo.exceptions import AccessError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    blue_provider_id = fields.Many2one('muk_ai.provider', compute='_compute_blue_connections',
                                      groups='base.group_system')
    blue_connection_id = fields.Many2one('blue.ai.connection', compute='_compute_blue_connections',
                                        groups='base.group_system')
    blue_cloud_enabled = fields.Boolean(related='blue_provider_id.active', readonly=False,
                                        groups='base.group_system')
    blue_cloud_url = fields.Char(related='blue_provider_id.api_url', readonly=False,
                                groups='base.group_system')
    blue_cloud_model = fields.Char(related='blue_provider_id.default_chat_model_id.technical_name',
                                  readonly=False, groups='base.group_system')
    blue_agent_name = fields.Char(related='blue_connection_id.agent_name', readonly=False,
                                 groups='base.group_system')
    blue_user_key = fields.Char(related='blue_connection_id.api_key', readonly=False,
                               groups='base.group_system')
    blue_team_name = fields.Char(related='blue_connection_id.team_name', groups='base.group_system')
    blue_task_name = fields.Char(related='blue_connection_id.task_name', groups='base.group_system')

    @api.depends_context('uid')
    def _compute_blue_connections(self):
        provider = self.env.ref('blue_ai_client.provider_blue_cloud', raise_if_not_found=False)
        connection = self.env['blue.ai.connection'].search([('user_id', '=', self.env.uid)], limit=1)
        for settings in self:
            settings.blue_provider_id = provider
            settings.blue_connection_id = connection

    def action_blue_test_connection(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._('只有管理员可以修改云端配置。'))
        self.set_values()
        return self.blue_connection_id.action_test_connection()

    def action_blue_manage_connections(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._('只有管理员可以管理用户连接。'))
        return self.env['ir.actions.actions']._for_xml_id('blue_ai_client.blue_ai_connection_action')
