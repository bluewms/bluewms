from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class WcsEquipment(models.Model):
    _name = 'wcs.equipment'
    _description = 'WCS device connection'
    _check_company_auto = True
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('设备名称', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    adapter_code = fields.Selection([('simulation', '模拟设备'), ('hik', '海康国标任务'), ('json', '标准 JSON 网关')], required=True, default='simulation')
    endpoint = fields.Char('任务下发 URL', groups='base.group_system')
    api_key = fields.Char('App Key / Bearer Token', groups='base.group_system', copy=False)
    api_secret = fields.Char('海康 App Secret', groups='base.group_system', copy=False)
    callback_token = fields.Char('回调凭据', groups='base.group_system', copy=False)
    task_type = fields.Char('设备任务模板', default='TRANSFER', required=True)
    category_id = fields.Many2one('wcs.equipment.category', '设备类别', check_company=True)
    owner_user_id = fields.Many2one('res.users', '所有者')
    technician_user_id = fields.Many2one('res.users', '技术员')
    maintenance_team_id = fields.Many2one('wcs.team', '作业团队', check_company=True)
    partner_id = fields.Many2one('res.partner', '供应商', check_company=True)
    partner_ref = fields.Char('供应商参考')
    location = fields.Char('使用地点')
    model = fields.Char('模型')
    serial_no = fields.Char('序列号', copy=False)
    assign_date = fields.Date('分配日期')
    effective_date = fields.Date('实际日期', default=fields.Date.context_today)
    warranty_date = fields.Date('质量保证到期日期')
    cost = fields.Float('成本')
    note = fields.Html('注释')
    color = fields.Integer('颜色')
    task_tmpl = fields.Char('任务模板', related='task_type', readonly=False)
    request_ids = fields.One2many('wcs.request', 'equipment_id', 'WCS作业')
    maintenance_count = fields.Integer('作业统计', compute='_compute_counts')

    @api.depends('request_ids')
    def _compute_counts(self):
        for device in self:
            device.maintenance_count = len(device.request_ids)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals, adapter_code=self.env['wcs.equipment.category'].browse(vals['category_id']).adapter_code)
                     if vals.get('category_id') else vals for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('category_id'):
            vals = dict(vals, adapter_code=self.env['wcs.equipment.category'].browse(vals['category_id']).adapter_code)
        return super().write(vals)

    def action_to_wcs_requests(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': self.env._('WCS作业'), 'res_model': 'wcs.request',
                'view_mode': 'kanban,list,form', 'domain': [('equipment_id', '=', self.id)]}


    @api.constrains('endpoint', 'adapter_code', 'api_key', 'api_secret')
    def _check_connection(self):
        for device in self:
            if device.endpoint:
                url = urlsplit(device.endpoint)
                if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ValidationError(self.env._('Use an HTTP(S) endpoint without credentials or query parameters.'))
            if device.adapter_code == 'hik' and bool(device.api_key) != bool(device.api_secret):
                raise ValidationError(self.env._('Configure both HIK App Key and App Secret.'))

    def _connection_snapshot(self):
        self.ensure_one()
        # Only the private scheduler needs connection secrets; no RPC returns them.
        device = self.sudo()
        result = {key: device[key] for key in ('adapter_code', 'endpoint', 'api_key', 'api_secret')}
        if device.category_id:
            category = device.category_id
            result.update(adapter_code=category.adapter_code,
                          endpoint=(category.ip_post or '').rstrip('/') + (category.submit_path or '') if category.ip_post else device.endpoint,
                          api_key=category.app_key or device.api_key, api_secret=category.app_secret or device.api_secret)
        return result
