from odoo import api, fields, models
from odoo.exceptions import AccessError

from .guard import WCS_TOKEN


class WcsEvent(models.Model):
    _name = 'wcs.event'
    _description = 'Immutable WCS device event'
    _check_company_auto = True

    request_id = fields.Many2one('wcs.request', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True)
    external_id = fields.Char(required=True)
    event = fields.Char(required=True)
    point = fields.Char()
    content_hash = fields.Char(required=True)
    _unique_event = models.Constraint('UNIQUE(request_id, external_id)', 'Duplicate device event.')

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('Events require the authenticated device workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('Device events are immutable.'))

    def unlink(self):
        raise AccessError(self.env._('Keep device event history.'))
