import uuid

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from ..guard import (
    BINDING_TOKEN, CODE_TOOLS, HOOK_TASKS, KNOWLEDGE_TOOLS, REQUIRED_GUIDANCE,
    REVIEW_APPROVE, REVIEW_QUESTION_PREFIX, TASK_NAME,
)


BINDING_FIELDS = {
    'blue_session_uuid', 'blue_profile_id', 'blue_draft_hash', 'blue_base_release_id',
    'blue_task_name', 'blue_contract', 'blue_company_id', 'blue_identity_scope', 'blue_knowledge_reference',
    'blue_hook_code', 'blue_knowledge_search_results', 'blue_asset_read', 'blue_cloud_identity',
    'blue_requirements_review',
}


class AISession(models.Model):
    _inherit = 'muk_ai.session'

    blue_session_uuid = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, copy=False)
    blue_profile_id = fields.Many2one('blue.config.profile', string='代码资产', readonly=True,
                                    ondelete='set null', copy=False)
    blue_draft_hash = fields.Char(readonly=True, copy=False)
    blue_base_release_id = fields.Many2one('blue.config.release', readonly=True, copy=False, ondelete='restrict')
    blue_task_name = fields.Char('云端业务任务', readonly=True, copy=False)
    blue_contract = fields.Char(readonly=True, copy=False)
    blue_company_id = fields.Many2one('res.company', readonly=True, copy=False, ondelete='restrict')
    blue_identity_scope = fields.Char(readonly=True, copy=False)
    blue_knowledge_reference = fields.Json('云端知识版本', readonly=True, copy=False)
    blue_hook_code = fields.Selection(list(HOOK_TASKS.items()), string='业务入口', readonly=True, copy=False)
    blue_knowledge_search_results = fields.Json(readonly=True, copy=False)
    blue_asset_read = fields.Boolean(readonly=True, copy=False)
    blue_cloud_identity = fields.Json('实际云端 Task 绑定', readonly=True, copy=False)
    blue_requirements_review = fields.Json('本次需求确认', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_ai_binding_token') is not BINDING_TOKEN:
            if any(BINDING_FIELDS.intersection(vals) for vals in vals_list):
                raise AccessError(self.env._('代码资产关联只能通过业务页面创建。'))
        return super().create(vals_list)

    def write(self, vals):
        if (BINDING_FIELDS.intersection(vals)
                and self.env.context.get('blue_ai_binding_token') is not BINDING_TOKEN):
            raise AccessError(self.env._('不能直接修改云端会话与代码资产关联。'))
        return super().write(vals)

    def _get_filtered_catalog(self):
        catalog = super()._get_filtered_catalog()
        if self.blue_profile_id or self.blue_hook_code:
            allowed = KNOWLEDGE_TOOLS | (CODE_TOOLS if self.blue_profile_id else set())
            return [entry for entry in catalog if entry['name'] in allowed]
        return catalog

    def _enqueue_user_turn(self, user_message, attachments, extend=True):
        if self.blue_profile_id and self.blue_requirements_review:
            self._blue_check_binding()
            self.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_requirements_review': False})
        return super()._enqueue_user_turn(user_message, attachments, extend=extend)

    def _register_ask_user(self, call):
        question = (call.get('arguments') or {}).get('question') or ''
        if self.blue_profile_id and isinstance(question, str) and question.startswith(REVIEW_QUESTION_PREFIX):
            self._blue_check_binding()
            requirements = question[len(REVIEW_QUESTION_PREFIX):].strip()
            pages = {(p.get('scope'), p.get('ref'))
                     for p in (self.blue_knowledge_reference or {}).get('pages', [])}
            references = self.blue_knowledge_reference or {}
            scopes = [book['scope'] for book in references.get('catalog', []) if book['scope'] != 'common']
            roles = {(p.get('scope'), p.get('role')) for p in references.get('pages', [])}
            if not self.blue_asset_read or not {('common', ref) for ref in REQUIRED_GUIDANCE}.issubset(pages):
                raise UserError(self.env._('请先读资产和两份通用必读页,再提交需求确认.'))
            if len(scopes) != 1 or not {(scopes[0], 'specification'), (scopes[0], 'example')}.issubset(roles):
                raise UserError(self.env._('请先完整读取本领域规范和匹配案例,再提交需求确认.'))
            if not 20 <= len(requirements) <= 8192 or '```' in requirements:
                raise UserError(self.env._('需求确认请提供20至8192字符的具体业务摘要,不要附带代码.'))
            self.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_requirements_review': {
                'status': 'pending', 'question': question, 'requirements': requirements,
                'draft_hash': self.blue_draft_hash, 'call_id': call['call_id'],
            }})
        return super()._register_ask_user(call)

    def answer(self, answer, attachment_ids=None):
        review = self.blue_requirements_review or {}
        pending = self.pending_ask or {}
        if self.blue_profile_id and review and self.state == 'waiting' and pending.get('kind') == 'question':
            self._blue_check_binding()
            matches = (self.state == 'waiting' and pending.get('kind') == 'question'
                       and pending.get('text') == review.get('question')
                       and pending.get('call_id') == review.get('call_id'))
            if matches and review.get('status') == 'pending':
                text = answer.strip().rstrip('.!。！').lower() if isinstance(answer, str) else ''
                approved = text in {REVIEW_APPROVE, '确认', '确认生成草稿', '确认以上需求', '同意', '可以', '按这个方案生成', 'yes'}
                self.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_requirements_review': {
                    **review, 'status': 'confirmed' if approved else 'changes_requested',
                    'confirmed_by': self.env.uid if approved else False,
                }})
            elif review.get('status') == 'confirmed':
                self.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_requirements_review': False})
        return super().answer(answer, attachment_ids=attachment_ids)

    def _dispatch_tool_call(self, name, arguments, call_id):
        allowed = KNOWLEDGE_TOOLS | (CODE_TOOLS if self.blue_profile_id else set()) | {'tool_load'}
        if (self.blue_profile_id or self.blue_hook_code) and name not in allowed:
            return {'error': self.env._('代码会话只允许专用草稿工具。')}, False
        return super()._dispatch_tool_call(name, arguments, call_id)

    def _resolve_provider(self):
        provider = super()._resolve_provider()
        if (self.blue_profile_id or self.blue_hook_code) and provider.name != 'blue_cloud':
            raise UserError(self.env._('业务会话必须使用宝蓝云端,请从原业务入口重新打开.'))
        if provider.name == 'blue_cloud':
            if self.blue_profile_id and not self.blue_hook_code:
                raise UserError(self.env._('旧代码会话保留为历史,请从资产页面重新打开 AI,使用对应业务 Task 与原生 Wiki.'))
            if self.blue_hook_code and self.blue_task_name != HOOK_TASKS[self.blue_hook_code]:
                raise UserError(self.env._('业务入口与云端 Task 不匹配,请重新打开会话.'))
            provider = provider.with_context(
                blue_ai_session_uuid=self.blue_session_uuid,
                blue_ai_task_name=self.blue_task_name or TASK_NAME,
                blue_ai_contract=self.blue_contract or '',
                allowed_company_ids=[self.blue_company_id.id] if self.blue_company_id else self.env.companies.ids,
            )
            if self.blue_identity_scope and provider._get_client().identity_scope() != self.blue_identity_scope:
                raise UserError(self.env._('云端身份已改变，请从代码资产页面重新打开 AI 修改。'))
        return provider

    def _blue_check_binding(self):
        self.ensure_one()
        self.check_access('write')
        if self.user_id != self.env.user:
            raise AccessError(self.env._('只有会话所有者可以使用业务知识和草稿工具.'))
        profile = self.blue_profile_id
        if profile:
            profile._check_manager()
        if profile and (profile.contract != self.blue_contract or profile.company_id != self.blue_company_id
                        or profile.hook_code != self.blue_hook_code):
            raise UserError(self.env._('资产接口或公司已改变，请重新打开 AI 修改。'))
        reference = self.blue_knowledge_reference
        if reference and (reference.get('source') != 'tencent_wiki'
                          or reference.get('hook_code') != self.blue_hook_code
                          or reference.get('contract') != (self.blue_contract or '')):
            raise UserError(self.env._('知识引用方式已升级,请从业务页面重新打开AI会话.'))
        provider = self._resolve_provider()
        if provider.name != 'blue_cloud' or not provider.active:
            raise UserError(self.env._('代码会话必须使用宝蓝云端连接。'))
        return provider._get_client()

    def _blue_pin_cloud_identity(self, identity):
        self.ensure_one()
        self.check_access('write')
        if self.user_id != self.env.user or identity.get('task_name') != self.blue_task_name:
            raise AccessError(self.env._('云端 Task 身份与本会话不一致.'))
        if self.blue_cloud_identity and self.blue_cloud_identity != identity:
            raise UserError(self.env._('云端用户,Agent 或 Task 已变化,请重新打开会话.'))
        self.with_context(blue_ai_binding_token=BINDING_TOKEN).write({'blue_cloud_identity': identity})

    def _system_prompt_addenda(self):
        if self.blue_hook_code:
            instructions = self.env._(
                '当前入口为 %s,云端 Task 为 %s.知识使用腾讯原生 Wiki,不能调用旧 Skill,Bash,curl 或文件工具.'
                '资产会话先 blue_read_code_asset 读取真实合同和已有需求,然后 blue_search_code_knowledge 搜索,'
                '再 blue_read_code_knowledge 读取搜索结果的 page_ref.'
                '搜索摘要不算读过正文.提交前必须完整读取通用生成规则,本领域规范及至少一个匹配案例.'
                '必须完整读 basics/ai-generation-workflow.md 和 basics/requirements-clarification.md,'
                '分别检索"生成步骤 工具规则"和"五类 需求澄清";本领域规范检索 specification 或业务字段.'
                '只能使用当前入口的实际工具;没有正文,批准失效,合同不匹配或版本漂移时报告错误,不回退旧示例.'
                '对照五类入口澄清规则区分已有事实,待核实事实,待决业务选择和本机能力缺口.'
                '未知厂家,协议,实际字段和单位先核实资料,不能把已有案例推荐成现场事实.'
                '已有代码和AI生成的需求文字只说明已有实现,不等于用户已确认本次未决选择;提问也不能偷设默认答案.'
                '凡相关关键选择未明确,先 ask_user 并结束本轮等待真实回答,不先写代码或保存猜测草稿.'
                '每轮集中问1-3个相关问题,已明确或工具可读取的信息不重复询问;信息完整时直接整理摘要供确认.'
                '开始生成前仍须一次真实需求摘要确认:按 blue_read_code_asset 返回的 requirements_review 协议,'
                '用 ask_user 展示具体业务摘要并等待确认.不能自己宣称用户已确认.'
                '确认后提交的 requirements 必须与获确认摘要逐字相同;同需求自动修复不重复确认.'
                '不要在同一模型响应同时调用 ask_user 与业务工具.固定执行器未支持的行为必须说明限制,不能假装已实现.',
                HOOK_TASKS[self.blue_hook_code], self.blue_task_name)
            if not self.blue_profile_id:
                return [instructions, self.env._(
                    '本会话仅用于本领域知识沟通,不绑定代码资产,不得生成或提交可执行草稿.'
                    '五类入口的可执行修改均须从对应业务资产页打开,本知识会话只讨论需求和能力.')]
            return [instructions, self.env._(
                '本会话仅可修改绑定资产 ID %s.必须先 blue_read_code_asset 读取真实代码,完整 contract_schema,'
                '测试与 draft_hash;该工具只返回知识范围,正文须另外搜索,读取.'
                '按当前合同写完整增强代码及本次测试,保存草稿后 blue_validate_code_draft 验证,由用户人工发布.'
                '系统权限,原生上架优先级,容量,托盘和冻结不放宽;WCS /4 区分 lines/tasks,逐行 create/wait/exclude,'
                'repeat/relay 后续 goods 等上一 goods end,计划数量与库存只记一次;人工设备和任务类型不改.'
                '代码无 ORM,网络,文件,设备执行或发布权限.', self.blue_profile_id.id)]
        if self.blue_profile_id:
            return [self.env._('旧代码会话仅保留历史,请从资产页面重新打开原生 Wiki 会话.')]
        return super()._system_prompt_addenda()

    def _system_message(self):
        if not self.blue_profile_id and not self.blue_hook_code:
            return super()._system_message()
        # The generic MuK file/Skill blocks advertise tools unavailable here.
        parts = [self._effective_system_prompt(), self._build_available_tools_block(),
                 *self._system_prompt_addenda(), self._build_runtime_block()]
        return {'role': 'system', 'content': [{'type': 'input_text', 'text': '\n\n'.join(filter(None, parts))}]}

    @api.model
    def action_blue_business_chat(self, hook_code):
        if not isinstance(hook_code, str) or hook_code not in HOOK_TASKS:
            raise UserError(self.env._('未知宝蓝 AI 业务入口.'))
        provider = self.env.ref('blue_ai_client.provider_blue_cloud')
        if not provider.active or not provider._can_serve():
            raise UserError(self.env._('请先启用宝蓝云端服务并配置当前用户连接.'))
        provider = provider.with_context(blue_ai_task_name=HOOK_TASKS[hook_code], blue_ai_contract='')
        session = self.with_context(blue_ai_binding_token=BINDING_TOKEN).create({
            'name': self.env._('AI 知识:%s', HOOK_TASKS[hook_code]),
            'agent_id': self.env.ref('blue_ai_client.agent_blue_code').id,
            'blue_hook_code': hook_code, 'blue_task_name': HOOK_TASKS[hook_code],
            'blue_company_id': self.env.company.id,
            'blue_identity_scope': provider._get_client().identity_scope(),
        })
        return {'type': 'ir.actions.client', 'tag': 'blue_ai_client.open_code_chat', 'name': session.name,
                'params': {'session_id': session.id}}
