from odoo import api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.blue_stock_inventory.models.guard import trusted


class BlueErpEvent(models.Model):
    _inherit = 'blue.erp.event'

    inventory_id = fields.Many2one('stock.inventory', '盘点单', readonly=True, copy=False, check_company=True, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        inventory_id = self.env.context.get('blue_stock_inventory_id') if trusted(self) else False
        for values in vals_list:
            if 'inventory_id' in values:
                raise AccessError(self.env._('盘点同步关联只能由盘点流程建立.'))
            values['inventory_id'] = False
            if inventory_id:
                inventory = self.env['stock.inventory'].browse(inventory_id).exists()
                if not inventory or inventory.company_id.id != values.get('company_id') or inventory.state != 'in_progress':
                    raise AccessError(self.env._('盘点同步的公司或状态不一致.'))
                values['inventory_id'] = inventory.id
                snapshot = values['input_snapshot']
                snapshot['request'] = {**snapshot['request'], 'number': inventory.name, 'external_id': inventory.name}
                line_ids = sorted(self.env.context.get('blue_stock_inventory_line_ids', []))
                values['source_key'] = 'inventory:%s:%s' % (inventory.id, ','.join(str(i) for i in line_ids))
        return super().create(vals_list)
