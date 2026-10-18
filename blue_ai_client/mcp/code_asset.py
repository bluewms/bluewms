import json

from odoo import api, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.muk_mcp.core.tool import mcp_tool

from ..guard import BINDING_TOKEN
from ..providers.knowledge import read_policy_knowledge


class BlueCodeAssetTools(models.AbstractModel):
    _inherit = 'muk_mcp.mixin'

    def _blue_asset_session(self):
        session = self._resolve_mcp_session(self.env._('请从代码资产页面打开 AI 修改。'))
        if not session.blue_profile_id:
            raise UserError(self.env._('此会话没有绑定代码资产。'))
        session._blue_check_binding()
        return session

    def _blue_lock_draft(self, session, expected_hash):
        profile = session.blue_profile_id
        profile._lock()
        if (not isinstance(expected_hash, str) or expected_hash != session.blue_draft_hash
                or expected_hash != profile._draft_hash()
                or session.blue_base_release_id != profile.active_release_id):
            raise UserError(self.env._('草稿已变化，请回到业务页面重新打开 AI 修改，避免覆盖其他修改。'))
        return profile

    @api.model
    @mcp_tool(name='blue_read_code_asset', description='读取本会话绑定的代码资产及接口契约，不接受任意记录 ID。',
              input_schema={'type': 'object', 'properties': {}, 'required': []}, category='read', registry='odoo')
    def _mcp_blue_read_code_asset(self):
        session = self._blue_asset_session()
        profile = session.blue_profile_id
        schema = self.env['blue.extension.contract']._describe(profile.contract)
        schema['instance_scope'] = profile._scope_snapshot()
        bundle, reference = read_policy_knowledge(session._blue_check_binding(), session.blue_knowledge_reference,
                                                   hook_code=profile.hook_code, contract=profile.contract)
        if profile.hook_code == 'wcs_creation' and (reference.get('hook_code') != profile.hook_code or reference.get('contract') != profile.contract):
            raise UserError(self.env._('批准知识与WCS合同不一致, 当前草稿未修改.'))
        session.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_knowledge_reference': reference})
        return {'profile_id': profile.id, 'name': profile.name, 'hook_code': profile.hook_code,
                'contract': profile.contract, 'code': profile.draft_code or '',
                'contract_schema': schema, 'contract_specification': schema, 'cloud_knowledge': bundle,
                'tests': profile.draft_tests or '', 'requirements': profile.requirements or '',
                'draft_hash': session.blue_draft_hash, 'current_draft_hash': profile._draft_hash(),
                'release_id': profile.active_release_id.id or False,
                'record_link': f'blue.config.profile,{profile.id}'}

    @api.model
    @mcp_tool(name='blue_submit_code_draft', description='提交当前代码资产的 AI 草稿。不会发布。必须传入读取时的 draft_hash。',
              input_schema={'type': 'object', 'properties': {
                  'code': {'type': 'string'}, 'tests': {'type': 'string'},
                  'requirements': {'type': 'string'}, 'expected_hash': {'type': 'string'},
              }, 'required': ['code', 'tests', 'requirements', 'expected_hash']}, category='write', registry='odoo')
    def _mcp_blue_submit_code_draft(self, code, tests, requirements, expected_hash):
        session = self._blue_asset_session()
        profile = self._blue_lock_draft(session, expected_hash)
        if not session.blue_knowledge_reference:
            raise UserError(self.env._('请先读取代码资产及本会话对应的参考上下文, 再提交草稿.'))
        result = profile.action_submit_draft(
            code, tests, requirements, expected_release_id=profile.active_release_id.id or False,
            conversation_ref=f'muk_ai.session:{session.blue_session_uuid}',
            knowledge_references=json.dumps(session.blue_knowledge_reference, ensure_ascii=False, sort_keys=True),
        )
        session.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_draft_hash': result['draft_hash']})
        return result

    @api.model
    @mcp_tool(name='blue_validate_code_draft', description='对当前草稿执行已有试算与验证，返回失败原因用于修复。不会发布。',
              input_schema={'type': 'object', 'properties': {'expected_hash': {'type': 'string'}},
                            'required': ['expected_hash']}, category='write', registry='odoo')
    def _mcp_blue_validate_code_draft(self, expected_hash):
        session = self._blue_asset_session()
        profile = self._blue_lock_draft(session, expected_hash)
        try:
            with self.env.cr.savepoint():
                profile.action_validate()
        except (ValidationError, UserError) as error:
            return {'valid': False, 'error': str(error), 'draft_hash': expected_hash}
        return {'valid': True, 'draft_hash': expected_hash, 'results': profile.simulation_result,
                'version_id': profile.validated_version_id.id, 'published': False}
