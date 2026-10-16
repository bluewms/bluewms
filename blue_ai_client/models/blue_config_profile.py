from odoo import models
from odoo.exceptions import UserError

from ..guard import BINDING_TOKEN, HOOK_TASKS


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    def action_blue_ai_chat(self):
        self._check_manager()
        if self.hook_code != 'putaway_policy':
            raise UserError(self.env._('当前 AI 代码入口仅开放上架策略，其他入口须先完成合同和业务验证。'))
        provider = self.env.ref('blue_ai_client.provider_blue_cloud')
        if not provider.active or not provider._can_serve():
            raise UserError(self.env._('请先启用宝蓝云端服务，并配置当前用户的连接。'))
        provider = provider.with_context(blue_ai_task_name=HOOK_TASKS[self.hook_code],
                                         blue_ai_contract=self.contract,
                                         allowed_company_ids=[self.company_id.id])
        session = self.env['muk_ai.session'].with_context(blue_ai_binding_token=BINDING_TOKEN).create({
            'name': self.env._('AI 修改：%s', self.name),
            'agent_id': self.env.ref('blue_ai_client.agent_blue_code').id,
            'view_context': {'kind': 'record', 'model': self._name, 'id': self.id, 'display_name': self.name},
            'blue_profile_id': self.id,
            'blue_draft_hash': self._draft_hash(),
            'blue_base_release_id': self.active_release_id.id,
            'blue_task_name': HOOK_TASKS[self.hook_code],
            'blue_contract': self.contract,
            'blue_company_id': self.company_id.id,
            'blue_identity_scope': provider._get_client().identity_scope(),
        })
        return {'type': 'ir.actions.client', 'tag': 'blue_ai_client.open_code_chat', 'name': session.name,
                'params': {'session_id': session.id}}
