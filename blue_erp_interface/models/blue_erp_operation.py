import re
from urllib.parse import unquote, urlsplit

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .guard import manager


class BlueErpOperation(models.Model):
    _name = 'blue.erp.operation'
    _description = 'ERP 允许的外部操作'
    _check_company_auto = True

    name = fields.Char('操作名称', required=True)
    interface_id = fields.Many2one('blue.erp.interface', required=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='interface_id.company_id', store=True)
    code = fields.Char('操作代码', required=True)
    path = fields.Char('请求路径', required=True)
    _unique_code = models.Constraint('UNIQUE(interface_id, code)', '同一接口的操作代码必须唯一.')

    @api.constrains('code', 'path')
    def _check_values(self):
        for operation in self:
            parts = urlsplit(operation.path or '')
            decoded = unquote(operation.path or '')
            if (not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', operation.code or '')
                    or not decoded.startswith('/') or decoded.startswith('//') or '\\' in decoded
                    or any(ord(c) < 32 for c in decoded) or parts.scheme or parts.netloc or parts.fragment
                    or '..' in decoded.split('/') or len(decoded) > 1024):
                raise ValidationError(self.env._('操作代码使用小写字母和下划线,路径须为本服务内的相对路径.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.interface_id._lock_configuration()
        return records

    def write(self, vals):
        manager(self)
        if 'interface_id' in vals:
            raise UserError(self.env._('不能更换操作所属接口.'))
        self.interface_id._lock_configuration()
        return super().write(vals)

    def unlink(self):
        manager(self)
        self.interface_id._lock_configuration()
        return super().unlink()
