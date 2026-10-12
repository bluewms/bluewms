from odoo import fields, models


class StockPackage(models.Model):
    _name = 'stock.package'
    _inherit = ['stock.package', 'mail.thread', 'mail.activity.mixin']

    package_use = fields.Selection(
        [('disposable', '一次性包装盒'), ('reusable', '可重复使用的盒子')],
        string='包裹使用', default='reusable', required=True,
    )
    package_removal_priority = fields.Char('子位置', tracking=True, copy=False)

    def _blue_reset_empty_priority(self):
        empty = self.exists().filtered(lambda package: not any(quant.quantity or quant.reserved_quantity for quant in package.contained_quant_ids))
        empty.filtered('package_removal_priority').write({'package_removal_priority': False})

    def action_batch_copy(self):
        self.ensure_one()
        wizard = self.env['copy.package.wizard'].create({'pack': self.id})
        return {'type': 'ir.actions.act_window', 'name': self.env._('批量复制包裹'),
                'view_mode': 'form', 'res_model': 'copy.package.wizard', 'target': 'new', 'res_id': wizard.id}
