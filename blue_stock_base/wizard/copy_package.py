from odoo import fields, models
from odoo.exceptions import UserError


class CopyPackageWizard(models.TransientModel):
    _name = 'copy.package.wizard'
    _description = '复制包裹'

    qty = fields.Integer('复制数量', default=1, required=True)
    pack = fields.Many2one('stock.package', string='包裹', required=True)

    def action_copy(self):
        self.ensure_one()
        if not 1 <= self.qty <= 2000:
            raise UserError(self.env._('复制数量必须在1到2000之间'))
        self.pack.check_access('r')
        Package = self.env['stock.package']
        values = self.pack.copy_data()[0]
        values.update(quant_ids=[], child_package_ids=[], parent_package_id=False,
                      package_dest_id=False, package_removal_priority=False, location_id=False)
        packages = Package.create([dict(values) for _ in range(self.qty)])
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.package',
                'view_mode': 'list,form', 'domain': [('id', 'in', packages.ids)]}
