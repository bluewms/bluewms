from odoo import fields, models


class WcsStage(models.Model):
    _name = 'wcs.stage'
    _description = 'WCS作业阶段'
    _order = 'sequence,id'

    name = fields.Char('名称', required=True)
    sequence = fields.Integer('序号', default=20)
    fold = fields.Boolean('是否折叠')
    code = fields.Char('流程代码', required=True, readonly=True)
    done = fields.Boolean('已结束', readonly=True)
    is_in_progres = fields.Boolean('是否进行中', readonly=True)
    _unique_code = models.Constraint('UNIQUE(code)', 'Stage codes must be unique.')
