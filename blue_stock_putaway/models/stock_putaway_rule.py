from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockPutawayRule(models.Model):
    _inherit = 'stock.putaway.rule'

    blue_profile_id = fields.Many2one('blue.config.profile', '增强策略', check_company=True, ondelete='set null',
        domain="[('company_id', '=', company_id), ('hook_code', '=', 'putaway_policy')]",
        help='选择可复用的场景名称. 系统范围和容量先检查, 场景代码只继续筛选. 未发布时不执行草稿.')
    blue_active_release_id = fields.Many2one(related='blue_profile_id.active_release_id', string='当前增强版本')

    @api.constrains('blue_profile_id', 'company_id')
    def _check_blue_profile(self):
        for rule in self:
            if rule.blue_profile_id and (rule.blue_profile_id.company_id != rule.company_id or rule.blue_profile_id.hook_code != 'putaway_policy'):
                raise ValidationError(self.env._('请选择同一公司的上架增强策略.'))

    def _blue_locations(self, product):
        self.ensure_one()
        location = self.location_out_id
        if self.sublocation == 'last_used':
            location = self._get_last_used_location(product) or location
        if self.storage_category_id:
            return location.child_internal_location_ids.filtered(lambda child: child.storage_category_id == self.storage_category_id)
        return location if location.usage == 'internal' else self.env['stock.location']
