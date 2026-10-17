import uuid

from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..guard import BINDING_TOKEN


class AISession(models.Model):
    _inherit = 'muk_ai.session'

    blue_session_uuid = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, copy=False)
    blue_profile_id = fields.Many2one('blue.config.profile', string='代码资产', readonly=True,
                                    ondelete='set null', copy=False)
    blue_draft_hash = fields.Char(readonly=True, copy=False)
    blue_base_release_id = fields.Many2one('blue.config.release', readonly=True, copy=False, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'blue_session_uuid', 'blue_profile_id', 'blue_draft_hash', 'blue_base_release_id'}
        if self.env.context.get('blue_ai_binding_token') is not BINDING_TOKEN:
            if any(protected.intersection(vals) for vals in vals_list):
                raise AccessError(self.env._('代码资产关联只能通过业务页面创建。'))
        return super().create(vals_list)

    def write(self, vals):
        if ({'blue_session_uuid', 'blue_profile_id', 'blue_draft_hash', 'blue_base_release_id'}.intersection(vals)
                and self.env.context.get('blue_ai_binding_token') is not BINDING_TOKEN):
            raise AccessError(self.env._('不能直接修改云端会话与代码资产关联。'))
        return super().write(vals)

    def _get_filtered_catalog(self):
        catalog = super()._get_filtered_catalog()
        if self.blue_profile_id:
            allowed = {'blue_read_code_asset', 'blue_submit_code_draft', 'blue_validate_code_draft', 'ask_user'}
            return [entry for entry in catalog if entry['name'] in allowed]
        return catalog

    def _dispatch_tool_call(self, name, arguments, call_id):
        if self.blue_profile_id and name not in {
            'blue_read_code_asset', 'blue_submit_code_draft', 'blue_validate_code_draft', 'ask_user', 'tool_load',
        }:
            return {'error': self.env._('代码会话只允许专用草稿工具。')}, False
        return super()._dispatch_tool_call(name, arguments, call_id)

    def _resolve_provider(self):
        provider = super()._resolve_provider()
        if provider.name == 'blue_cloud':
            provider = provider.with_context(blue_ai_session_uuid=self.blue_session_uuid)
        return provider

    def _system_prompt_addenda(self):
        blocks = super()._system_prompt_addenda()
        if self.blue_profile_id:
            blocks.append(self.env._(
                '本会话仅允许修改代码资产 ID %s。先调用 blue_read_code_asset 获取实际代码、'
                '接口契约和基础摘要。业务知识与技能由云端提供。本地仅保存草稿和验证，'
                '发布由用户操作。', self.blue_profile_id.id
            ))
        return blocks
