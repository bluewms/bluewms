from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    blue_barcode_profile_id = fields.Many2one('blue.config.profile', 'AI 扫描配置', check_company=True,
        domain="[('hook_code','=','barcode_policy'),('company_id','=',company_id)]", ondelete='restrict')

    @api.constrains('blue_barcode_profile_id', 'company_id')
    def _check_barcode_profile(self):
        for operation in self:
            profile = operation.blue_barcode_profile_id
            if profile and (profile.hook_code != 'barcode_policy' or profile.company_id != operation.company_id):
                raise ValidationError(self.env._('请选择同公司条码策略资产.'))

    def action_blue_barcode_policy(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise ValidationError(self.env._('只有库存管理员可以配置扫描策略.'))
        if not self.blue_barcode_profile_id:
            self.blue_barcode_profile_id = self.env['blue.config.profile'].create({
                'name': self.env._('条码: %s', self.display_name), 'company_id': self.company_id.id,
                'template_id': self.env.ref('blue_barcode_extension.template_barcode').id})
        return {'type': 'ir.actions.act_window', 'res_model': 'blue.config.profile',
                'res_id': self.blue_barcode_profile_id.id, 'view_mode': 'form', 'target': 'current'}
