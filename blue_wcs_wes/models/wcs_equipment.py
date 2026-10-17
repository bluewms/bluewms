from odoo import fields, models


class WcsEquipment(models.Model):
    _inherit = 'wcs.equipment'

    adapter_code = fields.Selection(selection_add=[('wes', 'WES VZF')], ondelete={'wes': 'set default'})
    wes_authorization = fields.Char('WES Authorization', groups='base.group_system', copy=False)
    wes_token_url = fields.Char('WES Token URL', groups='base.group_system')
    wes_app_id = fields.Char('WES App ID', groups='base.group_system', copy=False)
    wes_app_secret = fields.Char('WES App Secret', groups='base.group_system', copy=False)
    wes_direction = fields.Selection([('in', '入库并组盘'), ('out', '出库并分配')], default='in', required=True)
    wes_warehouse_code = fields.Char('WES仓库编码')
    wes_room_code = fields.Char('WES库房编码')
    wes_owner_code = fields.Char('WES货主编码')
    wes_order_type = fields.Char('WES单据类型', default='TRANSFER_ASN')
    wes_storage_type = fields.Char('WES存储类型')

    def _connection_snapshot(self):
        result = super()._connection_snapshot()
        if self.adapter_code == 'wes':
            device = self.sudo()  # Private scheduler only; exact configured connection fields.
            result.update({key: device.category_id[key] or device[key] if device.category_id else device[key]
                           for key in ('wes_authorization', 'wes_token_url', 'wes_app_id', 'wes_app_secret')})
        return result
