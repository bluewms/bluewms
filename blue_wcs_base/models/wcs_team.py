from odoo import fields, models


class WcsTeam(models.Model):
    _name = 'wcs.team'
    _description = '作业团队'
    _check_company_auto = True
    _order = 'sequence,id'

    name = fields.Char('团队名称', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    member_ids = fields.Many2many('res.users', string='团队成员')
    category_id = fields.Many2one('wcs.equipment.category', '设备类别', check_company=True)
    sequence = fields.Integer('序号', default=20)
    color = fields.Integer('颜色')
