import hashlib
import json

from odoo import api, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.muk_mcp.core.tool import mcp_tool

from ..guard import BINDING_TOKEN, REQUIRED_GUIDANCE
from ..providers.knowledge import MAX_PAGES, MAX_TOTAL, NativeWiki


class BlueCodeAssetTools(models.AbstractModel):
    _inherit = 'muk_mcp.mixin'

    def _blue_asset_session(self):
        session = self._resolve_mcp_session(self.env._('请从代码资产页面打开 AI 修改。'))
        if not session.blue_profile_id:
            raise UserError(self.env._('此会话没有绑定代码资产。'))
        session._blue_check_binding()
        return session

    def _blue_knowledge_session(self):
        session = self._resolve_mcp_session(self.env._('请从宝蓝业务入口打开 AI 会话.'))
        if not session.blue_hook_code:
            raise UserError(self.env._('请重新从业务入口打开原生 Wiki 会话.'))
        session._blue_check_binding()
        return session

    def _blue_wiki(self, session):
        return NativeWiki(session._blue_check_binding(), session.blue_hook_code,
                          session.blue_contract, session.blue_knowledge_reference)

    def _blue_wiki_context(self, session):
        reference = self._blue_wiki(session).context()
        session.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_knowledge_reference': reference})
        return reference

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
        knowledge = self._blue_wiki_context(session)
        session.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_asset_read': True})
        return {'profile_id': profile.id, 'name': profile.name, 'hook_code': profile.hook_code,
                'contract': profile.contract, 'code': profile.draft_code or '',
                'contract_schema': schema, 'contract_specification': schema,
                'cloud_knowledge': knowledge,
                'required_guidance': list(REQUIRED_GUIDANCE),
                'tests': profile.draft_tests or '', 'requirements': profile.requirements or '',
                'draft_source': profile.draft_source,
                'draft_hash': session.blue_draft_hash, 'current_draft_hash': profile._draft_hash(),
                'release_id': profile.active_release_id.id or False,
                'record_link': f'blue.config.profile,{profile.id}'}

    @api.model
    @mcp_tool(name='blue_search_code_knowledge', description='通过腾讯原生 Wiki 搜索当前入口与通用规则.摘要不是正文,之后必须完整读页.',
              input_schema={'type': 'object', 'properties': {'query': {'type': 'string'}},
                            'required': ['query'], 'additionalProperties': False}, category='read', registry='odoo')
    def _mcp_blue_search_code_knowledge(self, query):
        session = self._blue_knowledge_session()
        if not session.blue_knowledge_reference:
            self._blue_wiki_context(session)
        hits = self._blue_wiki(session).search(query)
        known = dict(session.blue_knowledge_search_results or {})
        results = []
        for hit in hits:
            page = {'scope': hit['scope'], 'ref': hit['ref']}
            ref = hashlib.sha256((session.blue_session_uuid + json.dumps(page, sort_keys=True)).encode()).hexdigest()[:24]
            known[ref] = page
            results.append({'page_ref': ref, 'title': hit['title'], 'scope': hit['scope'], 'snippet': hit['snippet']})
        if len(known) > 80:
            raise UserError(self.env._('本会话检索页数过多,请缩小需求或重新打开会话.'))
        session.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_knowledge_search_results': known})
        return {'results': results, 'task_name': session.blue_task_name,
                'required_guidance': list(REQUIRED_GUIDANCE),
                'instruction': 'Read the generation workflow, five-domain requirements clarification, domain specification and a relevant example in full. Ask and wait for unresolved business choices before writing code.'}

    @api.model
    @mcp_tool(name='blue_read_code_knowledge', description='读取本会话搜索返回的页面全文并固定批准来源,版本及摘要.',
              input_schema={'type': 'object', 'properties': {'page_ref': {'type': 'string'}},
                            'required': ['page_ref'], 'additionalProperties': False}, category='read', registry='odoo')
    def _mcp_blue_read_code_knowledge(self, page_ref):
        session = self._blue_knowledge_session()
        page = (session.blue_knowledge_search_results or {}).get(page_ref) if isinstance(page_ref, str) else None
        if not page:
            raise UserError(self.env._('请先在本会话搜索知识,不能读取任意页面或其他会话的引用.'))
        body, reference = self._blue_wiki(session).read(page)
        reference = {**reference, 'bytes': len(body.encode())}
        frozen = dict(session.blue_knowledge_reference)
        pages = list(frozen['pages'])
        previous = next((p for p in pages if (p['scope'], p['ref']) == (reference['scope'], reference['ref'])), None)
        if previous and previous != reference:
            raise UserError(self.env._('已读知识正文发生变化,请重新打开会话.'))
        if not previous:
            pages.append(reference)
        if len(pages) > MAX_PAGES or sum(p['bytes'] for p in pages) > MAX_TOTAL:
            raise UserError(self.env._('已读知识超过会话预算,请选择较少的完整案例.'))
        frozen['pages'] = pages
        session.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_knowledge_reference': frozen})
        return {'content': body, 'reference': reference, 'published': False}

    @api.model
    @mcp_tool(name='blue_submit_code_draft', description='提交当前代码资产的 AI 草稿。不会发布。必须传入读取时的 draft_hash。',
              input_schema={'type': 'object', 'properties': {
                  'code': {'type': 'string'}, 'tests': {'type': 'string'},
                  'requirements': {'type': 'string'}, 'expected_hash': {'type': 'string'},
              }, 'required': ['code', 'tests', 'requirements', 'expected_hash']}, category='write', registry='odoo')
    def _mcp_blue_submit_code_draft(self, code, tests, requirements, expected_hash):
        session = self._blue_asset_session()
        profile = self._blue_lock_draft(session, expected_hash)
        if not session.blue_asset_read:
            raise UserError(self.env._('请先读取当前绑定资产与本地合同,再提交草稿.'))
        self._blue_wiki(session).verify()
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
        self._blue_wiki(session).verify()
        try:
            with self.env.cr.savepoint():
                profile.action_validate()
        except (ValidationError, UserError) as error:
            return {'valid': False, 'error': str(error), 'draft_hash': expected_hash}
        return {'valid': True, 'draft_hash': expected_hash, 'results': profile.simulation_result,
                'version_id': profile.validated_version_id.id, 'published': False}
