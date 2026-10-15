from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .guard import WCS_TOKEN


class WcsPlanLine(models.Model):
    _name = 'wcs.plan.line'
    _description = 'WCS planned product quantity'
    _check_company_auto = True

    plan_id = fields.Many2one('wcs.plan', required=True, ondelete='restrict', check_company=True)
    company_id = fields.Many2one(related='plan_id.company_id', store=True)
    move_line_id = fields.Many2one('stock.move.line', ondelete='set null', check_company=True, index=True)
    source_line_ref = fields.Integer('原库存明细编号', required=True)
    product_id = fields.Many2one('product.product', required=True)
    uom_id = fields.Many2one('uom.uom', required=True)
    quantity = fields.Float(required=True)
    lot_id = fields.Many2one('stock.lot', check_company=True)
    package_id = fields.Many2one('stock.package', check_company=True)
    _positive_quantity = models.Constraint('CHECK(quantity > 0)', 'Planned quantity must be positive.')
    _unique_line = models.Constraint('UNIQUE(plan_id, move_line_id)', 'Duplicate WCS product line.')

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('Plan lines can only be created by the planning service.'))
        vals_list = [dict(vals, source_line_ref=vals['move_line_id']) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('Planned quantities are immutable.'))

    def unlink(self):
        raise UserError(self.env._('Keep planned quantity history.'))
