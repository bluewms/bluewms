from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    blue_wcs_enabled = fields.Boolean('启用WCS', default=False)
    wcs_type = fields.Selection([('in', '入库'), ('out', '出库')], string='WCS入库类型')
    wcs_generate_condition = fields.Selection([('partial_picked', '部分已拣选'), ('all_picked', '全部已拣选')],
                                             default='partial_picked', string='WCS生成条件')
    equipment_category_id = fields.Many2one('wcs.equipment.category', '设备类别', check_company=True)
    equipment_id = fields.Many2one('wcs.equipment', '设备', check_company=True, domain="[('category_id','=',equipment_category_id)]")
    task_type = fields.Char('任务类型')
    auto_create_wcs_request_execute = fields.Boolean('自动创建WCS作业并执行')
    is_auto_validate = fields.Boolean('WCS完成后自动验证')
    is_wcs_required_for_validate = fields.Boolean('验证前必须存在WCS作业', default=False)
    wcs_request_mode = fields.Selection([('single', '单作业'), ('double_in', '入库双作业'),
                                        ('double_out', '出库双作业'), ('relay', '同货两段接力')], default='single', string='WCS作业模式')
    is_create_wcs_by_container = fields.Boolean('按容器生成WCS任务')
    wcs_secondary_equipment_id = fields.Many2one('wcs.equipment', '接力设备', check_company=True)
    wcs_secondary_task_type = fields.Char('附加设备任务类型', help='人工授权的附加设备任务类型, AI不能替换.')
    wcs_intermediate_location_id = fields.Many2one('stock.location', '接力交接位置', check_company=True)
    blue_wcs_auto_create = fields.Boolean(related='auto_create_wcs_request_execute', readonly=False)
    blue_wcs_auto_validate = fields.Boolean(related='is_auto_validate', readonly=False)
    blue_wcs_profile_id = fields.Many2one('blue.config.profile', 'AI创建配置', check_company=True, domain="[('hook_code','=','wcs_creation'),('company_id','=',company_id)]")
    blue_wcs_ready_mode = fields.Selection([('confirmed', '实际确认数量'), ('reserved', '完成前的有效预留数量')], default='confirmed', string='创建数量依据')

    @api.onchange('equipment_category_id')
    def _onchange_equipment_category_id(self):
        if self.equipment_id and self.equipment_id.category_id != self.equipment_category_id:
            self.equipment_id = False

    @api.constrains('blue_wcs_profile_id', 'equipment_id', 'equipment_category_id')
    def _check_wcs_policy(self):
        for operation in self:
            if operation.blue_wcs_profile_id and operation.blue_wcs_profile_id.hook_code != 'wcs_creation':
                raise ValidationError(self.env._('请选择WCS AI创建配置.'))
            if operation.equipment_category_id and operation.equipment_id.category_id != operation.equipment_category_id and operation.equipment_id:
                raise ValidationError(self.env._('设备必须属于所选设备类别.'))
