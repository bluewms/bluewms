import json
import uuid

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools.contract import ProtocolError, run_mapping
from .guard import ERP_TOKEN, internal, manager


class BlueErpEvent(models.Model):
    _name = 'blue.erp.event'
    _description = 'ERP 同步事件'
    _order = 'id desc'
    _check_company_auto = True
    _rec_name = 'event_key'

    interface_id = fields.Many2one('blue.erp.interface', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True)
    document_id = fields.Many2one('blue.erp.document', 'ERP 来源单据', check_company=True, ondelete='restrict')
    picking_id = fields.Many2one('stock.picking', 'WMS 单据', check_company=True, ondelete='restrict')
    event_key = fields.Char('事件 ID', required=True, default=lambda self: str(uuid.uuid4()), copy=False, index=True)
    source_key = fields.Char(required=True)
    release_id = fields.Many2one('blue.config.release', '固定代码版本', required=True, check_company=True, ondelete='restrict')
    input_snapshot = fields.Json('准确输入快照', required=True)
    state = fields.Selection([('queued', '待发送'), ('sending', '发送中'), ('failed', '失败'), ('unknown', '待核对'), ('done', '成功')],
                              default='queued', required=True)
    result = fields.Char('处理结果')
    delivery_ids = fields.One2many('blue.erp.delivery', 'event_id', '外部操作记录')
    _unique_source = models.Constraint('UNIQUE(interface_id, source_key)', '此完成事件已经入队.')
    _unique_event = models.Constraint('UNIQUE(event_key)', '事件 ID 必须唯一.')

    @api.model_create_multi
    def create(self, vals_list):
        internal(self)
        return super().create(vals_list)

    def write(self, vals):
        internal(self)
        if set(vals) - {'state', 'result'}:
            raise AccessError(self.env._('ERP 事件快照不可修改.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_history(self):
        raise AccessError(self.env._('ERP 事件须保留追溯.'))

    @api.model
    def _enqueue(self, interface, release, phase, rows, source_key, document=None, picking=None):
        existing = self.search([('interface_id', '=', interface.id), ('source_key', '=', source_key)], limit=1)
        if existing:
            return existing
        key = str(uuid.uuid4())
        snapshot = interface._payload(phase, candidates=rows, event_key=key,
            external_id=document.external_id if document else '', number=document.number if document else key)
        return self.with_context(blue_erp_token=ERP_TOKEN).create({
            'interface_id': interface.id, 'company_id': interface.company_id.id,
            'release_id': release.id, 'source_key': source_key, 'event_key': key,
            'input_snapshot': snapshot, 'document_id': document.id if document else False,
            'picking_id': picking.id if picking else False})

    def _prepare(self):
        self.ensure_one()
        if self.delivery_ids or self.state != 'queued':
            return
        interface = self.interface_id
        scope = json.loads(self.release_id.snapshot)['scope']['erp_scope']
        if not interface.active or not interface.connection_id.active or scope != interface._scope():
            raise UserError(self.env._('接口连接或业务范围已变化,事件尚未发送.'))
        actions = run_mapping(self.release_id.version_id.code_text, self.input_snapshot)['actions']
        values = []
        for index, action in enumerate(actions, 1):
            if action['operation'] not in scope['operations']:
                raise ValidationError(self.env._('代码引用了未批准的 ERP 操作.'))
            values.append({'event_id': self.id, 'company_id': self.company_id.id, 'sequence': index,
                'operation': action['operation'], 'path': scope['operations'][action['operation']],
                'body': action['body'], 'headers': action.get('headers', {})})
        self.env['blue.erp.delivery'].with_context(blue_erp_token=ERP_TOKEN).create(values)

    def _refresh_state(self):
        self.ensure_one()
        states = set(self.delivery_ids.mapped('state'))
        state = ('unknown' if 'unknown' in states else 'sending' if 'sending' in states else
                 'failed' if 'failed' in states else 'done' if states == {'done'} else 'queued')
        self.with_context(blue_erp_token=ERP_TOKEN).write({'state': state})

    def action_retry(self):
        manager(self)
        for event in self:
            if event.state != 'failed' or event.delivery_ids:
                raise UserError(self.env._('仅未生成外部操作的失败事件可重新准备. 已发送操作请逐步核对.'))
            event.with_context(blue_erp_token=ERP_TOKEN).write({'state': 'queued', 'result': False})

    @api.model
    def _cron_dispatch(self):
        # Own cursors persist intent before HTTP, so process death never looks unsent.
        for unused in range(10):
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, {})
                cr.execute("SELECT id FROM blue_erp_event WHERE state = 'queued' AND NOT EXISTS "
                           "(SELECT 1 FROM blue_erp_delivery d WHERE d.event_id = blue_erp_event.id) "
                           "ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1")
                row = cr.fetchone()
                if not row:
                    break
                event = env['blue.erp.event'].browse(row[0])
                try:
                    with cr.savepoint():
                        event.with_company(event.company_id)._prepare()
                except (UserError, ValidationError, ProtocolError):
                    event.with_context(blue_erp_token=ERP_TOKEN).write({'state': 'failed', 'result': '代码或配置未通过校验,没有发送 ERP 请求.'})
                cr.commit()  # Own cursor: persist preparation or safe pre-send failure.
        for unused in range(20):
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, {})
                # Fixed SQL claims one step, preserving order within event and source document.
                cr.execute("SELECT d.id FROM blue_erp_delivery d JOIN blue_erp_event e ON e.id=d.event_id "
                    "WHERE d.state='pending' AND NOT EXISTS (SELECT 1 FROM blue_erp_delivery p "
                    "WHERE p.event_id=d.event_id AND p.sequence<d.sequence AND p.state!='done') "
                    "AND NOT EXISTS (SELECT 1 FROM blue_erp_event prior WHERE prior.document_id=e.document_id "
                    "AND prior.id<e.id AND prior.state!='done') ORDER BY d.id FOR UPDATE OF d SKIP LOCKED LIMIT 1")
                row = cr.fetchone()
                if not row:
                    break
                delivery = env['blue.erp.delivery'].browse(row[0])
                delivery_id = delivery.id
                try:
                    connection = delivery.with_company(delivery.company_id)._connection()
                except (UserError, ValidationError, ProtocolError):
                    delivery._finish('failed', result='连接配置不匹配,尚未发送.')
                    cr.commit()  # Own cursor: persist a safe failure before network access.
                    continue
                code = delivery.event_id.release_id.version_id.code_text
                snapshot = delivery.event_id.input_snapshot
                operation, body, headers = delivery.operation, delivery.body, delivery.headers
                delivery.with_context(blue_erp_token=ERP_TOKEN).write({'state': 'sending', 'sent_at': fields.Datetime.now()})
                delivery.event_id._refresh_state()
                cr.commit()  # Own cursor: durable sending claim before external side effect.
            from ..tools.transport import send
            outcome, external_number = send(connection, operation, body, headers, code, snapshot)
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, {})
                delivery = env['blue.erp.delivery'].browse(delivery_id)
                delivery._lock()
                if delivery.state == 'sending':
                    delivery._finish(outcome, external_number=external_number)
                cr.commit()  # Own cursor: persist acknowledgement independently of stock work.
        stale = self.env['blue.erp.delivery'].search([('state', '=', 'sending'),
            ('sent_at', '<', fields.Datetime.subtract(fields.Datetime.now(), minutes=10))])
        for delivery in stale:
            delivery._lock()
            if delivery.state == 'sending':
                delivery._finish('unknown', result='发送进程中断,请向 ERP 核对结果后再处理.')
