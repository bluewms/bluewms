from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .policy_guard import POLICY_TOKEN


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    blue_putaway_release_id = fields.Many2one('blue.config.release', '上架策略版本', readonly=True, copy=False, check_company=True, ondelete='restrict')
    blue_putaway_binding_ids = fields.One2many('blue.putaway.binding', 'picking_id', '按规则固定的增强版本', copy=False)
    blue_putaway_application_ids = fields.One2many('blue.putaway.application', 'picking_id', '上架分配记录')

    @api.model_create_multi
    def create(self, vals_list):
        if any({'blue_putaway_release_id', 'blue_putaway_application_ids', 'blue_putaway_binding_ids'}.intersection(vals) for vals in vals_list):
            raise AccessError(self.env._('Putaway versions are assigned by policy execution.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'blue_putaway_release_id', 'blue_putaway_application_ids', 'blue_putaway_binding_ids'}.intersection(vals) and self.env.context.get('blue_putaway_token') is not POLICY_TOKEN:
            raise AccessError(self.env._('Putaway versions are assigned by policy execution.'))
        if 'company_id' in vals and any(self.mapped('blue_putaway_binding_ids')):
            raise UserError(self.env._('A picking with a pinned policy keeps its company and operation.'))
        return super().write(vals)

    def action_blue_apply_putaway(self):
        self.ensure_one()
        if not self.env.user.has_group('stock.group_stock_user'):
            raise AccessError(self.env._('Inventory access is required.'))
        self.check_access('write')
        if self.state in ('done', 'cancel'):
            raise UserError(self.env._('Apply putaway to an open transfer.'))
        self.move_line_ids._blue_apply_policy()
        return True

    def _blue_rule_bindings(self, rules):
        self.ensure_one()
        self.check_access('read')
        existing = self.env['blue.putaway.binding'].search(Domain('picking_id', '=', self.id) & Domain('rule_key', 'in', rules.ids))
        bindings = {binding.rule_key: binding for binding in existing}
        values = []
        for rule in rules:
            if rule.id in bindings:
                continue
            profile = rule.blue_profile_id
            release = profile.active_release_id if profile and profile.active else self.env['blue.config.release']
            values.append({'company_id': self.company_id.id, 'picking_id': self.id, 'rule_key': rule.id,
                           'rule_id': rule.id, 'profile_id': profile.id or False, 'release_id': release.id or False})
        if values:
            created = self.env['blue.putaway.binding'].with_context(blue_putaway_token=POLICY_TOKEN).create(values)
            bindings.update({binding.rule_key: binding for binding in created})
        return bindings
