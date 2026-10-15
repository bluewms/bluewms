from odoo import api, fields, models
from odoo.exceptions import ValidationError


class WcsRoute(models.Model):
    _name = 'wcs.route'
    _description = 'Approved WCS route'
    _check_company_auto = True

    name = fields.Char('路线名称', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    picking_type_id = fields.Many2one('stock.picking.type', '作业类型', required=True, check_company=True)
    source_id = fields.Many2one('stock.location', '库存起点', required=True, check_company=True)
    destination_id = fields.Many2one('stock.location', '库存目的地', required=True, check_company=True)
    equipment_id = fields.Many2one('wcs.equipment', '第一段设备', required=True, check_company=True)
    second_equipment_id = fields.Many2one('wcs.equipment', '第二段设备', check_company=True)
    mode = fields.Selection([('single', '单段搬运'), ('relay', '同货两段接力'), ('double_in', '放货及空载具回收'), ('double_out', '空载具供应及搬货')], required=True, default='single')
    source_point = fields.Char('起点站点编码', required=True)
    destination_point = fields.Char('目的站点编码', required=True)
    intermediate_point = fields.Char('交接 / 空载具站点编码')
    dependency_event = fields.Selection([('end', '前段完成'), ('take', '已取货'), ('point', '到达指定点')], required=True, default='end')
    dependency_point = fields.Char('释放后段的指定点编码')
    sequence = fields.Integer(default=10)

    @api.constrains('mode', 'second_equipment_id', 'intermediate_point', 'dependency_event', 'dependency_point', 'source_id', 'destination_id')
    def _check_route(self):
        for route in self:
            if route.source_id == route.destination_id:
                raise ValidationError(self.env._('Source and destination must differ.'))
            if route.mode != 'single' and (not route.second_equipment_id or not route.intermediate_point):
                raise ValidationError(self.env._('Two-task routes need a second device and intermediate point.'))
            if route.mode == 'relay' and route.dependency_event != 'end':
                raise ValidationError(self.env._('Same-goods relay requires the first leg to complete.'))
            if route.dependency_event != 'end' and not route.dependency_point:
                raise ValidationError(self.env._('Early release needs an explicitly approved event point.'))
            if route.mode == 'double_in' and route.picking_type_id.code == 'outgoing':
                raise ValidationError(self.env._('Inbound paired tasks cannot use an outbound operation type.'))
            if route.mode == 'double_out' and route.picking_type_id.code == 'incoming':
                raise ValidationError(self.env._('Outbound paired tasks cannot use an inbound operation type.'))
