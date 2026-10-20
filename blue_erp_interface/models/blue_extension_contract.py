from odoo import api, models
from odoo.exceptions import ValidationError

from ..tools.contract import CONTRACT, ProtocolError, mapping_schema, run_mapping, validate_protocol


class BlueExtensionContract(models.AbstractModel):
    _inherit = 'blue.extension.contract'

    @api.model
    def _describe(self, contract):
        return mapping_schema() if contract == CONTRACT else super()._describe(contract)

    @api.model
    def _validate_code(self, code, contract='putaway_policy/1'):
        if contract != CONTRACT:
            return super()._validate_code(code, contract)
        try:
            validate_protocol(code)
        except ProtocolError as error:
            raise ValidationError(self.env._('ERP 代码无效: %s', str(error))) from error

    @api.model
    def _run(self, code, payload, contract='putaway_policy/1'):
        if contract != CONTRACT:
            return super()._run(code, payload, contract)
        try:
            return run_mapping(code, payload)
        except ProtocolError as error:
            raise ValidationError(self.env._('ERP 试算失败: %s', str(error))) from error
