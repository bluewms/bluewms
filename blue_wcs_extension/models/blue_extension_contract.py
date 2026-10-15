from odoo import api, models
from odoo.exceptions import ValidationError
from .creation_contract import run_creation
from odoo.addons.blue_extension_contract.tools.policy import PolicyError, run_policy, validate_code


class BlueExtensionContract(models.AbstractModel):
    _inherit = 'blue.extension.contract'

    @api.model
    def _validate_code(self, code, contract='putaway_policy/1'):
        if contract not in ('wcs_creation/1', 'wcs_creation/2'):
            return super()._validate_code(code, contract)
        try:
            validate_code(code)
        except PolicyError as error:
            raise ValidationError(self.env._('Invalid WCS strategy: %s', str(error))) from error

    @api.model
    def _run(self, code, payload, contract='putaway_policy/1'):
        if contract not in ('wcs_creation/1', 'wcs_creation/2'):
            return super()._run(code, payload, contract)
        try:
            return run_creation(code, payload) if contract == 'wcs_creation/2' else run_policy(code, payload, id_key='route_id')
        except PolicyError as error:
            raise ValidationError(self.env._('Invalid WCS strategy: %s', str(error))) from error
