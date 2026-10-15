import json
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain
from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN


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
        if any({'blue_wcs_generation', 'blue_wcs_policy_fixed', 'blue_wcs_release_id'} & set(vals) for vals in vals_list):
            raise AccessError(self.env._('Do not supply fixed WCS versions directly.'))
        return super().create(vals_list)

    def _wcs_lock(self):
        self.ensure_one()
        self.check_access('write')
        # A real write causes Odoo's repeatable-read retry for stale concurrent planners.
        self.env.cr.execute('UPDATE stock_picking SET blue_wcs_generation = COALESCE(blue_wcs_generation, 0) + 1 WHERE id = %s', [self.id])
        self.invalidate_recordset()

    def _wcs_units(self):
        self.ensure_one()
        if not self.picking_type_id.blue_wcs_enabled or self.state in ('draft', 'cancel', 'done'):
            return []
        positive = self.move_line_ids.filtered(lambda line: line.uom_id.compare(line.quantity, 0) > 0)
        if len(positive) > 200:
            raise UserError(self.env._('WCS planning supports at most 200 product lines per operation.'))
        groups = defaultdict(lambda: self.env['stock.move.line'])
        for line in positive:
            package = line.result_package_id if self.picking_type_id.code == 'incoming' else line.package_id
            if not package:
                # Current migration scope is container/pallet WCS, not loose-item robots.
                continue
            if self.picking_type_id.is_create_wcs_by_container:
                groups['package:%s' % package.outermost_package_id.id] |= line
            else:
                groups['line:%s' % line.id] |= line
        return [(key, lines) for key, lines in sorted(groups.items())]

    def _wcs_available(self, lines):
        self.ensure_one()
        if self.picking_type_id.blue_wcs_ready_mode == 'confirmed' and not all(lines.mapped('picked')):
            return {}, '等待实际数量确认'
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
            package = lines.package_id[:1].outermost_package_id if self.picking_type_id.is_create_wcs_by_container else lines.package_id[:1]
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
        if not device and operation.equipment_category_id:
            devices = self.env['wcs.equipment'].search([('category_id', '=', operation.equipment_category_id.id),
                ('company_id', '=', self.company_id.id)], limit=2)
            if len(devices) == 1:
                device = devices
        if not device or not device.active or device.company_id != self.company_id:
            raise UserError(self.env._('请在原WCS设置中明确选择设备, 设备类别有多个设备时不能自动猜测.'))
        return device

    def _wcs_payload(self, lines, quantities):
        self.ensure_one()
        operation = self.picking_type_id
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
        devices = self.env['wcs.equipment'].search([('company_id', '=', self.company_id.id), ('active', '=', True)], limit=201)
        if len(devices) > 200:
            raise UserError(self.env._('同公司WCS设备超过200项, 请缩小配置范围.'))
        mode = operation.wcs_request_mode
        task_type = operation.task_type or device.task_type
        base = {'equipment_id': device.id, 'location_res_id': source.id, 'location_dest_id': destination.id,
                'role': 'goods', 'task_type': task_type, 'dependency_step': 0, 'dependency_event': 'end',
                'dependency_point': '', 'reason': '原WCS默认创建规则'}
        candidates = [base]
        if mode == 'relay':
            intermediate = operation.wcs_intermediate_location_id
            secondary = operation.wcs_secondary_equipment_id
            candidates = [dict(base, location_dest_id=intermediate.id), dict(base,
                equipment_id=secondary.id, task_type=secondary.task_type,
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
        all_confirmed = all(line.picked for line in self.move_line_ids if line.quantity > 0)
        request = {'picking_id': self.id, 'state': self.state, 'operation': operation.code,
                   'confirmed': all(lines.mapped('picked')), 'all_confirmed': all_confirmed,
                   'default_condition_met': operation.wcs_generate_condition != 'all_picked' or all_confirmed,
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
                        'task_type': item.task_type} for item in devices},
                   'quantities': {str(line.id): quantities.get(line.id, 0) for line in lines}}
        return {'request': request, 'candidates': candidates}

    def _wcs_select(self, payload, profile=None):
        self.ensure_one()
        if profile:
            profile.check_access('read')
            if profile.company_id != self.company_id or profile.hook_code != 'wcs_creation':
                raise ValidationError(self.env._('请选择本公司的WCS创建配置.'))
            code, contract = profile.draft_code, profile.contract
        elif self.blue_wcs_release_id or (not self.blue_wcs_policy_fixed and self.picking_type_id.blue_wcs_profile_id.active_release_id):
            release = self.blue_wcs_release_id or self.picking_type_id.blue_wcs_profile_id.active_release_id
            version = release.version_id
            code, contract = version.code_text, version.contract
        else:
            code, contract = 'result = []\nfor candidate in candidates:\n    if request["ready"] and request["default_condition_met"]:\n        result.append(candidate)', 'wcs_creation/2'
        if contract != 'wcs_creation/2':
            raise UserError(self.env._('旧线路选择版配置已保留在历史中, 请载入新示例并重新验证发布创建配置.'))
        return self.env['blue.extension.contract']._run(code, payload, contract)

    def _wcs_task_values(self, tasks):
        result = []
        for task in tasks:
            source = self.env['stock.location'].browse(task['location_res_id'])
            destination = self.env['stock.location'].browse(task['location_dest_id'])
            device = self.env['wcs.equipment'].browse(task['equipment_id'])
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
        output = []
        for key, lines in self._wcs_units():
            quantities, waiting = self._wcs_available(lines)
            if waiting:
                output.append({'unit': key, 'waiting': waiting})
                continue
            payload = self._wcs_payload(lines, quantities)
            tasks = self._wcs_select(payload, profile)
            output.append({'unit': key, 'quantities': quantities, 'tasks': self._wcs_task_values(tasks),
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
        if not lines or any(not line.result_package_id or (line.product_id.tracking and not line.lot_id) for line in lines):
            raise UserError(self.env._('Enter positive actual quantities, destination packages and required lots.'))
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
        created = self.env['wcs.plan']
        for key, lines in self._wcs_units():
            package = (lines.result_package_id if self.picking_type_id.code == 'incoming' else lines.package_id)[:1]
            if self.picking_type_id.is_create_wcs_by_container:
                package = package.outermost_package_id
            package._wcs_lock_carrier()
            busy = self.env['wcs.plan'].search(Domain('carrier_id', '=', package.id) & Domain('company_id', '=', self.company_id.id)
                & Domain('request_ids.state', 'not in', ['completed', 'cancelled']), limit=1)
            if busy:
                if busy.picking_id != self:
                    raise UserError(self.env._('This carrier is occupied by another WCS plan.'))
                continue
            quantities, waiting = self._wcs_available(lines)
            if waiting:
                continue
            if not self.blue_wcs_policy_fixed:
                profile = self.picking_type_id.blue_wcs_profile_id
                if profile and (not profile.active or not profile.active_release_id):
                    raise UserError(self.env._('Publish the bound WCS strategy before creating tasks.'))
            payload = self._wcs_payload(lines, quantities)
            selected = self._wcs_select(payload)
            if not selected:
                continue
            if not self.blue_wcs_policy_fixed:
                self.with_context(blue_wcs_token=WCS_TOKEN).write({'blue_wcs_policy_fixed': True, 'blue_wcs_release_id': profile.active_release_id.id if profile else False})
            steps = self._wcs_task_values(selected)
            snapshot = {'mode': self.picking_type_id.wcs_request_mode, 'steps': steps,
                        'release_id': self.blue_wcs_release_id.id or False,
                        'adapters': {str(step['equipment_id']): self.env['wcs.equipment'].browse(step['equipment_id']).adapter_code for step in steps}}
            latest = self.env['wcs.plan'].search([('picking_id', '=', self.id), ('unit_key', '=', key)], order='revision desc', limit=1)
            revision = latest.revision + 1 if latest else 1
            plan = self.env['wcs.plan'].with_context(blue_wcs_token=WCS_TOKEN).create({
                'name': '%s / %s / %s' % (self.name, package.name, revision),
                'company_id': self.company_id.id, 'picking_id': self.id, 'unit_key': key,
                'revision': revision, 'carrier_id': package.id, 'snapshot': json.dumps(snapshot, ensure_ascii=False)})
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
            created |= plan
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
                units = picking._wcs_units()
                if units and any(picking._wcs_available(lines)[0] for key, lines in units):
                    raise UserError(self.env._('Plan and complete the WCS quantities before validating inventory.'))
        return super(StockPicking, self.with_context(blue_wcs_token=WCS_TOKEN)).button_validate()
