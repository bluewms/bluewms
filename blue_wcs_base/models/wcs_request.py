import hashlib
import json
import uuid
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .guard import WCS_TOKEN
from .transport import send


class WcsRequest(models.Model):
    _name = 'wcs.request'
    _description = 'WCS device task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'id desc'

    name = fields.Char('任务编号', required=True, copy=False, default=lambda self: 'WCS-' + uuid.uuid4().hex)
    company_id = fields.Many2one('res.company', required=True)
    plan_id = fields.Many2one('wcs.plan', required=True, check_company=True, ondelete='restrict')
    picking_id = fields.Many2one(related='plan_id.picking_id', store=True)
    equipment_id = fields.Many2one('wcs.equipment', '设备', required=True, check_company=True, ondelete='restrict')
    category_id = fields.Many2one(related='equipment_id.category_id', store=True, string='设备类别')
    picking_type_id = fields.Many2one(related='picking_id.picking_type_id', store=True, string='作业类型')
    location_res_id = fields.Many2one('stock.location', '源位置', check_company=True)
    location_dest_id = fields.Many2one('stock.location', '目的位置', check_company=True)
    package_id = fields.Many2one('stock.package', '包裹', compute='_compute_goods')
    container_id = fields.Many2one('stock.package', '容器', compute='_compute_goods')
    product_id = fields.Many2one('product.product', '产品', compute='_compute_goods')
    product_qty = fields.Float('数量', compute='_compute_goods')
    product_uom_id = fields.Many2one('uom.uom', '单位', compute='_compute_goods')
    lot_id = fields.Many2one('stock.lot', '批次', compute='_compute_goods')
    goods_line_ids = fields.One2many(related='plan_id.line_ids', string='货物明细')
    is_simulation = fields.Boolean(compute='_compute_goods')
    is_package_only = fields.Boolean('仅空包裹', compute='_compute_goods')
    stage_id = fields.Many2one('wcs.stage', '阶段', compute='_compute_stage', store=True, group_expand='_expand_stages')
    owner_user_id = fields.Many2one('res.users', '请求人', default=lambda self: self.env.user)
    user_id = fields.Many2one('res.users', '技术员')
    maintenance_team_id = fields.Many2one('wcs.team', '作业团队', check_company=True)
    priority = fields.Selection([('0', '低'), ('1', '普通'), ('2', '高'), ('3', '紧急')], default='1', string='优先级')
    color = fields.Integer('颜色')
    description = fields.Text('内部注释')
    request_date = fields.Date('请求日期', default=fields.Date.context_today)
    stage_name = fields.Char(related='stage_id.name')
    step = fields.Integer('步骤', required=True)
    role = fields.Selection([('goods', '货物搬运'), ('empty_supply', '空载具供应'), ('empty_return', '空载具回收')], required=True)
    source_point = fields.Char('起点站点', required=True)
    destination_point = fields.Char('目的站点', required=True)
    carrier_code = fields.Char('载具编码')
    goods_mode = fields.Selection([('primary', '首个货物程序'), ('repeat', '同数据后续程序'), ('relay', '连续接力'), ('empty', '空载具配合')], readonly=True)
    source_ref = fields.Char('设备起点映射来源', readonly=True)
    destination_ref = fields.Char('设备终点映射来源', readonly=True)
    source_scope = fields.Boolean('设备起点是库区', readonly=True)
    destination_scope = fields.Boolean('设备终点是库区', readonly=True)
    task_type = fields.Char('设备任务模板', required=True)
    predecessor_id = fields.Many2one('wcs.request', '前置任务', check_company=True, ondelete='restrict')
    dependency_event = fields.Selection([('end', '完成'), ('take', '取货'), ('point', '指定点'), ('point_or_take', '取货或点位通知')], default='end', required=True)
    dependency_point = fields.Char('依赖点位')
    state = fields.Selection([
        ('waiting', '等待前段'), ('pending_send', '待发送'), ('sending', '发送中'),
        ('accepted', '设备已接受'), ('running', '执行中'), ('completed', '已完成'),
        ('unknown', '结果待核对'), ('failed', '未发送失败'), ('cancelled', '发送前取消'),
    ], default='pending_send', required=True, tracking=True)
    dispatch_date = fields.Datetime('发送时间')
    done_date = fields.Datetime('完成时间')
    payload = fields.Text('准确发送报文', readonly=True)
    last_result = fields.Text('发送结果', readonly=True)
    event_ids = fields.One2many('wcs.event', 'request_id', '设备事件')
    _unique_name = models.Constraint('UNIQUE(name)', 'Device task number must be unique.')
    _unique_step = models.Constraint('UNIQUE(plan_id, step)', 'Duplicate WCS plan step.')

    @api.depends('state')
    def _compute_stage(self):
        stages = {stage.code: stage for stage in self.env['wcs.stage'].search([])}
        for task in self:
            task.stage_id = stages.get(task.state, False)

    def _expand_stages(self, stages, domain):
        return stages.search([], order='sequence,id')

    @api.depends('role', 'plan_id.line_ids', 'equipment_id.adapter_code')
    def _compute_goods(self):
        for task in self:
            rows = task.plan_id.line_ids if task.role == 'goods' else self.env['wcs.plan.line']
            products, units, packages, lots = rows.product_id, rows.uom_id, rows.package_id, rows.lot_id
            task.product_id = products if len(products) == 1 else False
            task.product_uom_id = units if len(units) == 1 and len(products) == 1 else False
            task.product_qty = sum(rows.mapped('quantity')) if task.product_uom_id else 0
            task.package_id = packages if len(packages) == 1 else False
            outers = packages.outermost_package_id
            task.container_id = outers if len(outers) == 1 else False
            task.lot_id = lots if len(lots) == 1 else False
            task.is_package_only = task.role != 'goods'
            task.is_simulation = task.equipment_id.adapter_code == 'simulation'

    def action_to_picking_id(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': self.picking_id.id, 'view_mode': 'form'}

    def button_execute(self):
        for task in self:
            task.check_access('write')
            if task.state != 'pending_send':
                raise UserError(self.env._('Only ready tasks can be queued for execution.'))
            task._preflight()
        # Fixed scheduler only; the user cannot choose another cron or code.
        self.env.ref('blue_wcs_base.cron_wcs_dispatch').sudo()._trigger()
        return True

    def archive_equipment_request(self):
        return self.action_cancel_unsent()

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('Use the WCS planning service to create tasks.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('Use WCS workflow actions.'))
        if set(vals) - {'state', 'dispatch_date', 'done_date', 'payload', 'last_result'}:
            raise AccessError(self.env._('Task instructions are immutable.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(self.env._('Keep WCS task history.'))

    def _lock(self):
        self.check_access('read')
        self.flush_recordset()
        # Incrementing a version is not necessary here: state writes force retry on stale snapshots.
        self.env.cr.execute('SELECT id FROM wcs_request WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def _payload(self):
        self.ensure_one()
        details = [{'product_code': row.product_id.default_code or str(row.product_id.id),
                    'quantity': row.quantity, 'uom': row.uom_id.name, 'lot': row.lot_id.name or ''}
                   for row in self.plan_id.line_ids] if self.role == 'goods' else []
        if self.equipment_id.adapter_code == 'hik':
            return {'taskType': self.task_type, 'robotTaskCode': self.name,
                    'targetRoute': [{'type': 'ZONE' if self.source_scope or self.location_res_id.usage == 'view' else 'SITE', 'code': self.source_point}, {'type': 'ZONE' if self.destination_scope or self.location_dest_id.usage == 'view' or self.location_dest_id.location_rank == 'area' else 'SITE', 'code': self.destination_point}],
                    'initPriority': 50, 'extra': {'carrierInfo': [{'carrierCode': self.carrier_code}]} if self.carrier_code else {}}
        return {'task_id': self.name, 'plan_id': self.plan_id.name, 'role': self.role,
                'source': self.source_point, 'destination': self.destination_point,
                'carrier': self.carrier_code or '', 'items': details}

    def _prepared_payload(self):
        self.ensure_one()
        return json.loads(self.payload) if self.payload else self._payload()

    def _preflight(self):
        self.ensure_one()
        plan = self.plan_id
        snapshot = json.loads(plan.snapshot)
        expected_adapter = snapshot.get('adapters', {}).get(str(self.equipment_id.id))
        if expected_adapter and self.equipment_id.adapter_code != expected_adapter:
            raise UserError(self.env._('Device protocol changed; reconcile the fixed task before sending.'))
        if self.equipment_id.adapter_code != 'simulation' and not (self.equipment_id.sudo().callback_token or self.equipment_id.sudo().category_id.callback_token):
            # Fixed device field only: require callback authentication before real dispatch.
            raise UserError(self.env._('Configure device callback authentication before dispatch.'))
        if plan.picking_id.state in ('cancel', 'done') or not self.equipment_id.active:
            raise UserError(self.env._('Operation or device is no longer available.'))
        if (self.location_res_id._blue_stock_blocking_location()
                or self.location_dest_id._blue_stock_blocking_location(receiving=True)):
            raise UserError(self.env._('WCS task locations are blocked.'))
        if self.role == 'goods' and not plan.carrier_id and snapshot.get('contract') in ('wcs_creation/3', 'wcs_creation/4'):
            if not (self.equipment_id.adapter_code == 'simulation'
                    or (self.equipment_id.adapter_code == 'json' and self.equipment_id.supports_loose_goods)):
                raise UserError(self.env._('Device no longer supports these loose goods.'))
        if self.goods_mode == 'repeat' and self.equipment_id.adapter_code != 'simulation' and not self.equipment_id.supports_repeated_goods:
            raise UserError(self.env._('Device no longer supports repeated goods programs.'))
        if (self.source_scope or self.destination_scope) and self.equipment_id.adapter_code not in ('simulation', 'hik') and not self.equipment_id.supports_location_scope:
            raise UserError(self.env._('Device no longer supports area position mappings.'))
        if self.predecessor_id and self.predecessor_id.state != 'completed' and self.dependency_event == 'end':
            raise UserError(self.env._('Complete the predecessor before dispatch.'))
        goods_start = self.role == 'goods' and (snapshot.get('contract') == 'wcs_creation/4' or not self.predecessor_id or self.predecessor_id.role != 'goods')
        if self.role == 'goods':
            if snapshot.get('contract') == 'wcs_creation/4':
                self._check_fixed_carrier()
            for row in plan.line_ids:
                line = row.move_line_id
                if (snapshot.get('settings', {}).get('quantity_basis') == 'confirmed' or snapshot.get('line_decisions', {}).get(str(line.id), {}).get('quantity_basis') == 'confirmed') and not line.picked:
                    raise UserError(self.env._('Actual WCS goods are no longer confirmed.'))
                if line.product_id != row.product_id or line.lot_id != row.lot_id or line.uom_id != row.uom_id or line.uom_id.compare(line.quantity, row.quantity) < 0:
                    raise UserError(self.env._('Planned goods changed; reconcile this plan.'))
                if line.location_id._blue_stock_blocking_location() or line.location_dest_id._blue_stock_blocking_location(receiving=True):
                    raise UserError(self.env._('Stock locations are blocked.'))
                if goods_start and line.picking_id.picking_type_id.code != 'incoming':
                    quants = self.env['stock.quant'].search([
                        ('company_id', '=', self.company_id.id), ('location_id', '=', line.location_id.id),
                        ('product_id', '=', row.product_id.id), ('lot_id', '=', row.lot_id.id),
                        ('package_id', '=', line.package_id.id), ('owner_id', '=', line.owner_id.id)])
                    matching_rows = plan.line_ids.filtered(lambda item: item.product_id == row.product_id and item.lot_id == row.lot_id
                        and item.move_line_id.package_id == line.package_id and item.move_line_id.owner_id == line.owner_id
                        and item.move_line_id.location_id == line.location_id) if snapshot.get('contract') == 'wcs_creation/4' else row
                    required = sum(item.uom_id._compute_quantity(item.quantity, item.product_id.uom_id, round=False) for item in matching_rows)
                    if (row.product_id.uom_id.compare(sum(quants.mapped('quantity')), required) < 0
                            or row.product_id.uom_id.compare(sum(quants.mapped('reserved_quantity')), required) < 0):
                        raise UserError(self.env._('Reserved stock changed before device dispatch.'))
                if goods_start and line.picking_id.picking_type_id.code != 'outgoing' and line.location_dest_id.usage == 'internal':
                    destination = line.location_dest_id.with_context(exclude_sml_ids=set(plan.line_ids.move_line_id.ids))
                    if not destination._check_can_be_used(line.product_id, quantity=line.quantity_product_uom,
                                                        package=row.package_id.outermost_package_id):
                        raise UserError(self.env._('Destination capacity or storage rules changed.'))


    def _check_fixed_carrier(self):
        self.ensure_one()
        plan = self.plan_id
        picking = plan.picking_id
        carrier = plan.carrier_id
        if not carrier:
            return
        current_lines = picking.move_line_ids.filtered(lambda line: line.quantity > 0 and (line.result_package_id if picking.picking_type_id.code == 'incoming' else line.package_id).outermost_package_id == carrier)
        if set(current_lines.ids) != set(plan.line_ids.move_line_id.ids):
            raise UserError(self.env._('Carrier contents changed after planning; reconcile before dispatch.'))
        if picking.picking_type_id.code == 'incoming':
            return
        dimensions = defaultdict(float)
        for row in plan.line_ids:
            line = row.move_line_id
            dimensions[(row.product_id.id, row.lot_id.id, line.package_id.id, line.owner_id.id, line.location_id.id)] += row.uom_id._compute_quantity(row.quantity, row.product_id.uom_id, round=False)
        for quant in carrier.contained_quant_ids:
            key = (quant.product_id.id, quant.lot_id.id, quant.package_id.id, quant.owner_id.id, quant.location_id.id)
            if quant.quantity > 0 and quant.uom_id.compare(dimensions[key], quant.quantity) != 0:
                raise UserError(self.env._('Carrier stock contents changed after planning; reconcile before dispatch.'))

    def _receive_event(self, event_id, event, point='', actual_destination=''):
        self.ensure_one()
        self._lock()
        if type(event_id) is not str or not 1 <= len(event_id) <= 128 or event not in ('start', 'take', 'point', 'end', 'outbin', 'notifyPodArr'):
            raise ValidationError(self.env._('Invalid device event.'))
        content = json.dumps([event, point, actual_destination], separators=(',', ':'))
        existing = self.env['wcs.event'].search([('request_id', '=', self.id), ('external_id', '=', event_id)], limit=1)
        if existing:
            if existing.content_hash != hashlib.sha256(content.encode()).hexdigest():
                raise ValidationError(self.env._('Event ID was reused with different content.'))
            return True
        if self.state in ('waiting', 'pending_send', 'failed', 'cancelled'):
            raise UserError(self.env._('This task has not been sent.'))
        expected_bins = {(row.move_line_id.location_dest_id.agv_map_point or row.move_line_id.location_dest_id.barcode) for row in self.plan_id.line_ids} if self.destination_scope and self.role == 'goods' else set()
        mapped_bin = self.destination_scope and len(expected_bins) == 1 and actual_destination in expected_bins
        if event == 'end' and actual_destination and actual_destination != self.destination_point and not mapped_bin:
            raise ValidationError(self.env._('Unexpected actual destination; reconcile before completing.'))
        self.env['wcs.event'].with_context(blue_wcs_token=WCS_TOKEN).create({
            'request_id': self.id, 'company_id': self.company_id.id, 'external_id': event_id,
            'event': event, 'point': point, 'content_hash': hashlib.sha256(content.encode()).hexdigest()})
        if event == 'end' and self.state != 'completed':
            self.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'completed', 'done_date': fields.Datetime.now()})
        elif event == 'start' and self.state not in ('completed', 'running'):
            self.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'running'})
        followers = self.search([('predecessor_id', '=', self.id), ('state', '=', 'waiting')])
        for follower in followers:
            if (event == 'end' or ((follower.dependency_event == event or (follower.dependency_event == 'point_or_take' and event in ('point','take'))) and (not follower.dependency_point or follower.dependency_point == point))):
                follower.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'pending_send'})
        return True

    def action_simulate_accept(self):
        for task in self:
            task._check_simulation()
            task._lock()
            if task.state != 'pending_send':
                raise UserError(self.env._('Only pending simulated tasks can be accepted.'))
            task._preflight()
            task.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'accepted', 'payload': json.dumps(task._prepared_payload(), ensure_ascii=False)})
        return True

    def action_simulate_end(self):
        for task in self:
            task._check_simulation()
            task._receive_event('sim-end-' + task.name, 'end', actual_destination=task.destination_point)
        return True

    def _check_simulation(self):
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager') or any(device.adapter_code != 'simulation' for device in self.equipment_id):
            raise AccessError(self.env._('Managers can simulate only simulated devices.'))

    def action_open_reconciliation(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(self.env._('Only managers can reconcile device tasks.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'wcs.reconciliation',
                'view_mode': 'form', 'target': 'new', 'context': {'default_request_id': self.id}}

    def action_cancel_unsent(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(self.env._('Only managers can cancel unsent plans.'))
        self.check_access('write')
        for plan in self.plan_id:
            tasks = plan.request_ids.sorted('id')
            for task in tasks:
                task._lock()
            if any(task.state not in ('waiting', 'pending_send', 'failed', 'cancelled') for task in tasks):
                raise UserError(self.env._('A sent plan requires device reconciliation; do not release its quantities.'))
            tasks.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'cancelled'})
        return True

    @api.model
    def _cron_dispatch(self):
        # Own cursors deliberately persist sending before HTTP. A crash leaves an unknown
        # outcome, never a task that appears unsent and can be blindly sent again.
        for unused in range(20):
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, {})
                task = env['wcs.request'].search([('state', '=', 'pending_send')], order='id', limit=1)
                if not task:
                    break
                task._lock()
                if task.state != 'pending_send':
                    continue
                try:
                    task._preflight()
                    payload = task._prepared_payload()
                except UserError as error:
                    task.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'failed', 'last_result': str(error)})
                    cr.commit()  # Own cursor: persist this pre-send failure.
                    continue
                connection = task.equipment_id._connection_snapshot()
                task_id = task.id
                task.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'sending', 'dispatch_date': fields.Datetime.now(), 'payload': json.dumps(payload, ensure_ascii=False)})
                cr.commit()  # Own cursor: durable claim before external side effect.
            state, result = send(connection, payload)
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, {})
                task = env['wcs.request'].browse(task_id)
                task._lock()
                if task.state == 'sending':
                    task.with_context(blue_wcs_token=WCS_TOKEN).write({'state': state, 'last_result': result})
                cr.commit()  # Own cursor: acknowledgement, preserving any earlier callback.
        stale = self.search([('state', '=', 'sending'), ('dispatch_date', '<', fields.Datetime.subtract(fields.Datetime.now(), minutes=10))])
        stale.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'unknown', 'last_result': 'Sender interrupted; reconcile with the device.'})
