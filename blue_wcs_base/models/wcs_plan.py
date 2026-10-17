from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .guard import WCS_TOKEN


class WcsPlan(models.Model):
    _name = 'wcs.plan'
    _description = 'Immutable WCS movement plan'
    _check_company_auto = True
    _order = 'id desc'

    name = fields.Char('计划编号', required=True)
    company_id = fields.Many2one('res.company', required=True)
    picking_id = fields.Many2one('stock.picking', required=True, check_company=True, ondelete='restrict')
    carrier_id = fields.Many2one('stock.package', '载具', check_company=True, index=True)
    unit_key = fields.Char(required=True)
    revision = fields.Integer(required=True)
    route_id = fields.Many2one('wcs.route', '旧版线路引用', check_company=True, ondelete='restrict')
    snapshot = fields.Text('固定路线及策略', required=True)
    request_ids = fields.One2many('wcs.request', 'plan_id', 'WCS任务')
    line_ids = fields.One2many('wcs.plan.line', 'plan_id', '货物明细')
    _unique_revision = models.Constraint('UNIQUE(picking_id, unit_key, revision)', 'Duplicate WCS unit revision.')

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('Create plans through the WCS planning service.'))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('WCS plans are immutable.'))

    def unlink(self):
        raise UserError(self.env._('Keep WCS movement history.'))
