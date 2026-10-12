from odoo import api, fields, models
from odoo.exceptions import AccessError

from .asset_guard import check_internal


class BlueConfigRelease(models.Model):
    _name = 'blue.config.release'
    _description = 'Immutable Blue scene release'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char('发布版本', required=True)
    profile_id = fields.Many2one('blue.config.profile', required=True, ondelete='restrict', check_company=True, index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='restrict', index=True)
    version_id = fields.Many2one('blue.customization.version', required=True, ondelete='restrict', check_company=True)
    previous_release_id = fields.Many2one('blue.config.release', ondelete='restrict', check_company=True)
    snapshot = fields.Text('完整场景快照', required=True)
    content_hash = fields.Char('场景校验值', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        check_internal(self)
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('Published releases are immutable.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_immutable(self):
        raise AccessError(self.env._('Published releases must be retained for audit and rollback.'))
