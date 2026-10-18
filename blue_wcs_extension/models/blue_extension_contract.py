from odoo import api, models
from odoo.exceptions import ValidationError
from .creation_contract import run_creation, run_creation_v3
from .creation_schema import creation_schema
from .creation_v4 import run_creation_v4
from .creation_v4_schema import creation_schema_v4
from odoo.addons.blue_extension_contract.tools.policy import PolicyError, run_policy, validate_code


class BlueExtensionContract(models.AbstractModel):
    _inherit = 'blue.extension.contract'

    @api.model
    def _describe(self, contract):
        if contract == 'wcs_creation/4':
            return creation_schema_v4()
        return creation_schema() if contract == 'wcs_creation/3' else super()._describe(contract)

    @api.model
    def _validate_code(self, code, contract='putaway_policy/1'):
        if contract not in ('wcs_creation/1', 'wcs_creation/2', 'wcs_creation/3', 'wcs_creation/4'):
            return super()._validate_code(code, contract)
        try:
            validate_code(code)
        except PolicyError as error:
            raise ValidationError(self.env._('Invalid WCS strategy: %s', str(error))) from error

    @api.model
    def _run(self, code, payload, contract='putaway_policy/1'):
        if contract not in ('wcs_creation/1', 'wcs_creation/2', 'wcs_creation/3', 'wcs_creation/4'):
            return super()._run(code, payload, contract)
        try:
            if contract == 'wcs_creation/4':
                return run_creation_v4(code, payload)
            if contract == 'wcs_creation/3':
                return run_creation_v3(code, payload)
            return run_creation(code, payload) if contract == 'wcs_creation/2' else run_policy(code, payload, id_key='route_id')
        except PolicyError as error:
            raise ValidationError(self.env._('Invalid WCS strategy: %s', str(error))) from error
