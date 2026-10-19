import json
from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN

from .creation_v4 import BASIC_V4_CODE


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    blue_wcs_decision_snapshot = fields.Json('WCS逐行决策', readonly=True, copy=False)

    def write(self, vals):
        if 'blue_wcs_decision_snapshot' in vals and self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            raise AccessError(self.env._('Line decisions require the WCS planning service.'))
        return super().write(vals)

    def _wcs_use_v4(self, profile=None):
        strategy = self._wcs_strategy(profile)
        return not strategy or strategy[1] == 'wcs_creation/4'

    def _wcs4_fingerprint(self, line):
        return {name: line[name].id if line._fields[name].type == 'many2one' else line[name]
                for name in ('product_id', 'lot_id', 'uom_id', 'quantity', 'location_id', 'location_dest_id',
                             'package_id', 'result_package_id', 'owner_id', 'picked')}

    def _wcs4_covered(self):
        covered = defaultdict(float)
        rows = self.env['wcs.plan.line'].search([('move_line_id', 'in', self.move_line_ids.ids)])
        for row in rows:
            if any(task.state != 'cancelled' for task in row.plan_id.request_ids):
                covered[row.move_line_id.id] += row.quantity
        return covered

    def _wcs4_input(self):
        self.ensure_one()
        lines = self.move_line_ids.filtered(lambda row: row.uom_id.compare(row.quantity, 0) > 0).sorted('id')
        if len(lines) > 200:
            raise UserError(self.env._('WCS planning supports at most 200 product lines per operation.'))
        covered = self._wcs4_covered()
        carriers = defaultdict(lambda: self.env['stock.move.line'])
        for line in lines:
            carriers[self._wcs_carrier(line).id or -line.id] |= line
        candidates = []
        for line in lines:
            amount = line.quantity - covered[line.id]
            if line.uom_id.compare(amount, 0) < 0:
                raise UserError(self.env._('Current quantity is below the fixed WCS plan.'))
            carrier = self._wcs_carrier(line)
            siblings = carriers[carrier.id or -line.id]
            quantities = [(row, row.uom_id._compute_quantity(row.quantity, row.product_id.uom_id, round=False)) for row in siblings]
            quants = self.env['stock.quant'].search([('company_id', '=', self.company_id.id), ('location_id', '=', line.location_id.id),
                ('product_id', '=', line.product_id.id), ('lot_id', '=', line.lot_id.id), ('package_id', '=', line.package_id.id), ('owner_id', '=', line.owner_id.id)]) if self.picking_type_id.code != 'incoming' else self.env['stock.quant']
            candidates.append({
                'line_id': line.id, 'line_key': 'line:%s' % line.id,
                'carrier_id': carrier.id or False, 'carrier_key': 'package:%s' % carrier.id if carrier else 'line:%s' % line.id,
                'route_key': 'route:%s:%s:%s' % (carrier.id or 0, line.location_id.id, line.location_dest_id.id),
                'product_id': line.product_id.id, 'product_code': line.product_id.default_code or '',
                'lot_id': line.lot_id.id or False, 'owner_id': line.owner_id.id or False, 'uom_id': line.uom_id.id,
                'quantity': line.quantity, 'covered_quantity': covered[line.id], 'available_quantity': max(0, amount),
                'picked': line.picked, 'stock_state': line.state,
                'stock_quantity': sum(quants.mapped('quantity')), 'reserved_quantity': sum(quants.mapped('reserved_quantity')),
                'company_valid': line.company_id == self.company_id, 'storable': line.product_id.is_storable,
                'lot_ready': not line.product_id.tracking or bool(line.lot_id),
                'source_blocked': bool(line.location_id._blue_stock_blocking_location()),
                'destination_blocked': bool(line.location_dest_id._blue_stock_blocking_location(receiving=True)),
                'source_id': line.location_id.id, 'destination_id': line.location_dest_id.id,
                'carrier_all_picked': all(siblings.mapped('picked')),
                'carrier_same_uom': len(siblings.uom_id) == 1,
                'carrier_quantity': sum(siblings.mapped('quantity')) if len(siblings.uom_id) == 1 else False,
                'carrier_weight': sum(qty * row.product_id.weight for row, qty in quantities),
                'carrier_weight_complete': all(row.product_id.weight > 0 for row in siblings),
                'carrier_volume': sum(qty * row.product_id.volume for row, qty in quantities),
                'carrier_volume_complete': all(row.product_id.volume > 0 for row in siblings),
                'package_max_weight': carrier.package_type_id.max_weight or False,
                'package_type_id': carrier.package_type_id.id or False,
            })
        request = {'phase': 'lines', 'picking_id': self.id, 'state': self.state, 'company_id': self.company_id.id,
                   'operation': self.picking_type_id.code, 'wcs_type': self.picking_type_id.wcs_type,
                   'all_confirmed': all(lines.mapped('picked')), 'picking_source_id': self.location_id.id,
                   'picking_destination_id': self.location_dest_id.id}
        return {'request': request, 'candidates': candidates}

    def _wcs4_run(self, payload, profile=None):
        strategy = self._wcs_strategy(profile) or (BASIC_V4_CODE, 'wcs_creation/4')
        return self.env['blue.extension.contract']._run(strategy[0], payload, strategy[1])

    def _wcs4_positions(self, lines):
        source, destination = lines.location_id, lines.location_dest_id
        return {'line_source': source.id if len(source) == 1 else False,
                'line_destination': destination.id if len(destination) == 1 else False,
                'picking_source': self.location_id.id, 'picking_destination': self.location_dest_id.id,
                'source_parent': source.location_id.id if len(source.location_id) == 1 else False,
                'destination_parent': destination.location_id.id if len(destination.location_id) == 1 else False,
                'handoff': self.picking_type_id.wcs_intermediate_location_id.id or False}

    def _wcs4_safety(self, lines, decisions, profile=None):
        for line in lines:
            decision = decisions[line.id]
            if line.company_id != self.company_id:
                raise UserError(self.env._('WCS goods must belong to the operation company.'))
            if line.state != 'assigned':
                return '等待库存明细分配'
            if not line.product_id.is_storable:
                raise UserError(self.env._('Every WCS product must be inventory tracked.'))
            if (self.picking_type_id.code == 'incoming' or decision['quantity_basis'] == 'confirmed') and not line.picked:
                return '等待实际数量确认'
            if line.product_id.tracking and not line.lot_id:
                return '等待批次确认'
            if line.location_id._blue_stock_blocking_location() or line.location_dest_id._blue_stock_blocking_location(receiving=True):
                raise UserError(self.env._('WCS cannot use blocked locations.'))
        carrier = self._wcs_carrier(lines)
        if len(carrier) > 1 or (carrier and any(not self._wcs_carrier(line) for line in lines)):
            raise UserError(self.env._('Do not combine different physical carriers in one WCS movement.'))
        waiting = self._wcs_busy(lines)
        if waiting:
            return waiting
        if carrier:
            siblings = self.move_line_ids.filtered(lambda row: row.quantity > 0 and self._wcs_carrier(row) == carrier)
            if set(siblings.ids) != set(lines.ids):
                if not self._wcs_strategy(profile):
                    raise UserError(self.env._('One carrier contains several product lines. Use an AI container grouping policy or separate the physical carriers before line-by-line creation.'))
                return '等待同载具全部有效货物纳入计划, 不能随载具移动未计划货物'
            if any(line.uom_id.compare(decisions[line.id]['quantity'], line.quantity) != 0 for line in lines):
                raise UserError(self.env._('Plan the complete carrier quantities; do not split a physical carrier.'))
        dimensions = defaultdict(float)
        for line in lines:
            required = line.uom_id._compute_quantity(decisions[line.id]['quantity'], line.product_id.uom_id, round=False)
            key = (line.product_id.id, line.lot_id.id, line.package_id.id, line.owner_id.id, line.location_id.id)
            dimensions[key] += required
        if self.picking_type_id.code != 'incoming':
            for (product_id, lot_id, package_id, owner_id, location_id), required in dimensions.items():
                product = self.env['product.product'].browse(product_id)
                quants = self.env['stock.quant'].search([('company_id', '=', self.company_id.id), ('location_id', '=', location_id),
                    ('product_id', '=', product_id), ('lot_id', '=', lot_id), ('package_id', '=', package_id), ('owner_id', '=', owner_id)])
                if product.uom_id.compare(sum(quants.mapped('quantity')), required) < 0 or product.uom_id.compare(sum(quants.mapped('reserved_quantity')), required) < 0:
                    raise UserError(self.env._('Outbound WCS requires available reserved goods.'))
            for quant in carrier.contained_quant_ids:
                key = (quant.product_id.id, quant.lot_id.id, quant.package_id.id, quant.owner_id.id, quant.location_id.id)
                if quant.quantity > 0 and quant.uom_id.compare(dimensions[key], quant.quantity) != 0:
                    raise UserError(self.env._('Plan all contents before moving an entire carrier.'))
        return ''

    def _wcs4_task_input(self, lines, decisions, payload):
        device = self._wcs_default_device()
        devices = device
        operation = self.picking_type_id
        secondary = operation.wcs_secondary_equipment_id
        if secondary and operation.wcs_secondary_task_type:
            if not secondary.active or secondary.company_id != self.company_id:
                raise UserError(self.env._('Additional equipment must be active and belong to this company.'))
            if secondary == device and operation.wcs_secondary_task_type != operation.task_type:
                raise UserError(self.env._('One equipment needs one manually authorized task type.'))
            devices |= secondary
        first = decisions[lines[0].id]
        if any((item['source_ref'], item['destination_ref']) != (first['source_ref'], first['destination_ref']) for item in (decisions[line.id] for line in lines)):
            raise UserError(self.env._('A group must use one pair of position mapping sources.'))
        positions = self._wcs4_positions(lines)
        source, destination = positions[first['source_ref']], positions[first['destination_ref']]
        if not source or not destination:
            raise UserError(self.env._('The selected position mapping is missing or ambiguous for this group.'))
        task = {'equipment_id': device.id, 'location_res_id': source, 'location_dest_id': destination,
                'source_ref': first['source_ref'], 'destination_ref': first['destination_ref'],
                'role': 'goods', 'task_type': operation.task_type, 'movement': 'primary', 'dependency_step': 0,
                'dependency_event': 'end', 'dependency_point': '', 'reason': first['reason']}
        request = dict(payload['request'], phase='tasks', positions=positions, base_task=task,
                       primary_equipment_id=device.id, secondary_equipment_id=secondary.id if secondary and operation.wcs_secondary_task_type else False,
                       secondary_task_type=operation.wcs_secondary_task_type or '',
                       position_details={ref: {'id': location_id, 'name': self.env['stock.location'].browse(location_id).complete_name,
                           'contains_inventory_source': self._wcs4_scope_contains(self.env['stock.location'].browse(location_id), lines.location_id),
                           'contains_inventory_destination': self._wcs4_scope_contains(self.env['stock.location'].browse(location_id), lines.location_dest_id),
                           'point': self.env['stock.location'].browse(location_id).agv_map_point or self.env['stock.location'].browse(location_id).barcode or self.env['stock.location'].browse(location_id).complete_name}
                           for ref, location_id in positions.items() if location_id},
                       equipment={str(item.id): {'name': item.name, 'task_type': operation.task_type if item == device else operation.wcs_secondary_task_type,
                                                'adapter': item.adapter_code,
                                                'supports_loose_goods': item._supports_wcs_loose_goods(),
                                                'supports_location_scope': item._supports_wcs_location_scope(),
                                                'supports_repeated_goods': item.adapter_code == 'simulation' or item.supports_repeated_goods} for item in devices},
                       lines={str(item['line_id']): item for item in payload['candidates'] if item['line_id'] in lines.ids},
                       decisions={str(line.id): decisions[line.id] for line in lines})
        return {'request': request, 'candidates': [task]}

    def _wcs4_scope_contains(self, location, actual):
        return all(item == location or (item.parent_path or '').startswith(location.parent_path or 'invalid/') for item in actual)

    def _wcs4_steps(self, tasks, lines):
        goods = [task for task in tasks if task['role'] == 'goods']
        if goods:
            source = self.env['stock.location'].browse(goods[0]['location_res_id'])
            destination = self.env['stock.location'].browse(goods[-1]['location_dest_id'])
            if not self._wcs4_scope_contains(source, lines.location_id) or not self._wcs4_scope_contains(destination, lines.location_dest_id):
                raise UserError(self.env._('Physical source/destination scopes must contain the fixed inventory locations.'))
        steps = self._wcs_task_values(tasks, lines)
        for step in steps:
            device = self.env['wcs.equipment'].browse(step['equipment_id'])
            source = self.env['stock.location'].browse(step['location_res_id'])
            destination = self.env['stock.location'].browse(step['location_dest_id'])
            if (not source.active or not destination.active or source.company_id not in (self.company_id, self.env['res.company'])
                    or destination.company_id not in (self.company_id, self.env['res.company'])):
                raise UserError(self.env._('WCS mapping locations must be active and in the operation company.'))
            for side, location in (('source', source), ('destination', destination)):
                ref = step[side + '_ref']
                actual = lines.location_id if ref in ('picking_source', 'source_parent') else lines.location_dest_id
                step[side + '_scope'] = ref in ('picking_source', 'picking_destination', 'source_parent', 'destination_parent') and any(item != location for item in actual)
            if (step['source_scope'] or step['destination_scope']) and not device._supports_wcs_location_scope():
                raise UserError(self.env._('This adapter needs explicit support for area/zone position mappings.'))
            if step['movement'] == 'repeat' and device.adapter_code != 'simulation' and not device.supports_repeated_goods:
                raise UserError(self.env._('Confirm the real device supports repeated same-data goods programs before using this orchestration.'))
        return steps

    def _wcs4_preview(self, profile=None):
        self.ensure_one()
        self.check_access('read')
        if not self.picking_type_id.blue_wcs_enabled or self.state in ('draft', 'done', 'cancel'):
            return []
        payload = self._wcs4_input()
        decisions = {item['line_id']: item for item in self._wcs4_run(payload, profile)}
        groups = defaultdict(lambda: self.env['stock.move.line'])
        output = []
        for line in self.move_line_ids.sorted('id'):
            if line.id not in decisions:
                continue
            decision = decisions[line.id]
            if decision['action'] != 'create' or line.uom_id.compare(decision['quantity'], 0) <= 0:
                output.append({'unit': 'line:%s' % line.id, 'line_decisions': [decision], 'waiting': decision['reason'] if decision['action'] != 'create' else '数量已由WCS计划覆盖', 'excluded': decision['action'] == 'exclude'})
            else:
                groups[decision['group_key']] |= line
        for key, lines in sorted(groups.items()):
            waiting = self._wcs4_safety(lines, decisions, profile)
            row = {'unit': key, 'line_decisions': [decisions[line.id] for line in lines],
                   'quantities': {line.id: decisions[line.id]['quantity'] for line in lines}, 'waiting': waiting}
            if not waiting:
                task_input = self._wcs4_task_input(lines, decisions, payload)
                tasks = self._wcs4_run(task_input, profile)
                row.update(tasks=self._wcs4_steps(tasks, lines), input=task_input,
                           waiting='' if tasks else '创建条件尚未满足')
            output.append(row)
        return output

    def _wcs4_create(self):
        # Picking already locked by the public planning action. Lock physical carriers in ID order.
        carriers = self._wcs_carrier(self.move_line_ids)
        for carrier in carriers.sorted('id'):
            carrier._wcs_lock_carrier()
        preview = self._wcs4_preview()
        decisions = [decision for row in preview for decision in row['line_decisions']]
        for row in preview:
            if row['waiting'] or not row.get('tasks'):
                continue
            lines = self.move_line_ids.filtered(lambda line: line.id in row['quantities'])
            carrier = self._wcs_carrier(lines)
            if not self.blue_wcs_policy_fixed:
                profile = self.picking_type_id.blue_wcs_profile_id
                self.with_context(blue_wcs_token=WCS_TOKEN).write({'blue_wcs_policy_fixed': True,
                    'blue_wcs_release_id': profile.active_release_id.id if profile else False})
            steps = row['tasks']
            snapshot = {'contract': 'wcs_creation/4', 'release_id': self.blue_wcs_release_id.id or False,
                        'line_decisions': {str(item['line_id']): item for item in row['line_decisions']},
                        'inventory': {str(line.id): self._wcs4_fingerprint(line) for line in lines}, 'steps': steps,
                        'adapters': {str(step['equipment_id']): self.env['wcs.equipment'].browse(step['equipment_id']).adapter_code for step in steps}}
            latest = self.env['wcs.plan'].search([('picking_id', '=', self.id), ('unit_key', '=', row['unit'])], order='revision desc', limit=1)
            revision = latest.revision + 1 if latest else 1
            plan = self.env['wcs.plan'].with_context(blue_wcs_token=WCS_TOKEN).create({
                'name': '%s / %s / %s' % (self.name, carrier.name or row['unit'], revision), 'company_id': self.company_id.id,
                'picking_id': self.id, 'carrier_id': carrier.id, 'unit_key': row['unit'], 'revision': revision,
                'snapshot': json.dumps(snapshot, ensure_ascii=False)})
            self.env['wcs.plan.line'].with_context(blue_wcs_token=WCS_TOKEN).create([
                {'plan_id': plan.id, 'move_line_id': line.id, 'product_id': line.product_id.id, 'uom_id': line.uom_id.id,
                 'quantity': row['quantities'][line.id], 'lot_id': line.lot_id.id,
                 'package_id': (line.result_package_id if self.picking_type_id.code == 'incoming' else line.package_id).id}
                for line in lines])
            by_step = {}
            for index, step in enumerate(steps, 1):
                predecessor = by_step.get(step['dependency_step'])
                device = self.env['wcs.equipment'].browse(step['equipment_id'])
                values = {key: value for key, value in step.items() if key not in ('dependency_step', 'reason', 'movement')}
                task = self.env['wcs.request'].with_context(blue_wcs_token=WCS_TOKEN).create(dict(values,
                    goods_mode=step['movement'], plan_id=plan.id, step=index, company_id=self.company_id.id,
                    carrier_code=carrier.name if step['role'] == 'goods' else False,
                    predecessor_id=predecessor.id if predecessor else False, state='waiting' if predecessor else 'pending_send',
                    description=step['reason'], maintenance_team_id=device.maintenance_team_id.id))
                by_step[index] = task
                task.with_context(blue_wcs_token=WCS_TOKEN).write({'payload': json.dumps(task._payload(), ensure_ascii=False)})
        self.with_context(blue_wcs_token=WCS_TOKEN).write({'blue_wcs_decision_snapshot': {
            'release_id': self.blue_wcs_release_id.id or False,
            'lines': {str(item['line_id']): {'decision': item, 'fingerprint': self._wcs4_fingerprint(self.env['stock.move.line'].browse(item['line_id']))} for item in decisions}}})
        return {'type': 'ir.actions.act_window', 'name': self.env._('WCS任务'), 'res_model': 'wcs.request',
                'view_mode': 'kanban,list,form', 'domain': [('picking_id', '=', self.id)]}

    def _wcs4_excluded_lines(self):
        snapshot = self.blue_wcs_decision_snapshot or {}
        if snapshot.get('release_id') != (self.blue_wcs_release_id.id or False):
            return self.env['stock.move.line']
        data = snapshot.get('lines', {})
        planned_carriers = self.wcs_plan_ids.filtered(lambda plan: any(task.state != 'cancelled' for task in plan.request_ids)).carrier_id
        return self.move_line_ids.filtered(lambda line: data.get(str(line.id), {}).get('decision', {}).get('action') == 'exclude'
            and data[str(line.id)]['fingerprint'] == self._wcs4_fingerprint(line)
            and not (self._wcs_carrier(line) & planned_carriers))

    def _wcs_legacy_route_select(self, code, payload):
        """Run /1 as a route filter, without granting route devices over human selections."""
        request = payload['request']
        operation = self.picking_type_id
        source = self.env['stock.location'].browse(request['source_id'])
        destination = self.env['stock.location'].browse(request['destination_id'])
        routes = self.env['wcs.route'].search([('company_id', '=', self.company_id.id), ('picking_type_id', '=', operation.id)])
        routes = routes.filtered(lambda route: route.equipment_id == operation.equipment_id
            and route.mode == request['mode'] and self._wcs4_scope_contains(route.source_id, source)
            and self._wcs4_scope_contains(route.destination_id, destination)
            and (route.mode == 'single' or route.second_equipment_id == operation.wcs_secondary_equipment_id))
        if not routes:
            raise UserError(self.env._('旧/1配置没有符合当前人工设备、模式和库存位置的线路. 请人工选择匹配设置或新建/4配置试算后改绑.'))
        candidates = [{'route_id': route.id, 'priority': route.sequence, 'mode': route.mode} for route in routes]
        selected = self.env['blue.extension.contract']._run(code, {'request': request, 'candidates': candidates}, 'wcs_creation/1')
        if not selected:
            return []
        # The original route selector returns a sorted preference, not duplicate movement plans.
        request['legacy_route_id'] = selected[0]['route_id']
        return [dict(task, reason=selected[0]['reason']) for task in payload['candidates']]
