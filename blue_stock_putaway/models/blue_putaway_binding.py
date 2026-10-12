from odoo import api, fields, models
from odoo.exceptions import AccessError

from .policy_guard import check_internal


class BluePutawayBinding(models.Model):
    _name = 'blue.putaway.binding'
    _description = 'Immutable per-picking native-rule policy selection'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, index=True)
    picking_id = fields.Many2one('stock.picking', required=True, check_company=True, ondelete='cascade', index=True)
    rule_key = fields.Integer('原始规则ID', required=True)
    rule_id = fields.Many2one('stock.putaway.rule', '原生上架规则', check_company=True, ondelete='set null')
    profile_id = fields.Many2one('blue.config.profile', '增强场景', check_company=True, ondelete='restrict')
    release_id = fields.Many2one('blue.config.release', '固定代码版本', check_company=True, ondelete='restrict')

    _selection_unique = models.Constraint('UNIQUE(picking_id, rule_key)', 'A picking keeps one selection per native rule.')

    @api.model_create_multi
    def create(self, vals_list):
        check_internal(self)
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(self.env._('规则的已使用策略版本不可直接修改.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_history(self):
        raise AccessError(self.env._('已使用的策略选择需要保留用于审计.'))
