import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    wcs_upgrade_notice = fields.Char('配置说明', compute='_compute_wcs_upgrade_notice')

    @api.depends('hook_code', 'active_release_id')
    def _compute_wcs_upgrade_notice(self):
        for profile in self:
            profile.wcs_upgrade_notice = ('旧发布版本已保留. 直接任务生成版创建配置需要重新试算、验证并发布.'
                if profile.hook_code == 'wcs_creation' and profile.active_release_id and profile.active_release_id.version_id.contract != 'wcs_creation/2' else False)

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
            if type(case) is not dict or set(case) != {'name', 'input', 'expected_tasks'} or type(case['name']) is not str or type(case['expected_tasks']) is not list:
                raise ValidationError(self.env._('Each trial requires name, input, expected_tasks.'))
            result = self.env['blue.extension.contract']._run(self.draft_code, case['input'], self.contract)
            if result != case['expected_tasks']:
                raise ValidationError(self.env._('WCS trial failed: %s', case['name']))
            results.append({'name': case['name'], 'passed': True, 'result': result})
        return results

    def action_open_wcs_preview(self):
        self._check_manager()
        if self.hook_code != 'wcs_creation':
            raise ValidationError(self.env._('Choose a WCS strategy.'))
        return {'type': 'ir.actions.act_window', 'name': self.env._('WCS真实作业试算'),
                'res_model': 'wcs.preview', 'view_mode': 'form', 'target': 'new', 'context': {'default_profile_id': self.id}}
