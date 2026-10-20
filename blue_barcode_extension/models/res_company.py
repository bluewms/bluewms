from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    blue_barcode_profile_id = fields.Many2one('blue.config.profile', '通用条码解析配置', ondelete='restrict')

    @api.constrains('blue_barcode_profile_id')
    def _check_barcode_profile(self):
        for company in self:
            profile = company.blue_barcode_profile_id
            if profile and (profile.hook_code != 'barcode_policy' or profile.company_id != company):
                raise ValidationError(self.env._('通用条码配置必须是同公司条码策略资产.'))
