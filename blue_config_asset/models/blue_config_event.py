from odoo import api, fields, models
from odoo.exceptions import AccessError

from .asset_guard import check_internal


class BlueConfigEvent(models.Model):
    _name = 'blue.config.event'
    _description = 'Blue configuration audit event'
    _order = 'id desc'
    _check_company_auto = True

    profile_id = fields.Many2one('blue.config.profile', required=True, check_company=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='restrict', index=True)
    release_id = fields.Many2one('blue.config.release', check_company=True, ondelete='restrict')
    event_type = fields.Selection([('validated', '验证'), ('published', '发布'), ('rollback', '回滚')], required=True)
    details = fields.Text('记录')

    @api.model_create_multi
    def create(self, vals_list):
        check_internal(self)
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('Audit events are immutable.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_immutable(self):
        raise AccessError(self.env._('Audit events must be retained.'))
