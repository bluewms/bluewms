import json

from odoo import api, models
from odoo.exceptions import ValidationError

from ..tools.contract import CONTRACT


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    @api.constrains('template_id')
    def _check_barcode_contract(self):
        for profile in self:
            if profile.hook_code == 'barcode_policy' and profile.contract != CONTRACT:
                raise ValidationError(self.env._('条码策略必须使用 barcode_policy/1.'))

    def _blue_ai_contracts(self):
        return {**super()._blue_ai_contracts(), 'barcode_policy': (CONTRACT,)}

    def _run_tests(self):
        if self.hook_code != 'barcode_policy':
            return super()._run_tests()
        self.ensure_one()
        try:
            cases = json.loads(self.draft_tests or '')
        except (ValueError, RecursionError) as error:
            raise ValidationError(self.env._('条码准确试算必须为 JSON.')) from error
        if type(cases) is not list or not 2 <= len(cases) <= 20:
            raise ValidationError(self.env._('提供 2 至 20 个试算,覆盖解析和动作两个阶段.'))
        results, phases = [], set()
        for case in cases:
            if (type(case) is not dict or set(case) != {'name', 'input', 'expected_result'}
                    or type(case['name']) is not str or not 1 <= len(case['name']) <= 256):
                raise ValidationError(self.env._('试算需要 name、input 和 expected_result.'))
            result = self.env['blue.extension.contract']._run(self.draft_code, case['input'], CONTRACT)
            if result != case['expected_result']:
                raise ValidationError(self.env._('条码准确试算结果不符: %s', case['name']))
            phases.add(case['input']['request']['phase'])
            results.append({'name': case['name'], 'passed': True, 'result': result})
        if phases != {'parse', 'decide'}:
            raise ValidationError(self.env._('必须同时覆盖 parse 和 decide 两阶段.'))
        return results
