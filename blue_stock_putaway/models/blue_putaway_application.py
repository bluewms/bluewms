from odoo import api, fields, models
from odoo.exceptions import AccessError

from .policy_guard import check_internal


class BluePutawayApplication(models.Model):
    _name = 'blue.putaway.application'
    _description = 'Immutable Blue putaway allocation audit'
    _order = 'id desc'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, index=True)
    picking_id = fields.Many2one('stock.picking', required=True, check_company=True, ondelete='restrict', index=True)
    move_line_id = fields.Many2one('stock.move.line', check_company=True, ondelete='set null', index=True)
    release_id = fields.Many2one('blue.config.release', required=True, check_company=True, ondelete='restrict')
    location_id = fields.Many2one('stock.location', required=True, check_company=True, ondelete='restrict')
    quantity = fields.Float('分配数量', required=True)
    unit = fields.Selection([('loose', '散件（产品单位）'), ('package', '整包/托盘（个）')], default='loose', required=True)
    package_id = fields.Many2one('stock.package', '包裹/托盘', check_company=True, ondelete='restrict')
    binding_ids = fields.Many2many('blue.putaway.binding', 'blue_putaway_application_binding_rel', 'application_id', 'binding_id', string='原生规则与版本')
    reason = fields.Char('选择原因')
    input_json = fields.Text('输入快照', required=True)
    output_json = fields.Text('输出快照', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        check_internal(self)
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('Allocation audit is immutable.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_audit(self):
        raise AccessError(self.env._('Allocation audit must be retained.'))
