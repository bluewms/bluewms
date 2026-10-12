from odoo import api, models
from odoo.exceptions import ValidationError

from ..tools.policy import PolicyError, run_policy, validate_code


class BlueExtensionContract(models.AbstractModel):
    _name = 'blue.extension.contract'
    _description = 'Blue policy contract'

    @api.model
    def _validate_code(self, code, contract='putaway_policy/1'):
        if contract not in ('putaway_policy/1', 'putaway_policy/2'):
            raise ValidationError(self.env._('Unsupported policy contract.'))
        try:
            validate_code(code)
        except PolicyError as error:
            raise ValidationError(self.env._('Invalid policy: %s', str(error))) from error

    @api.model
    def _run(self, code, payload, contract='putaway_policy/1'):
        self._validate_code(code, contract)
        try:
            return run_policy(code, payload)
        except PolicyError as error:
            raise ValidationError(self.env._('Invalid policy: %s', str(error))) from error
