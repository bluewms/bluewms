import hashlib
import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .asset_guard import ASSET_TOKEN


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class BlueConfigProfile(models.Model):
    _name = 'blue.config.profile'
    _description = 'Blue policy scene'
    _check_company_auto = True

    name = fields.Char('场景名称', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    template_id = fields.Many2one('blue.scene.template', '策略接口', required=True)
    cloud_managed = fields.Boolean(related='template_id.cloud_managed')
    hook_code = fields.Selection(related='template_id.hook_code', store=True)
    contract = fields.Char(related='template_id.contract')
    requirements = fields.Text('需求说明')
    draft_code = fields.Text('可编辑策略代码')
    draft_tests = fields.Text('试算样例 JSON')
    draft_source = fields.Selection([('manual', '人工编辑'), ('example', '标准示例'), ('ai', 'AI生成')], default='manual', required=True)
    conversation_ref = fields.Char('AI会话引用')
    knowledge_references = fields.Text('云端参考版本', readonly=True, copy=False)
    draft_base_release_id = fields.Many2one('blue.config.release', '草稿基础版本', readonly=True, ondelete='restrict', check_company=True)
    validated_version_id = fields.Many2one('blue.customization.version', '已验证代码版本', readonly=True, ondelete='restrict', check_company=True)
    active_release_id = fields.Many2one('blue.config.release', '当前正式版本', readonly=True, ondelete='restrict', check_company=True)
    simulation_result = fields.Text('试算结果', readonly=True)
    state = fields.Selection([('draft', '待验证'), ('validated', '已验证'), ('published', '已发布')], compute='_compute_state')
    version_ids = fields.One2many('blue.customization.version', 'profile_id', '代码历史')
    release_ids = fields.One2many('blue.config.release', 'profile_id', '发布历史')
    event_ids = fields.One2many('blue.config.event', 'profile_id', '审计记录')

    @api.depends('draft_code', 'draft_tests', 'requirements', 'draft_source', 'conversation_ref', 'knowledge_references', 'template_id', 'validated_version_id', 'active_release_id')
    def _compute_state(self):
        for profile in self:
            valid = profile.validated_version_id and profile.validated_version_id.content_hash == profile._draft_hash()
            profile.state = 'published' if valid and profile.active_release_id.version_id == profile.validated_version_id else ('validated' if valid else 'draft')

    @api.constrains('draft_code', 'draft_tests', 'requirements', 'conversation_ref')
    def _check_draft_size(self):
        for profile in self:
            if (len(profile.draft_code or '') > 32768 or len(profile.draft_tests or '') > 262144
                    or len(profile.requirements or '') > 32768 or len(profile.conversation_ref or '') > 256):
                raise ValidationError(self.env._('Draft text exceeds the supported size.'))

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'active_release_id', 'validated_version_id', 'draft_base_release_id', 'simulation_result', 'version_ids', 'release_ids', 'event_ids', 'knowledge_references'}
        if any(protected.intersection(vals) for vals in vals_list):
            raise AccessError(self.env._('Workflow fields cannot be supplied directly.'))
        return super().create(vals_list)

    def write(self, vals):
        internal = self.env.context.get('blue_asset_token') is ASSET_TOKEN
        protected = {'active_release_id', 'validated_version_id', 'draft_base_release_id', 'simulation_result', 'version_ids', 'release_ids', 'event_ids', 'knowledge_references'}
        if protected.intersection(vals) and not internal:
            raise AccessError(self.env._('Use validation, publication or rollback to change workflow fields.'))
        if {'company_id', 'template_id'}.intersection(vals) and any(self.mapped('release_ids')):
            raise UserError(self.env._('A published scene keeps its company and template. Create another scene for a different scope.'))
        if not internal and {'draft_code', 'draft_tests', 'requirements', 'draft_source', 'conversation_ref'}.intersection(vals):
            vals = dict(vals, validated_version_id=False, simulation_result=False)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_history(self):
        if any(self.mapped('version_ids')):
            raise UserError(self.env._('Archive scenes with history instead of deleting them.'))

    def _check_manager(self):
        self.ensure_one()
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(self.env._('Only inventory managers can edit or publish policies.'))
        self.check_access('write')

    def _lock(self):
        self.ensure_one()
        self.flush_recordset()
        # Serialize publications and drafts; the ORM has no row-lock operation.
        self.env.cr.execute('SELECT id FROM blue_config_profile WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def _draft_payload(self):
        self.ensure_one()
        payload = {'contract': self.contract, 'template_id': self.template_id.id,
                'code': self.draft_code or '', 'tests': self.draft_tests or '',
                'requirements': self.requirements or '', 'source': self.draft_source,
                'conversation_ref': self.conversation_ref or ''}
        # An absent reference keeps pre-upgrade hashes and releases intact.
        if self.knowledge_references:
            payload['knowledge_references'] = self.knowledge_references
        return payload

    def _draft_hash(self):
        return digest(self._draft_payload())

    def _scope_snapshot(self):
        self.ensure_one()
        return {'company_id': self.company_id.id, 'hook_code': self.hook_code}

    def _run_tests(self):
        self.ensure_one()
        engine = self.env['blue.extension.contract']
        engine._validate_code(self.draft_code, self.contract)
        if not self.draft_tests or len(self.draft_tests) > 262144:
            raise ValidationError(self.env._('Provide bounded JSON trial cases before publication.'))
        try:
            cases = json.loads(self.draft_tests)
        except (ValueError, RecursionError) as error:
            raise ValidationError(self.env._('Trial cases must be valid JSON.')) from error
        if type(cases) is not list or not 1 <= len(cases) <= 20:
            raise ValidationError(self.env._('Provide 1 to 20 trial cases.'))
        results = []
        for case in cases:
            if type(case) is not dict or set(case) != {'name', 'input', 'expected_order'} or type(case['name']) is not str:
                raise ValidationError(self.env._('Each trial needs name, input and expected_order.'))
            result = engine._run(self.draft_code, case['input'], self.contract)
            actual = [item['location_id'] for item in result]
            if type(case['expected_order']) is not list or any(type(item) is not int for item in case['expected_order']):
                raise ValidationError(self.env._('Expected order must be a list of location IDs.'))
            if actual != case['expected_order']:
                raise ValidationError(self.env._('Trial %(name)s failed: expected %(expected)s, received %(actual)s.', name=case['name'], expected=str(case['expected_order']), actual=str(actual)))
            results.append({'name': case['name'], 'passed': True, 'result': result})
        return results

    def action_load_example(self):
        self._check_manager()
        if self.cloud_managed:
            raise UserError(self.env._('此接口的通用示例由云端维护，请使用 AI 生成 / 修改。已有正式代码仍可新建草稿。'))
        self._lock()
        self.with_context(blue_asset_token=ASSET_TOKEN).write({
            'requirements': self.template_id.requirements, 'draft_code': self.template_id.code_text,
            'draft_tests': self.template_id.test_cases, 'draft_source': 'example', 'conversation_ref': False,
            'draft_base_release_id': self.active_release_id.id, 'validated_version_id': False, 'simulation_result': False,
            'knowledge_references': False,
        })
        return True

    def action_new_draft(self):
        self._check_manager()
        self._lock()
        values = {'draft_base_release_id': self.active_release_id.id, 'validated_version_id': False, 'simulation_result': False}
        if self.active_release_id:
            version = self.active_release_id.version_id
            values.update(draft_code=version.code_text, draft_tests=version.test_cases, requirements=version.requirements,
                          draft_source='manual', conversation_ref=False, knowledge_references=version.knowledge_references)
        self.with_context(blue_asset_token=ASSET_TOKEN).write(values)
        return True

    def action_submit_draft(self, code, tests, requirements, expected_release_id=False, conversation_ref=False,
                            knowledge_references=False):
        """Future AI tool entry: submit a draft as the current authorized user."""
        self._check_manager()
        self._lock()
        if (expected_release_id is not False and type(expected_release_id) is not int) or expected_release_id != (self.active_release_id.id or False):
            raise UserError(self.env._('The active release changed. Reload before submitting a draft.'))
        if not all(type(value) is str for value in (code, tests, requirements)) or len(requirements) > 32768:
            raise ValidationError(self.env._('Draft fields must be bounded text.'))
        if conversation_ref and (type(conversation_ref) is not str or len(conversation_ref) > 256):
            raise ValidationError(self.env._('Invalid conversation reference.'))
        if knowledge_references and (type(knowledge_references) is not str or len(knowledge_references) > 16384):
            raise ValidationError(self.env._('Invalid cloud knowledge references.'))
        self.env['blue.extension.contract']._validate_code(code, self.contract)
        if len(tests) > 262144:
            raise ValidationError(self.env._('Trial input is too large.'))
        self.with_context(blue_asset_token=ASSET_TOKEN).write({
            'draft_code': code, 'draft_tests': tests, 'requirements': requirements, 'draft_source': 'ai',
            'conversation_ref': conversation_ref, 'draft_base_release_id': self.active_release_id.id,
            'validated_version_id': False, 'simulation_result': False,
            'knowledge_references': knowledge_references,
        })
        return {'profile_id': self.id, 'draft_hash': self._draft_hash(), 'state': 'draft'}

    def action_validate(self):
        self._check_manager()
        self._lock()
        results = self._run_tests()
        version = self.env['blue.customization.version'].with_context(blue_asset_token=ASSET_TOKEN).create({
            'name': self.env._('%s - validated draft', self.name), 'profile_id': self.id, 'company_id': self.company_id.id,
            'template_id': self.template_id.id, 'contract': self.contract, 'code_text': self.draft_code,
            'requirements': self.requirements, 'test_cases': self.draft_tests, 'test_result': canonical(results),
            'content_hash': self._draft_hash(), 'source': self.draft_source, 'conversation_ref': self.conversation_ref,
            'base_release_id': self.draft_base_release_id.id,
            'knowledge_references': self.knowledge_references,
        })
        self.with_context(blue_asset_token=ASSET_TOKEN).write({'validated_version_id': version.id, 'simulation_result': json.dumps(results, ensure_ascii=False, indent=2)})
        self._record_event('validated', details=version.content_hash)
        return True

    def action_publish(self):
        self._check_manager()
        self._lock()
        version = self.validated_version_id
        if not self.active:
            raise UserError(self.env._('Activate the scene before publishing.'))
        if not version or version.content_hash != self._draft_hash():
            raise UserError(self.env._('Validate the current draft before publishing.'))
        if version.base_release_id != self.active_release_id:
            raise UserError(self.env._('The base release changed. Start a new draft before publishing.'))
        self._run_tests()
        snapshot = {'scope': self._scope_snapshot(), 'contracts': {self.hook_code: {
            'version_id': version.id, 'contract': version.contract, 'code': version.code_text,
            'content_hash': version.content_hash, 'tests': version.test_cases,
            'knowledge_references': version.knowledge_references,
        }}}
        release = self.env['blue.config.release'].with_context(blue_asset_token=ASSET_TOKEN).create({
            'name': self.env._('%s - release', self.name), 'profile_id': self.id, 'company_id': self.company_id.id,
            'version_id': version.id, 'previous_release_id': self.active_release_id.id,
            'snapshot': canonical(snapshot), 'content_hash': digest(snapshot),
        })
        self.with_context(blue_asset_token=ASSET_TOKEN).write({'active_release_id': release.id})
        self._record_event('published', release)
        return True

    def action_rollback(self):
        self._check_manager()
        self._lock()
        current = self.active_release_id
        if not current or not current.previous_release_id:
            raise UserError(self.env._('There is no previous release to restore.'))
        previous = current.previous_release_id
        self.with_context(blue_asset_token=ASSET_TOKEN).write({'active_release_id': previous.id, 'validated_version_id': False,
                                                           'draft_base_release_id': previous.id, 'simulation_result': False})
        self._record_event('rollback', previous, details=self.env._('Restored from release %s.', current.id))
        return True

    def _record_event(self, event_type, release=None, details=None):
        self.env['blue.config.event'].with_context(blue_asset_token=ASSET_TOKEN).create({
            'profile_id': self.id, 'company_id': self.company_id.id, 'release_id': release.id if release else False,
            'event_type': event_type, 'details': details,
        })
