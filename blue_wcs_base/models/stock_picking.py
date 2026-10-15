from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    wsc_request_count = fields.Integer('WCS作业数量', compute='_compute_wcs_summary')
    wcs_stage = fields.Selection([('in_progress', '进行中'), ('partial_done', '部分完成'), ('done', '完成')],
                                 string='WCS状态', compute='_compute_wcs_summary')

    @api.depends('wcs_request_ids.state')
    def _compute_wcs_summary(self):
        for picking in self:
            tasks = picking.wcs_request_ids.filtered(lambda task: task.state != 'cancelled')
            picking.wsc_request_count = len(picking.wcs_request_ids)
            done = sum(task.state == 'completed' for task in tasks)
            picking.wcs_stage = 'done' if tasks and done == len(tasks) else ('partial_done' if done else ('in_progress' if tasks else False))

    def action_to_blue_wcs_request(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': self.env._('WCS作业'), 'res_model': 'wcs.request',
                'view_mode': 'kanban,list,form', 'domain': [('picking_id', '=', self.id)]}

    wcs_plan_ids = fields.One2many('wcs.plan', 'picking_id', 'WCS计划')
    wcs_request_ids = fields.One2many('wcs.request', 'picking_id', 'WCS任务')

    def write(self, vals):
        if vals.get('state') == 'cancel' and any(task.state != 'cancelled' for task in self.wcs_request_ids):
            raise UserError(self.env._('Cancel or reconcile WCS tasks before cancelling the stock operation.'))
        return super().write(vals)

    def action_cancel(self):
        if any(task.state != 'cancelled' for task in self.wcs_request_ids):
            raise UserError(self.env._('Do not cancel inventory while WCS may still move the carrier.'))
        return super().action_cancel()

    def button_validate(self):
        for picking in self:
            live = picking.wcs_request_ids.filtered(lambda task: task.state != 'cancelled')
            if live and any(task.state != 'completed' for task in live):
                raise UserError(self.env._('Complete all WCS plan steps before validating inventory.'))
        return super().button_validate()
