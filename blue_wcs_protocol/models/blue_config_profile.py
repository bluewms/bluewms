import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools.protocol import CONTRACT
from .guard import PROTOCOL_TOKEN


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    device_category_id = fields.Many2one('wcs.equipment.category', '设备类别', readonly=True,
                                         copy=False, check_company=True, ondelete='restrict')
    _unique_device_category = models.Constraint('UNIQUE(device_category_id)', '每个设备类别只维护一份协议资产.')

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('device_category_id') for vals in vals_list) and self.env.context.get('blue_protocol_token') is not PROTOCOL_TOKEN:
            raise AccessError(self.env._('设备协议资产只能从设备类别创建.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'device_category_id' in vals:
            raise AccessError(self.env._('设备协议资产不能更换所属类别.'))
        return super().write(vals)

    @api.constrains('device_category_id', 'template_id', 'company_id')
    def _check_device_category(self):
        for profile in self:
            if profile.hook_code == 'device_protocol' and (not profile.device_category_id or profile.contract != CONTRACT):
                raise ValidationError(self.env._('请从设备类别创建设备协议资产.'))
            if profile.device_category_id and (profile.hook_code != 'device_protocol'
                    or profile.device_category_id.company_id != profile.company_id):
                raise ValidationError(self.env._('协议、设备类别及公司必须一致.'))

    def _blue_ai_contracts(self):
        return {**super()._blue_ai_contracts(), 'device_protocol': (CONTRACT,)}

    def _draft_payload(self):
        data = super()._draft_payload()
        if self.hook_code == 'device_protocol':
            data['device_scope'] = self.device_category_id._protocol_scope()
        return data

    def _scope_snapshot(self):
        data = super()._scope_snapshot()
        if self.hook_code == 'device_protocol':
            data['device_scope'] = self.device_category_id._protocol_scope()
        return data

    def _run_tests(self):
        if self.hook_code != 'device_protocol':
            return super()._run_tests()
        self.ensure_one()
        self.env['blue.extension.contract']._validate_code(self.draft_code, CONTRACT)
        try:
            cases = json.loads(self.draft_tests or '')
        except (ValueError, RecursionError) as error:
            raise ValidationError(self.env._('设备报文试算必须是有效 JSON.')) from error
        if type(cases) is not list or not 3 <= len(cases) <= 20:
            raise ValidationError(self.env._('请提供 3 至 20 个报文试算,覆盖下发、响应及回调.'))
        phases, results = set(), []
        for case in cases:
            if (type(case) is not dict or set(case) != {'name', 'input', 'expected_result'}
                    or type(case['name']) is not str or not 1 <= len(case['name']) <= 256):
                raise ValidationError(self.env._('每个设备试算需要 name、input 和 expected_result.'))
            result = self.env['blue.extension.contract']._run(self.draft_code, case['input'], CONTRACT)
            if result != case['expected_result']:
                raise ValidationError(self.env._('设备报文试算失败: %s', case['name']))
            phases.add(case['input']['request']['phase'])
            results.append({'name': case['name'], 'passed': True, 'result': result})
        if phases != {'request', 'response', 'callback'}:
            raise ValidationError(self.env._('设备试算必须覆盖下发、响应及完成回调三个阶段.'))
        return results

    def action_publish(self):
        if self.hook_code == 'device_protocol':
            self.device_category_id._protocol_check_configuration()
        return super().action_publish()

    def action_rollback(self):
        if self.hook_code == 'device_protocol':
            previous = self.active_release_id.previous_release_id
            if previous and json.loads(previous.snapshot)['scope'] != self._scope_snapshot():
                raise UserError(self.env._('历史版本的人工配置不同,请先核对类别设置再回滚.'))
        return super().action_rollback()
