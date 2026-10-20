import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools.contract import CONTRACT
from .guard import ERP_TOKEN


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    erp_interface_id = fields.Many2one('blue.erp.interface', 'ERP 接口', copy=False, readonly=True,
                                       check_company=True, ondelete='restrict')
    _unique_erp_interface = models.Constraint('UNIQUE(erp_interface_id)', '每个 ERP 接口仅维护一份代码资产.')

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('erp_interface_id') for v in vals_list) and self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            raise AccessError(self.env._('ERP 资产只能从接口页面创建.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'erp_interface_id' in vals:
            raise AccessError(self.env._('不能更换 ERP 资产所属接口.'))
        return super().write(vals)

    @api.constrains('erp_interface_id', 'template_id', 'company_id')
    def _check_erp_interface(self):
        for profile in self:
            if profile.hook_code == 'erp_mapping' and (not profile.erp_interface_id or profile.contract != CONTRACT):
                raise ValidationError(self.env._('请从 ERP 接口页面创建资产.'))
            if profile.erp_interface_id and (profile.hook_code != 'erp_mapping' or profile.company_id != profile.erp_interface_id.company_id):
                raise ValidationError(self.env._('ERP 接口、资产公司及合同必须一致.'))

    def _blue_ai_contracts(self):
        return {**super()._blue_ai_contracts(), 'erp_mapping': (CONTRACT,)}

    def _draft_payload(self):
        result = super()._draft_payload()
        if self.erp_interface_id:
            result['erp_scope'] = self.erp_interface_id._scope()
        return result

    def _scope_snapshot(self):
        result = super()._scope_snapshot()
        if self.erp_interface_id:
            result['erp_scope'] = self.erp_interface_id._scope()
        return result

    def _run_tests(self):
        if self.hook_code != 'erp_mapping':
            return super()._run_tests()
        self.ensure_one()
        try:
            tests = json.loads(self.draft_tests or '')
        except (ValueError, RecursionError) as error:
            raise ValidationError(self.env._('ERP 试算必须是 JSON 数组.')) from error
        if type(tests) is not list or not 3 <= len(tests) <= 20:
            raise ValidationError(self.env._('请提供 3 至 20 个准确试算.'))
        phases, results = set(), []
        for case in tests:
            if (type(case) is not dict or set(case) != {'name', 'input', 'expected_result'}
                    or type(case['name']) is not str or not 1 <= len(case['name']) <= 256):
                raise ValidationError(self.env._('试算需要 name、input、expected_result.'))
            if case['input'].get('request', {}).get('kind') != self.erp_interface_id.kind:
                raise ValidationError(self.env._('试算类别须与当前 ERP 接口一致.'))
            result = self.env['blue.extension.contract']._run(self.draft_code, case['input'], CONTRACT)
            if result != case['expected_result']:
                raise ValidationError(self.env._('ERP 试算结果不符: %s', case['name']))
            phases.add(case['input']['request']['phase'])
            if 'actions' in result and any(a['operation'] not in self.erp_interface_id.operation_ids.mapped('code') for a in result['actions']):
                raise ValidationError(self.env._('代码引用了未配置的 ERP 操作.'))
            results.append({'name': case['name'], 'passed': True, 'result': result})
        required = {'inventory', 'response'} if self.erp_interface_id.kind == 'inventory' else {'receive', 'complete', 'response'}
        if not required.issubset(phases):
            raise ValidationError(self.env._('试算须覆盖接收或盘点、完成及响应的适用阶段.'))
        return results

    def action_publish(self):
        if self.erp_interface_id:
            self._check_manager()
            self.env.cr.execute('SELECT id FROM blue_erp_interface WHERE id=%s FOR UPDATE', [self.erp_interface_id.id])
            if not self.erp_interface_id.operation_ids:
                raise UserError(self.env._('请先配置允许调用的 ERP 操作.'))
        return super().action_publish()

    def action_rollback(self):
        if self.erp_interface_id:
            previous = self.active_release_id.previous_release_id
            if previous and json.loads(previous.snapshot)['scope']['erp_scope'] != self.erp_interface_id._scope():
                raise UserError(self.env._('历史版本的接口配置不同,请先核对.'))
        return super().action_rollback()
