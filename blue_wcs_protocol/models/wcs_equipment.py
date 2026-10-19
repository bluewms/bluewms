from odoo import fields, models
from odoo.exceptions import UserError


class WcsEquipment(models.Model):
    _inherit = 'wcs.equipment'

    adapter_code = fields.Selection(selection_add=[('protocol', '可编辑 HTTP 接口')], ondelete={'protocol': 'set default'})
    protocol_device_code = fields.Char('厂商设备编码', help='回调提供 deviceId 时用于核对,不作为连接地址或认证信息.')

    def _supports_wcs_loose_goods(self):
        return self.supports_loose_goods if self.adapter_code == 'protocol' else super()._supports_wcs_loose_goods()

    def _supports_wcs_location_scope(self):
        return self.supports_location_scope if self.adapter_code == 'protocol' else super()._supports_wcs_location_scope()

    def write(self, vals):
        self.check_access('write')
        if {'category_id', 'adapter_code', 'company_id', 'protocol_device_code', 'active'}.intersection(vals):
            if self.env['wcs.request'].sudo().search([
                    ('equipment_id', 'in', self.ids), ('protocol_release_id', '!=', False),
                    ('state', 'not in', ['completed', 'cancelled'])], limit=1):
                raise UserError(self.env._('设备存在未结束协议任务,不能更换类别、编码或停用.'))
        return super().write(vals)

    def _connection_snapshot(self):
        if self.adapter_code != 'protocol':
            return super()._connection_snapshot()
        self.ensure_one()
        # Private sender only; new protocols never fall back to historical device credentials.
        category = self.category_id.sudo()
        if not category or category.adapter_code != 'protocol':
            raise UserError(self.env._('可编辑接口必须关联同公司设备类别.'))
        return {'adapter_code': 'protocol', 'endpoint': (category.ip_post or '').rstrip('/') + (category.submit_path or ''),
                'api_key': category.app_key or '', 'api_secret': category.app_secret or '',
                'auth_mode': ('headers' if category.protocol_auth_mode == 'headers' and category.app_key
                              else 'bearer' if category.app_key else 'none'), 'key_header': category.protocol_key_header,
                'secret_header': category.protocol_secret_header}
