from odoo import models
from odoo.exceptions import UserError

from ..guard import BINDING_TOKEN, HOOK_TASKS


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    def _blue_ai_contracts(self):
        return {'putaway_policy': ('putaway_policy/1', 'putaway_policy/2'), 'wcs_creation': ('wcs_creation/4',)}

    def action_blue_ai_chat(self):
        self._check_manager()
        if self.hook_code not in self._blue_ai_contracts():
            raise UserError(self.env._('当前 AI 代码入口支持上架策略及WCS /4, 其他入口须先完成合同和业务验证.'))
        if self.hook_code == 'wcs_creation' and self.contract != 'wcs_creation/4':
            raise UserError(self.env._('旧WCS合同和正式版本保留. 完整AI编排请新建/4配置后试算发布, 不自动转换旧资产.'))
        if self.contract not in self._blue_ai_contracts()[self.hook_code]:
            raise UserError(self.env._('当前业务合同尚未开放 AI 生成.'))
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
            'blue_hook_code': self.hook_code,
            'blue_contract': self.contract,
            'blue_company_id': self.company_id.id,
            'blue_identity_scope': provider._get_client().identity_scope(),
        })
        return {'type': 'ir.actions.client', 'tag': 'blue_ai_client.open_code_chat', 'name': session.name,
                'params': {'session_id': session.id}}
