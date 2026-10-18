import json
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN

from .creation_contract import BASIC_SETTINGS


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    blue_wcs_enabled = fields.Boolean(related='picking_type_id.blue_wcs_enabled')
    blue_wcs_generation = fields.Integer(copy=False)
    blue_wcs_policy_fixed = fields.Boolean(copy=False, readonly=True)
    blue_wcs_release_id = fields.Many2one('blue.config.release', readonly=True, copy=False, check_company=True, ondelete='restrict')

    def write(self, vals):
        if {'blue_wcs_generation', 'blue_wcs_policy_fixed', 'blue_wcs_release_id'} & set(vals) and self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('WCS version fields require the planning service.'))
        if {'picking_type_id', 'company_id', 'location_id', 'location_dest_id'} & set(vals) and any(task.state != 'cancelled' for task in self.wcs_request_ids):
            raise UserError(self.env._('Keep the operation scope fixed while WCS plans exist.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any({'blue_wcs_generation', 'blue_wcs_policy_fixed', 'blue_wcs_release_id', 'blue_wcs_decision_snapshot'} & set(vals) for vals in vals_list):
            raise AccessError(self.env._('Do not supply fixed WCS versions directly.'))
        return super().create(vals_list)

    def _wcs_lock(self):
        self.ensure_one()
        self.check_access('write')
        # A real write causes Odoo's repeatable-read retry for stale concurrent planners.
        self.env.cr.execute('UPDATE stock_picking SET blue_wcs_generation = COALESCE(blue_wcs_generation, 0) + 1 WHERE id = %s', [self.id])
        self.invalidate_recordset()

    def _wcs_strategy(self, profile=None):
        self.ensure_one()
        if profile:
            profile.check_access('read')
            if profile.company_id != self.company_id or profile.hook_code != 'wcs_creation':
                raise ValidationError(self.env._('请选择本公司的WCS AI创建配置.'))
            code, contract = profile.draft_code, profile.contract
        else:
            bound = self.picking_type_id.blue_wcs_profile_id
            release = self.blue_wcs_release_id if self.blue_wcs_policy_fixed else bound.active_release_id
            if not self.blue_wcs_policy_fixed and bound and (not bound.active or not release):
                raise UserError(self.env._('绑定的AI创建配置尚未发布. 请发布或取消绑定后使用基础逐行创建.'))
            if not release:
                return None
            code, contract = release.version_id.code_text, release.version_id.contract
        if contract not in ('wcs_creation/1', 'wcs_creation/2', 'wcs_creation/3', 'wcs_creation/4'):
            raise UserError(self.env._('旧合同的发布和任务历史已保留. 新建任务请绑定/3版AI创建配置, 或取消绑定使用基础逐行创建.'))
        return code, contract

    def _wcs_settings(self, profile=None):
        strategy = self._wcs_strategy(profile)
        if not strategy:
            return dict(BASIC_SETTINGS, quantity_basis='confirmed' if self.picking_type_id.code == 'incoming' else 'reserved')
        if strategy[1] in ('wcs_creation/1', 'wcs_creation/2'):
            operation = self.picking_type_id
            return {'condition': 'all_confirmed' if operation.wcs_generate_condition == 'all_picked' else 'ready',
                    'mode': operation.wcs_request_mode or 'single', 'quantity_basis': 'confirmed' if operation.code == 'incoming' else operation.blue_wcs_ready_mode or 'reserved',
                    'group_by_container': operation.is_create_wcs_by_container}
        return self.env['blue.extension.contract']._run(strategy[0], {
            'request': {'phase': 'configure', 'picking_id': self.id, 'state': self.state,
                        'company_id': self.company_id.id, 'operation': self.picking_type_id.code,
                        'wcs_type': self.picking_type_id.wcs_type,
                        'all_confirmed': all(line.picked for line in self.move_line_ids if line.quantity > 0)},
            'candidates': []}, strategy[1])

    def _wcs_units(self, settings=None):
        self.ensure_one()
        if not self.picking_type_id.blue_wcs_enabled or self.state in ('draft', 'cancel', 'done'):
            return []
        settings = settings or self._wcs_settings()
        positive = self.move_line_ids.filtered(lambda line: line.uom_id.compare(line.quantity, 0) > 0)
        if len(positive) > 200:
            raise UserError(self.env._('WCS planning supports at most 200 product lines per operation.'))
        groups = defaultdict(lambda: self.env['stock.move.line'])
        for line in positive:
            package = line.result_package_id if self.picking_type_id.code == 'incoming' else line.package_id
            key = 'package:%s' % package.outermost_package_id.id if package and settings['group_by_container'] else 'line:%s' % line.id
            groups[key] |= line
        return sorted(groups.items())

    def _wcs_carrier(self, lines):
        packages = lines.result_package_id if self.picking_type_id.code == 'incoming' else lines.package_id
        return packages.outermost_package_id

    def _wcs_busy(self, lines):
        package = self._wcs_carrier(lines)
        if not package:
            return ''
        plans = self.env['wcs.plan'].search([('carrier_id', '=', package.id), ('company_id', '=', self.company_id.id)])
        if any(task.state not in ('completed', 'cancelled') for task in plans.request_ids):
            return '载具存在在途WCS计划, 等待原计划完成或核对'
        if any(task.state == 'completed' for task in plans.filtered(lambda plan: plan.picking_id == self).request_ids):
            raise UserError(self.env._('This carrier has already moved on this operation. Reconcile remaining goods instead of moving it again.'))
        return ''

    def _wcs_available(self, lines, settings=None):
        self.ensure_one()
        settings = settings or self._wcs_settings()
        if settings['quantity_basis'] == 'confirmed' and not all(lines.mapped('picked')):
            return {}, '等待实际数量确认'
        if any(line.company_id != self.company_id for line in lines):
            raise UserError(self.env._('WCS goods must belong to the operation company.'))
        if any(line.state != 'assigned' for line in lines):
            return {}, '等待库存明细分配'
        if any(not line.product_id.is_storable for line in lines):
            raise UserError(self.env._('Every WCS product must be inventory tracked.'))
        if len(lines.location_id) != 1 or len(lines.location_dest_id) != 1:
            raise UserError(self.env._('One physical carrier must have one source and destination.'))
        if lines.location_id._blue_stock_blocking_location() or lines.location_dest_id._blue_stock_blocking_location(receiving=True):
            raise UserError(self.env._('WCS cannot use blocked locations.'))
        if any(bool(line.product_id.tracking) and not line.lot_id for line in lines):
            return {}, '等待批次确认'
        covered = defaultdict(float)
        for row in self.env['wcs.plan.line'].search([('move_line_id', 'in', lines.ids)]):
            if any(task.state != 'cancelled' for task in row.plan_id.request_ids):
                covered[row.move_line_id.id] += row.quantity
        quantities = {line.id: line.quantity - covered[line.id] for line in lines}
        if any(line.uom_id.compare(quantities[line.id], 0) < 0 for line in lines):
            raise UserError(self.env._('Current quantity is below the fixed WCS plan.'))
        if not any(line.uom_id.compare(quantities[line.id], 0) > 0 for line in lines):
            return {}, '数量已由WCS计划覆盖'
        waiting = self._wcs_busy(lines)
        if waiting:
            return {}, waiting
        package = self._wcs_carrier(lines)
        if package:
            all_lines = self.move_line_ids.filtered(lambda line: line.quantity > 0 and
                (line.result_package_id if self.picking_type_id.code == 'incoming' else line.package_id).outermost_package_id == package)
            if set(all_lines.ids) != set(lines.ids):
                raise UserError(self.env._('One carrier contains several product lines. Use an AI container grouping policy or separate the physical carriers before line-by-line creation.'))
        if self.picking_type_id.code != 'incoming':
            for line in lines:
                quants = self.env['stock.quant'].search([
                    ('company_id', '=', self.company_id.id), ('location_id', '=', line.location_id.id),
                    ('product_id', '=', line.product_id.id), ('lot_id', '=', line.lot_id.id),
                    ('package_id', '=', line.package_id.id), ('owner_id', '=', line.owner_id.id)])
                if (line.product_id.uom_id.compare(sum(quants.mapped('quantity')), line.quantity_product_uom) < 0
                        or line.product_id.uom_id.compare(sum(quants.mapped('reserved_quantity')), line.quantity_product_uom) < 0):
                    raise UserError(self.env._('Outbound WCS requires available reserved goods.'))
            # Do not move an outer carrier containing unplanned stock.
            package = self._wcs_carrier(lines)
            dimensions = defaultdict(float)
            for line in lines:
                dimensions[(line.product_id.id, line.lot_id.id, line.package_id.id, line.owner_id.id)] += line.quantity_product_uom
            for quant in package.contained_quant_ids:
                key = (quant.product_id.id, quant.lot_id.id, quant.package_id.id, quant.owner_id.id)
                if quant.uom_id.compare(quant.quantity, 0) > 0 and quant.uom_id.compare(dimensions[key], quant.quantity) != 0:
                    raise UserError(self.env._('Plan all contents before moving an entire carrier.'))
        return quantities, ''

    def _wcs_default_device(self):
        operation = self.picking_type_id
        device = operation.equipment_id
        if (not operation.wcs_type or not operation.equipment_category_id or not operation.task_type
                or not device or not device.active or device.company_id != self.company_id
                or device.category_id != operation.equipment_category_id):
            raise UserError(self.env._('请人工明确选择WCS入库类型、设备类别、设备和任务类型.'))
        return device

    def _wcs_payload(self, lines, quantities, settings=None, profile=None):
        self.ensure_one()
        operation = self.picking_type_id
        settings = settings or self._wcs_settings()
        device = self._wcs_default_device()
        source, destination = lines.location_id, lines.location_dest_id
        locations = (source | destination | source.location_id | destination.location_id |
                     self.location_id | self.location_dest_id | operation.default_location_src_id |
                     operation.default_location_dest_id | operation.wcs_intermediate_location_id)
        warehouse = operation.warehouse_id
        if warehouse:
            scoped = self.env['stock.location'].search([
                ('id', 'child_of', warehouse.view_location_id.id), ('active', '=', True),
                ('company_id', 'in', [False, self.company_id.id])], limit=max(1, 200 - len(locations)))
            locations |= scoped
        locations = locations.filtered(lambda location: location.active and location.company_id in (self.env['res.company'], self.company_id))
        devices = device
        secondary = operation.wcs_secondary_equipment_id if self._wcs_strategy(profile) and operation.wcs_secondary_task_type else self.env['wcs.equipment']
        if secondary:
            if not secondary.active or secondary.company_id != self.company_id or not operation.wcs_secondary_task_type:
                raise UserError(self.env._('附加设备须处于启用状态、属于同公司并人工指定任务类型.'))
            if secondary == device and operation.wcs_secondary_task_type != operation.task_type:
                raise UserError(self.env._('同一设备的主任务和附加任务必须使用同一人工任务类型.'))
            devices |= secondary
        mode = settings['mode']
        task_type = operation.task_type
        base = {'equipment_id': device.id, 'location_res_id': source.id, 'location_dest_id': destination.id,
                'role': 'goods', 'task_type': task_type, 'dependency_step': 0, 'dependency_event': 'end',
                'dependency_point': '', 'reason': '基础逐行直达作业'}
        candidates = [base]
        if mode == 'relay':
            intermediate = operation.wcs_intermediate_location_id
            candidates = [dict(base, location_dest_id=intermediate.id), dict(base,
                equipment_id=secondary.id, task_type=operation.wcs_secondary_task_type,
                location_res_id=intermediate.id, dependency_step=1)] if intermediate and secondary else []
        elif mode == 'double_in':
            # Same endpoints as ZF: goods to the assigned destination parent, empty return from assigned slot.
            place_destination = destination.location_id or destination
            candidates = [dict(base, location_dest_id=place_destination.id), dict(base, role='empty_return',
                location_res_id=destination.id, location_dest_id=source.id, dependency_step=1,
                dependency_event='point_or_take', dependency_point=source.agv_map_point or source.barcode or source.complete_name)]
        elif mode == 'double_out':
            candidates = [dict(base, role='empty_supply', location_res_id=destination.id,
                location_dest_id=(source.location_id or source).id), dict(base, dependency_step=1,
                dependency_event='point_or_take', dependency_point=destination.agv_map_point or destination.barcode or destination.complete_name)]
        if mode == 'relay' and not candidates:
            raise UserError(self.env._('接力策略需要人工选择附加设备、附加任务类型和交接位置.'))
        all_confirmed = all(line.picked for line in self.move_line_ids if line.quantity > 0)
        request = {'phase': 'tasks', 'settings': settings, 'wcs_type': operation.wcs_type, 'task_type': task_type,
                   'secondary_equipment_id': secondary.id or False, 'secondary_task_type': operation.wcs_secondary_task_type or '',
                   'intermediate_location_id': operation.wcs_intermediate_location_id.id or False,
                   'picking_id': self.id, 'state': self.state, 'operation': operation.code,
                   'confirmed': all(lines.mapped('picked')), 'all_confirmed': all_confirmed,
                   'default_condition_met': settings['condition'] != 'all_confirmed' or all_confirmed,
                   'ready': bool(quantities), 'company_id': self.company_id.id,
                   'source_id': source.id, 'destination_id': destination.id,
                   'source_parent_id': source.location_id.id or source.id,
                   'destination_parent_id': destination.location_id.id or destination.id,
                   'equipment_id': device.id, 'mode': mode,
                   'allowed_location_ids': locations.ids, 'allowed_equipment_ids': devices.ids,
                   'allowed_goods_destinations': list(set([destination.id] + ([destination.location_id.id] if mode == 'double_in' else []))),
                   'locations': {str(location.id): {'name': location.complete_name,
                        'parent_id': location.location_id.id or False,
                        'point': location.agv_map_point or location.barcode or ''} for location in locations},
                   'equipment': {str(item.id): {'name': item.name, 'category_id': item.category_id.id or False,
                        'task_type': task_type if item == device else operation.wcs_secondary_task_type} for item in devices},
                   'quantities': {str(line.id): quantities.get(line.id, 0) for line in lines}}
        return {'request': request, 'candidates': candidates}

    def _wcs_select(self, payload, profile=None):
        self.ensure_one()
        strategy = self._wcs_strategy(profile)
        code, contract = strategy or ('result = []\nfor candidate in candidates:\n    if request["ready"]:\n        result.append(candidate)', 'wcs_creation/3')
        if contract == 'wcs_creation/1':
            return self._wcs_legacy_route_select(code, payload)
        result = self.env['blue.extension.contract']._run(code, payload, contract)
        for task in result:
            if task['task_type'] != payload['request']['equipment'][str(task['equipment_id'])]['task_type']:
                raise UserError(self.env._('旧配置任务类型超出人工授权, 请迁移AI创建配置.'))
        return result

    def _wcs_task_values(self, tasks, lines=None):
        result = []
        for task in tasks:
            source = self.env['stock.location'].browse(task['location_res_id'])
            destination = self.env['stock.location'].browse(task['location_dest_id'])
            device = self.env['wcs.equipment'].browse(task['equipment_id'])
            if lines is not None and not self._wcs_carrier(lines) and task['role'] == 'goods':
                if not device._supports_wcs_loose_goods():
                    raise UserError(self.env._('所选设备未支持无容器货物搬运. 请确认JSON网关散件能力或为明细指定实际载具.'))
            if source._blue_stock_blocking_location() or destination._blue_stock_blocking_location(receiving=True):
                raise UserError(self.env._('创建配置不能使用冻结的起点、交接位置或目的位置.'))
            source_point = source.agv_map_point or source.barcode
            destination_point = destination.agv_map_point or destination.barcode
            if device.adapter_code == 'simulation':
                source_point = source_point or source.complete_name
                destination_point = destination_point or destination.complete_name
            if not source_point or not destination_point:
                raise UserError(self.env._('请为WCS起点和目的位置配置AGV地图坐标点或条码.'))
            result.append(dict(task, source_point=source_point, destination_point=destination_point))
        return result

    def _wcs_preview(self, profile=None):
        self.ensure_one()
        self.check_access('read')
        if profile:
            profile.check_access('read')
            if profile.company_id != self.company_id:
                raise ValidationError(self.env._('请选择同公司的创建配置.'))
        if self._wcs_use_v4(profile):
            return self._wcs4_preview(profile)
        output = []
        settings = self._wcs_settings(profile)
        for key, lines in self._wcs_units(settings):
            quantities, waiting = self._wcs_available(lines, settings)
            if waiting:
                output.append({'unit': key, 'waiting': waiting})
                continue
            payload = self._wcs_payload(lines, quantities, settings, profile)
            tasks = self._wcs_select(payload, profile)
            output.append({'unit': key, 'quantities': quantities, 'tasks': self._wcs_task_values(tasks, lines),
                           'waiting': '' if tasks else '创建条件尚未满足', 'input': payload})
        return output

    def action_confirm_wcs_quantities(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_user') or not self.picking_type_id.blue_wcs_enabled:
            raise AccessError(self.env._('Confirm quantities only for enabled WCS operations.'))
        if self.picking_type_id.code != 'incoming' or self.state in ('draft', 'cancel', 'done'):
            raise UserError(self.env._('Confirm actual WCS quantities on an open inbound operation.'))
        lines = self.move_line_ids.filtered(lambda line: line.uom_id.compare(line.quantity, 0) > 0)
        if not lines or any(line.product_id.tracking and not line.lot_id for line in lines):
            raise UserError(self.env._('Enter positive actual quantities and required lots.'))
        lines.write({'picked': True})
        return True

    def action_create_wcs_request_from_button(self):
        self.ensure_one()
        if not self.env.user.has_group('stock.group_stock_user'):
            raise AccessError(self.env._('Inventory users are required to plan WCS.'))
        self.check_access('write')
        self._wcs_lock()
        if not self.picking_type_id.blue_wcs_enabled:
            raise UserError(self.env._('Enable WCS for this operation type first.'))
        if self.state in ('draft', 'cancel', 'done'):
            raise UserError(self.env._('Create WCS tasks only on open confirmed operations.'))
        if self._wcs_use_v4():
            return self._wcs4_create()
        settings = self._wcs_settings()
        for key, lines in self._wcs_units(settings):
            package = self._wcs_carrier(lines)
            if package:
                package._wcs_lock_carrier()
            quantities, waiting = self._wcs_available(lines, settings)
            if waiting:
                continue
            if not self.blue_wcs_policy_fixed:
                profile = self.picking_type_id.blue_wcs_profile_id
                if profile and (not profile.active or not profile.active_release_id):
                    raise UserError(self.env._('Publish the bound WCS strategy before creating tasks.'))
            payload = self._wcs_payload(lines, quantities, settings)
            selected = self._wcs_select(payload)
            if not selected:
                continue
            if not self.blue_wcs_policy_fixed:
                self.with_context(blue_wcs_token=WCS_TOKEN).write({'blue_wcs_policy_fixed': True, 'blue_wcs_release_id': profile.active_release_id.id if profile else False})
            steps = self._wcs_task_values(selected, lines)
            snapshot = {'contract': self._wcs_strategy()[1] if self._wcs_strategy() else 'wcs_creation/3',
                        'legacy_route_id': payload['request'].get('legacy_route_id', False), 'settings': settings, 'mode': settings['mode'], 'steps': steps,
                        'release_id': self.blue_wcs_release_id.id or False,
                        'adapters': {str(step['equipment_id']): self.env['wcs.equipment'].browse(step['equipment_id']).adapter_code for step in steps}}
            latest = self.env['wcs.plan'].search([('picking_id', '=', self.id), ('unit_key', '=', key)], order='revision desc', limit=1)
            revision = latest.revision + 1 if latest else 1
            plan = self.env['wcs.plan'].with_context(blue_wcs_token=WCS_TOKEN).create({
                'name': '%s / %s / %s' % (self.name, package.name or key, revision),
                'company_id': self.company_id.id, 'picking_id': self.id, 'unit_key': key,
                'revision': revision, 'carrier_id': package.id, 'route_id': payload['request'].get('legacy_route_id', False), 'snapshot': json.dumps(snapshot, ensure_ascii=False)})
            self.env['wcs.plan.line'].with_context(blue_wcs_token=WCS_TOKEN).create([
                {'plan_id': plan.id, 'move_line_id': line.id, 'product_id': line.product_id.id,
                 'uom_id': line.uom_id.id, 'quantity': quantities[line.id], 'lot_id': line.lot_id.id,
                 'package_id': (line.result_package_id if self.picking_type_id.code == 'incoming' else line.package_id).id}
                for line in lines if line.uom_id.compare(quantities[line.id], 0) > 0])
            by_step = {}
            for index, step in enumerate(steps, start=1):
                device = self.env['wcs.equipment'].browse(step['equipment_id'])
                dependency = by_step.get(step['dependency_step'])
                values = {key: value for key, value in step.items() if key not in ('dependency_step', 'reason')}
                previous = self.env['wcs.request'].with_context(blue_wcs_token=WCS_TOKEN).create(dict(
                    values, company_id=self.company_id.id, plan_id=plan.id, step=index,
                    carrier_code=package.name if step['role'] == 'goods' else False,
                    predecessor_id=dependency.id if dependency else False, state='waiting' if dependency else 'pending_send',
                    description=step['reason'], maintenance_team_id=device.maintenance_team_id.id))
                by_step[index] = previous
                previous.with_context(blue_wcs_token=WCS_TOKEN).write({'payload': json.dumps(previous._payload(), ensure_ascii=False)})
        return {'type': 'ir.actions.act_window', 'name': self.env._('WCS任务'), 'res_model': 'wcs.request',
                'view_mode': 'kanban,list,form', 'domain': [('picking_id', '=', self.id)]}

    @api.model
    def _cron_create_wcs(self):
        pickings = self.search([('state', '=', 'assigned'), ('picking_type_id.blue_wcs_auto_create', '=', True),
                               ('picking_type_id.blue_wcs_enabled', '=', True)], order='write_date,id', limit=20)
        for picking in pickings:
            try:
                with self.env.cr.savepoint():
                    picking.action_create_wcs_request_from_button()
            except (UserError, ValidationError) as error:
                picking.message_post(body=self.env._('WCS creation paused: %s', str(error)))

    @api.model
    def _cron_validate_wcs(self):
        pickings = self.search([('state', '=', 'assigned'), ('picking_type_id.blue_wcs_enabled', '=', True),
                               ('picking_type_id.blue_wcs_auto_validate', '=', True)], order='write_date,id', limit=20)
        for picking in pickings:
            tasks = picking.wcs_request_ids.filtered(lambda task: task.state != 'cancelled')
            if not tasks or any(task.state != 'completed' for task in tasks):
                continue
            if any(move.uom_id.compare(move.quantity, move.product_uom_qty) != 0 for move in picking.move_ids):
                continue
            try:
                with self.env.cr.savepoint():
                    picking.button_validate()
            except (UserError, ValidationError) as error:
                picking.message_post(body=self.env._('WCS inventory validation paused: %s', str(error)))

    def button_validate(self):
        for picking in self:
            required = picking.picking_type_id.is_wcs_required_for_validate
            live = picking.wcs_request_ids.filtered(lambda task: task.state != 'cancelled')
            if required and not live:
                raise UserError(self.env._('该作业类型的单据必须创建并完成WCS作业后才能验证.'))
            if picking.picking_type_id.blue_wcs_enabled and (required or live):
                covered = defaultdict(float)
                for row in picking.wcs_plan_ids.filtered(lambda plan: any(task.state != 'cancelled' for task in plan.request_ids)).line_ids:
                    covered[row.move_line_id.id] += row.quantity
                if any(line.uom_id.compare(line.quantity, covered[line.id]) > 0 for line in picking.move_line_ids - picking._wcs4_excluded_lines()):
                    raise UserError(self.env._('Plan and complete the WCS quantities before validating inventory.'))
        return super(StockPicking, self.with_context(blue_wcs_token=WCS_TOKEN)).button_validate()
