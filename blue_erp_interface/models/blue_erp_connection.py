from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.blue_config_asset.models.blue_config_profile import digest


class BlueErpConnection(models.Model):
    _name = 'blue.erp.connection'
    _description = 'ERP 连接'
    _check_company_auto = True

    name = fields.Char('连接名称', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    base_url = fields.Char('ERP 服务地址', required=True, groups='base.group_system')
    app_key = fields.Char('App Key / Token (appId)', groups='base.group_system', copy=False)
    app_secret = fields.Char('App Secret (appSecret)', groups='base.group_system', copy=False)
    auth_mode = fields.Selection([('none', '由代码指定请求头'), ('bearer', 'Bearer Token')],
                                  string='默认下发认证', default='bearer', required=True, groups='base.group_system')
    service_user_id = fields.Many2one('res.users', '接收建单执行用户', required=True,
                                     default=lambda self: self.env.user, groups='base.group_system', ondelete='restrict')

    @api.constrains('base_url', 'company_id', 'service_user_id')
    def _check_configuration(self):
        for connection in self:
            parts = urlsplit(connection.base_url or '')
            if (parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password
                    or parts.query or parts.fragment or parts.path not in ('', '/')):
                raise ValidationError(self.env._('ERP 服务地址只能包含 HTTP(S) 协议、主机和端口.'))
            if (not connection.service_user_id.active
                    or connection.company_id not in connection.service_user_id.company_ids
                    or not connection.service_user_id.has_group('stock.group_stock_user')):
                raise ValidationError(self.env._('建单执行用户必须有效,具有本公司权限及库存权限.'))

    def write(self, vals):
        self.check_access('write')
        if set(vals) - {'name'}:
            if not self.env.user.has_group('base.group_system'):
                raise AccessError(self.env._('仅系统管理员可以修改 ERP 连接.'))
            # Exact authorized connections only; pending work may be owned by other warehouse users.
            if self.env['stock.picking'].sudo().search_count([('blue_erp_document_id.interface_id.connection_id', 'in', self.ids), ('state', 'not in', ['done', 'cancel'])]):
                raise UserError(self.env._('ERP 仍有关联单据未结束,请先处理后再修改连接.'))
            if self.env['blue.erp.event'].sudo().search_count([
                    ('interface_id.connection_id', 'in', self.ids), ('state', 'not in', ['done', 'failed'])]):
                raise UserError(self.env._('存在未结束 ERP 事件,请先处理后再更改连接.'))
        return super().write(vals)

    def _fingerprint(self):
        self.ensure_one()
        # Narrow private read of one authorized connection; only its digest enters assets.
        connection = self.sudo()
        return digest({key: connection[key] for key in ('base_url', 'app_key', 'app_secret', 'auth_mode')}
                      | {'user': connection.service_user_id.id, 'company': connection.company_id.id})
