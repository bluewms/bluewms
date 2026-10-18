import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    wcs_upgrade_notice = fields.Char('配置说明', compute='_compute_wcs_upgrade_notice')

    @api.depends('hook_code', 'contract')
    def _compute_wcs_upgrade_notice(self):
        for profile in self:
            profile.wcs_upgrade_notice = ('旧发布版本及固定任务保留. /1保留线路过滤且复核人工设备与模式, /2兼容人工授权的旧编排; /3继续原合同. 完整逐行增强和同数据多任务请新建/4版AI创建配置, 试算后人工发布.'
                if profile.hook_code == 'wcs_creation' and profile.contract != 'wcs_creation/4' else False)

    def _run_tests(self):
        self.ensure_one()
        if self.hook_code != 'wcs_creation':
            return super()._run_tests()
        self.env['blue.extension.contract']._validate_code(self.draft_code, self.contract)
        try:
            cases = json.loads(self.draft_tests or '')
        except (ValueError, RecursionError) as error:
            raise ValidationError(self.env._('WCS trials must be valid JSON.')) from error
        if type(cases) is not list or not 1 <= len(cases) <= 20:
            raise ValidationError(self.env._('Provide 1 to 20 WCS trials.'))
        results = []
        for case in cases:
            expected_key = 'expected_result' if self.contract in ('wcs_creation/3', 'wcs_creation/4') else 'expected_order' if self.contract == 'wcs_creation/1' else 'expected_tasks'
            if type(case) is not dict or set(case) != {'name', 'input', expected_key} or type(case['name']) is not str:
                raise ValidationError(self.env._('Each trial requires name, input and the contract-specific expected result.'))
            result = self.env['blue.extension.contract']._run(self.draft_code, case['input'], self.contract)
            actual = [item['route_id'] for item in result] if self.contract == 'wcs_creation/1' else result
            if actual != case[expected_key]:
                raise ValidationError(self.env._('WCS trial failed: %s', case['name']))
            results.append({'name': case['name'], 'passed': True, 'result': result})
        if self.contract == 'wcs_creation/3' and {case['input']['request'].get('phase') for case in cases} != {'configure', 'tasks'}:
            raise ValidationError(self.env._('WCS /3 trials must cover configure and tasks phases.'))
        if self.contract == 'wcs_creation/4' and {case['input']['request'].get('phase') for case in cases} != {'lines', 'tasks'}:
            raise ValidationError(self.env._('WCS /4 trials must cover lines and tasks phases.'))
        return results

    def action_open_wcs_preview(self):
        self._check_manager()
        if self.hook_code != 'wcs_creation':
            raise ValidationError(self.env._('Choose a WCS strategy.'))
        return {'type': 'ir.actions.act_window', 'name': self.env._('WCS真实作业试算'),
                'res_model': 'wcs.preview', 'view_mode': 'form', 'target': 'new', 'context': {'default_profile_id': self.id}}
