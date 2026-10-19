from odoo import api, fields, models
from odoo.exceptions import ValidationError


class WcsEquipmentCategory(models.Model):
    _name = 'wcs.equipment.category'
    _description = '设备类别'
    _inherit = ['mail.thread']
    _check_company_auto = True

    name = fields.Char('类别名称', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    technician_user_id = fields.Many2one('res.users', '负责人', default=lambda self: self.env.user)
    color = fields.Integer('颜色')
    note = fields.Html('注释')
    adapter_code = fields.Selection([('simulation', '模拟设备'), ('hik', 'HikRobot'), ('json', 'JSON接口')], required=True, default='simulation')
    ip_post = fields.Char('IP地址', groups='base.group_system')
    submit_path = fields.Char('任务接口路径', groups='base.group_system', default='/rcs/rtas/api/robot/controller/task/submit')
    app_key = fields.Char('App Key / Token (appId)', groups='base.group_system', copy=False,
                          help='厂商 App Key、appId 或已取得的 Token. 填写 appId 不会自动执行获取 Token 请求.')
    app_secret = fields.Char('App Secret (appSecret)', groups='base.group_system', copy=False,
                             help='厂商 App Secret 或 appSecret, 与 App Key / appId 配套填写.')
    callback_token = fields.Char('回调凭据', groups='base.group_system', copy=False)
    equipment_ids = fields.One2many('wcs.equipment', 'category_id', '设备')
    equipment_count = fields.Integer('设备数量', compute='_compute_counts')
    maintenance_ids = fields.One2many('wcs.request', 'category_id', 'WCS作业')
    maintenance_count = fields.Integer('作业数量', compute='_compute_counts')

    @api.depends('equipment_ids', 'maintenance_ids')
    def _compute_counts(self):
        for category in self:
            category.equipment_count = len(category.equipment_ids)
            category.maintenance_count = len(category.maintenance_ids)

    @api.constrains('submit_path')
    def _check_path(self):
        for category in self:
            if category.submit_path and (not category.submit_path.startswith('/') or category.submit_path.startswith('//') or '?' in category.submit_path or '#' in category.submit_path):
                raise ValidationError(self.env._('Use a relative device API path starting with one slash.'))

    def write(self, vals):
        result = super().write(vals)
        if 'adapter_code' in vals:
            self.equipment_ids.write({'adapter_code': vals['adapter_code']})
        return result
