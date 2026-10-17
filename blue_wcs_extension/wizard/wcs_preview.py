import json

from odoo import fields, models
from odoo.exceptions import AccessError, ValidationError


class WcsPreview(models.TransientModel):
    _name = 'wcs.preview'
    _description = 'Read-only WCS operation trial'

    profile_id = fields.Many2one('blue.config.profile', '创建配置', required=True)
    picking_id = fields.Many2one('stock.picking', '库存作业', required=True)
    result = fields.Text('试算结果', readonly=True)
    technical_result = fields.Text('技术数据', readonly=True)

    def action_preview(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(self.env._('Only managers can preview draft strategies.'))
        self.profile_id._check_manager()
        if self.profile_id.company_id != self.picking_id.company_id:
            raise ValidationError(self.env._('Choose a picking in the strategy company.'))
        trials = self.picking_id._wcs_preview(self.profile_id)
        lines = []
        for trial in trials:
            if trial.get('waiting'):
                lines.append('等待: ' + trial['waiting'])
                continue
            lines.append('将创建 %s 张WCS作业' % len(trial['tasks']))
            for line in self.picking_id.move_line_ids:
                quantity = trial['quantities'].get(line.id, 0)
                if line.uom_id.compare(quantity, 0) > 0:
                    lines.append('货物: %s; 数量: %s %s; 包裹: %s' % (
                        line.product_id.display_name, quantity, line.uom_id.name,
                        (line.result_package_id if self.picking_id.picking_type_id.code == 'incoming' else line.package_id).name))
            for index, task in enumerate(trial['tasks'], start=1):
                device = self.env['wcs.equipment'].browse(task['equipment_id'])
                source = self.env['stock.location'].browse(task['location_res_id'])
                destination = self.env['stock.location'].browse(task['location_dest_id'])
                event = dict(self.env['wcs.request']._fields['dependency_event']._description_selection(self.env))[task['dependency_event']]
                lines.append('%s. %s: %s (%s) → %s (%s); 设备: %s; 前置: %s; 条件: %s' % (
                    index, dict(self.env['wcs.request']._fields['role']._description_selection(self.env))[task['role']],
                    source.complete_name, task['source_point'], destination.complete_name, task['destination_point'],
                    device.name, task['dependency_step'] or '无', event))
        self.result = '\n'.join(lines) or '当前没有可创建的WCS明细'
        self.technical_result = json.dumps(trials, ensure_ascii=False, indent=2)
        return {'type': 'ir.actions.act_window', 'name': self.env._('WCS真实作业试算'), 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
