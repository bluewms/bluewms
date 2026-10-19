import json
import re
from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools.protocol import ProtocolError, bounded
from .guard import PROTOCOL_TOKEN


CONNECTION_FIELDS = {'adapter_code', 'company_id', 'ip_post', 'submit_path', 'app_key', 'app_secret', 'callback_token',
    'protocol_auth_mode', 'protocol_key_header', 'protocol_secret_header', 'protocol_callback_mode',
    'protocol_task_key', 'protocol_tusk_compat', 'protocol_allow_subposition', 'protocol_allow_destination',
    'protocol_destination_root_id', 'protocol_profile_id', 'protocol_parameters'}


class WcsEquipmentCategory(models.Model):
    _inherit = 'wcs.equipment.category'

    adapter_code = fields.Selection(string='接口执行方式', selection_add=[('protocol', '可编辑 HTTP 接口')],
                                     ondelete={'protocol': 'set default'}, default='protocol')
    submit_path = fields.Char(default=False)
    protocol_profile_id = fields.Many2one('blue.config.profile', '接口代码资产', readonly=True,
                                          copy=False, check_company=True, ondelete='restrict')
    protocol_auth_mode = fields.Selection([('auto', '根据连接凭据自动选择'), ('none', '不附加认证'), ('bearer', 'Bearer Token'),
                                           ('headers', '厂商认证请求头')], string='下发认证', default='auto', required=True,
                                           groups='base.group_system')
    protocol_key_header = fields.Char('App Key 请求头名称', default='X-App-Key', groups='base.group_system')
    protocol_secret_header = fields.Char('App Secret 请求头名称', default='X-App-Secret', groups='base.group_system')
    protocol_callback_mode = fields.Selection([('auto', '根据回调凭据自动选择'), ('legacy', '旧版兼容,不附加 Token'), ('bearer', 'Bearer Token')],
        string='回调接入方式', default='auto', required=True, groups='base.group_system')
    protocol_task_key = fields.Char('回调任务号字段', default='taskId', required=True, groups='base.group_system')
    protocol_tusk_compat = fields.Boolean('启用旧 TUSK 回调地址', groups='base.group_system')
    protocol_parameters = fields.Json('厂商业务参数(非密钥)', default=dict, groups='base.group_system',
                                      help='仓库编码等固定参数. 真实密钥仍填写 App Key / Secret 等专用字段.')
    protocol_allow_subposition = fields.Boolean('允许回写包裹子位置', default=True, groups='base.group_system')
    protocol_allow_destination = fields.Boolean('允许回调确定库存目的库位', groups='base.group_system')
    protocol_destination_root_id = fields.Many2one('stock.location', '允许目的库区', check_company=True,
                                                    groups='base.group_system')
    protocol_code = fields.Text(related='protocol_profile_id.draft_code', readonly=False, related_sudo=False)
    protocol_tests = fields.Text(related='protocol_profile_id.draft_tests', readonly=False, related_sudo=False)
    protocol_requirements = fields.Text(related='protocol_profile_id.requirements', readonly=False, related_sudo=False)
    protocol_state = fields.Selection(related='protocol_profile_id.state', related_sudo=False)
    protocol_result = fields.Text(related='protocol_profile_id.simulation_result', related_sudo=False)
    protocol_release_id = fields.Many2one(related='protocol_profile_id.active_release_id', related_sudo=False)

    protocol_draft_source = fields.Selection(related='protocol_profile_id.draft_source', readonly=False, related_sudo=False)
    protocol_conversation_ref = fields.Char(related='protocol_profile_id.conversation_ref', readonly=False, related_sudo=False)
    protocol_knowledge_references = fields.Text(related='protocol_profile_id.knowledge_references', related_sudo=False)
    protocol_version_ids = fields.One2many(related='protocol_profile_id.version_ids', related_sudo=False)
    protocol_release_ids = fields.One2many(related='protocol_profile_id.release_ids', related_sudo=False)
    protocol_event_ids = fields.One2many(related='protocol_profile_id.event_ids', related_sudo=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any('protocol_profile_id' in vals for vals in vals_list):
            raise AccessError(self.env._('接口代码资产由类别自动关联,不能指定其他资产.'))
        categories = super().create(vals_list)
        categories._protocol_ensure_profiles()
        return categories

    def write(self, vals):
        self.check_access('write')
        if 'protocol_profile_id' in vals and self.env.context.get('blue_protocol_token') is not PROTOCOL_TOKEN:
            raise AccessError(self.env._('接口代码资产不能直接更换.'))
        if CONNECTION_FIELDS.intersection(vals):
            tasks = self.env['wcs.request'].sudo().search([
                ('protocol_category_id', 'in', self.ids), ('state', 'not in', ['completed', 'cancelled'])], limit=1)
            # Fixed category/task lookup only; do not reveal task or connection data.
            if tasks:
                raise UserError(self.env._('类别存在未结束设备任务,请先完成或核对后再修改连接及回写范围.'))
        result = super().write(vals)
        if 'adapter_code' in vals:
            self._protocol_ensure_profiles()
        return result

    def _protocol_ensure_profiles(self):
        for category in self.filtered(lambda item: item.adapter_code == 'protocol' and not item.protocol_profile_id):
            profile = self.env['blue.config.profile'].with_context(blue_protocol_token=PROTOCOL_TOKEN).create({
                'name': self.env._('%s - 设备接口', category.name), 'company_id': category.company_id.id,
                'template_id': self.env.ref('blue_wcs_protocol.blue_scene_template_device_protocol').id,
                'device_category_id': category.id})
            category.with_context(blue_protocol_token=PROTOCOL_TOKEN).write({'protocol_profile_id': profile.id})

    def unlink(self):
        self.check_access('unlink')
        profiles = self.protocol_profile_id
        if profiles.version_ids:
            raise UserError(self.env._('设备类别已有协议版本,请保留历史记录.'))
        self.with_context(blue_protocol_token=PROTOCOL_TOKEN).write({'protocol_profile_id': False})
        profiles.unlink()
        return super().unlink()

    def _protocol_scope(self, legacy=False):
        self.ensure_one()
        category = self.sudo()
        if legacy:
            # Historical releases retain their original manually approved boundary.
            return {'category_id': category.id, 'submit_path': category.submit_path or '',
                    'callback_task_key': category.protocol_task_key, 'legacy_tusk_callback': category.protocol_tusk_compat,
                    'allow_subposition': category.protocol_allow_subposition,
                    'allow_destination': category.protocol_allow_destination,
                    'destination_root_id': category.protocol_destination_root_id.id or False,
                    'callback_mode': category.protocol_callback_mode, 'parameters': category.protocol_parameters or {}}
        return {'category_id': category.id, 'submit_path': category.submit_path or '',
                'interface_mode': 'http_json', 'parameters': category.protocol_parameters or {}}

    def _protocol_scope_matches(self, scope):
        return scope == self._protocol_scope(legacy=scope.get('interface_mode') != 'http_json')

    def _protocol_release_scope_matches(self, scope):
        expected = self.protocol_profile_id._scope_snapshot()
        expected['device_scope'] = self._protocol_scope(legacy=scope['device_scope'].get('interface_mode') != 'http_json')
        return scope == expected

    @api.constrains('adapter_code', 'ip_post', 'protocol_task_key', 'protocol_key_header',
                    'protocol_secret_header', 'protocol_tusk_compat', 'protocol_allow_destination',
                    'protocol_destination_root_id', 'protocol_parameters')
    def _check_protocol_fields(self):
        for category in self.filtered(lambda item: item.adapter_code == 'protocol'):
            config = category.sudo()
            try:
                bounded(config.protocol_parameters or {})
            except ProtocolError as error:
                raise ValidationError(self.env._('厂商业务参数必须是有界 JSON 对象.')) from error
            if type(config.protocol_parameters or {}) is not dict:
                raise ValidationError(self.env._('厂商业务参数必须是 JSON 对象.'))
            if any(re.search(r'(secret|password|token|credential|api.?key)', key, re.I) for key in (config.protocol_parameters or {})):
                raise ValidationError(self.env._('认证信息请使用专用密钥字段,不能放入发送给 AI 的业务参数.'))
            if config.ip_post:
                url = urlsplit(config.ip_post)
                if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ValidationError(self.env._('请输入不含凭据和查询参数的 HTTP(S) 设备地址.'))
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', config.protocol_task_key or ''):
                raise ValidationError(self.env._('回调任务号字段必须是单个 JSON 字段名称.'))
            for header in (config.protocol_key_header, config.protocol_secret_header):
                if header and (not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,63}', header)
                               or header.lower() in ('host', 'content-length', 'connection', 'transfer-encoding')):
                    raise ValidationError(self.env._('厂商认证请求头名称无效.'))
            if config.protocol_destination_root_id and config.protocol_destination_root_id.company_id != category.company_id:
                raise ValidationError(self.env._('目的库区必须属于当前公司.'))

    def _protocol_check_configuration(self):
        self.ensure_one()
        self.check_access('read')
        config = self.sudo()  # Only fixed connection fields, never returned to the AI.
        if config.adapter_code != 'protocol' or not config.ip_post or not config.submit_path:
            raise UserError(self.env._('请人工填写 HTTP(S) 设备地址及任务接口路径.'))

    def _protocol_release(self):
        self.ensure_one()
        self._protocol_check_configuration()
        profile = self.protocol_profile_id
        release = profile.active_release_id
        if not profile.active or not release or not self._protocol_release_scope_matches(json.loads(release.snapshot)['scope']):
            raise UserError(self.env._('请先验证并发布与当前类别设置一致的设备协议.'))
        return release

    def _protocol_action(self, method):
        self.ensure_one()
        self.protocol_profile_id._check_manager()
        if self.adapter_code != 'protocol':
            raise UserError(self.env._('请选择可编辑 HTTP 接口.'))
        # Callers select a fixed action below; never accept a method name from RPC.
        actions = {'validate': self.protocol_profile_id.action_validate,
                   'publish': self.protocol_profile_id.action_publish,
                   'rollback': self.protocol_profile_id.action_rollback,
                   'draft': self.protocol_profile_id.action_new_draft}
        actions[method]()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_protocol_validate(self):
        return self._protocol_action('validate')

    def action_protocol_publish(self):
        return self._protocol_action('publish')

    def action_protocol_rollback(self):
        return self._protocol_action('rollback')

    def action_protocol_new_draft(self):
        return self._protocol_action('draft')

    def action_protocol_ai(self):
        self.ensure_one()
        self.check_access('write')
        return self.protocol_profile_id.action_blue_ai_chat()
