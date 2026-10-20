from odoo import models
from odoo.exceptions import UserError


class BlueBarcodeSession(models.Model):
    _inherit = 'blue.barcode.session'

    def _decode(self, raw):
        if not self.policy_snapshot:
            return super()._decode(raw)
        context = self._policy_context()
        try:
            context['standard'] = super()._decode(raw)
        except UserError:
            context['standard'] = {}
        return self.env['blue.extension.contract']._run(self.policy_snapshot['code'], {
            'request': {'phase': 'parse', 'raw': raw, 'context': context, 'parsed': {}},
            'candidates': []}, 'barcode_policy/1')

    def _policy_context(self):
        return {'kind': self.kind, 'company_id': self.company_id.id, 'session_id': self.id,
                'scan': self.scan_context or {}}

    def _decide(self, parsed, candidates):
        if not self.policy_snapshot:
            return super()._decide(parsed, candidates)
        return self.env['blue.extension.contract']._run(self.policy_snapshot['code'], {
            'request': {'phase': 'decide', 'raw': parsed['code'], 'context': self._policy_context(), 'parsed': parsed},
            'candidates': candidates}, 'barcode_policy/1')
