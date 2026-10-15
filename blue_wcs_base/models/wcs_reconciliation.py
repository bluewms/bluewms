import uuid

from odoo import fields, models
from odoo.exceptions import AccessError, UserError

from .guard import WCS_TOKEN


class WcsReconciliation(models.TransientModel):
    _name = 'wcs.reconciliation'
    _description = 'Explicit device outcome reconciliation'

    request_id = fields.Many2one('wcs.request', '任务', required=True)
    outcome = fields.Selection([('accepted', '设备已接受'), ('completed', '设备已完成且目的地已核对'),
                                ('not_accepted', '设备确认未接受，可按原任务号发送')], required=True)
    evidence = fields.Text('设备查询结果 / 现场核对依据', required=True)

    def action_apply(self):
        self.ensure_one()
        self.check_access('write')
        task = self.request_id
        task.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(self.env._('Only inventory managers can reconcile device outcomes.'))
        if not self.evidence or not 20 <= len(self.evidence.strip()) <= 4096:
            raise UserError(self.env._('Record 20 to 4096 characters of device/physical verification evidence.'))
        task._lock()
        if task.state not in ('unknown', 'sending', 'failed', 'accepted', 'running'):
            raise UserError(self.env._('This task does not require device outcome reconciliation.'))
        if self.outcome == 'completed':
            if task.state == 'failed':
                raise UserError(self.env._('An unsent failure cannot be completed.'))
            task._receive_event('manual-' + uuid.uuid4().hex, 'end', actual_destination=task.destination_point)
        elif self.outcome == 'accepted':
            if task.state == 'failed':
                raise UserError(self.env._('An unsent failure cannot be accepted.'))
            task.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'accepted'})
        else:
            if task.state in ('accepted', 'running'):
                raise UserError(self.env._('Do not resend a task known to be accepted or running.'))
            task._preflight()
            task.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'pending_send'})
        task.message_post(body=self.env._('Device outcome %(outcome)s verified: %(evidence)s', outcome=self.outcome, evidence=self.evidence))
        return {'type': 'ir.actions.act_window_close'}
