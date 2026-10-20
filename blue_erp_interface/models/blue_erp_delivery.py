import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .guard import ERP_TOKEN, internal, manager


class BlueErpDelivery(models.Model):
    _name = 'blue.erp.delivery'
    _description = 'ERP 外部操作记录'
    _order = 'event_id desc, sequence'
    _check_company_auto = True

    event_id = fields.Many2one('blue.erp.event', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True)
    sequence = fields.Integer('步骤', required=True)
    operation = fields.Char('操作代码', required=True)
    path = fields.Char('固定请求路径', required=True)
    body = fields.Json('准确发送报文', required=True)
    headers = fields.Json('请求头凭据引用', default=dict)
    state = fields.Selection([('pending', '待发送'), ('sending', '发送中'), ('failed', '明确失败'), ('unknown', '待核对'), ('done', '成功')],
                              required=True, default='pending')
    sent_at = fields.Datetime('发送时间')
    external_number = fields.Char('ERP 返回单号')
    result = fields.Char('处理结果')
    reconciliation_note = fields.Char('人工核对说明', copy=False)
    history = fields.Json('操作历史', default=list)
    _unique_step = models.Constraint('UNIQUE(event_id, sequence)', '同一事件步骤不能重复.')

    @api.model_create_multi
    def create(self, vals_list):
        internal(self)
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) == {'reconciliation_note'}:
            manager(self)
        elif self.env.context.get('blue_erp_token') is ERP_TOKEN:
            if set(vals) - {'state', 'sent_at', 'external_number', 'result', 'history'}:
                raise AccessError(self.env._('外部操作的请求快照不可修改.'))
        else:
            raise AccessError(self.env._('请通过 ERP 核对按钮操作发送状态.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_history(self):
        raise AccessError(self.env._('外部操作记录须保留.'))

    def _lock(self):
        self.ensure_one()
        self.flush_recordset()
        self.env.cr.execute('SELECT id FROM blue_erp_delivery WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def _connection(self):
        self.ensure_one()
        interface = self.event_id.interface_id
        scope = json.loads(self.event_id.release_id.snapshot)['scope']['erp_scope']
        if not interface.active or not interface.connection_id.active or scope != interface._scope():
            raise UserError(self.env._('ERP 连接或批准范围已改变.'))
        # Exact private credentials for this step's already authorized connection only.
        connection = interface.connection_id.sudo()
        return {'url': connection.base_url.rstrip('/') + self.path, 'app_key': connection.app_key or '',
                'app_secret': connection.app_secret or '', 'auth_mode': connection.auth_mode,
                'idempotency_key': self.event_id.event_key + ':' + str(self.sequence)}

    def _finish(self, state, external_number='', result=''):
        self.ensure_one()
        history = list(self.history or [])
        history.append({'state': state, 'at': fields.Datetime.to_string(fields.Datetime.now()),
                        'user_id': self.env.uid, 'note': result})
        self.with_context(blue_erp_token=ERP_TOKEN).write({'state': state, 'external_number': external_number,
            'result': result or {'done': 'ERP 已确认成功.', 'failed': 'ERP 明确拒绝,请核对.',
                                 'unknown': '结果不明确,请向 ERP 核对,勿盲目重发.'}[state], 'history': history[-100:]})
        self.event_id._refresh_state()

    def action_confirm_done(self):
        manager(self)
        for delivery in self:
            delivery._lock()
            if delivery.state != 'unknown' or not delivery.reconciliation_note:
                raise UserError(self.env._('请先填写核对说明,确认 ERP 已处理此待核对操作.'))
            delivery._finish('done', result=delivery.reconciliation_note)

    def action_confirm_not_sent(self):
        manager(self)
        for delivery in self:
            delivery._lock()
            if delivery.state not in ('unknown', 'failed') or not delivery.reconciliation_note:
                raise UserError(self.env._('请先确认 ERP 未处理,填写核对说明后重新排队.'))
            history = list(delivery.history or [])
            history.append({'state': 'pending', 'at': fields.Datetime.to_string(fields.Datetime.now()),
                            'user_id': self.env.uid, 'note': delivery.reconciliation_note})
            delivery.with_context(blue_erp_token=ERP_TOKEN).write({'state': 'pending', 'result': '人工确认 ERP 未处理后重新排队.',
                                                                  'history': history[-100:]})
            delivery.event_id._refresh_state()
