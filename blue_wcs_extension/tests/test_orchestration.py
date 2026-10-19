import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN
from odoo.addons.blue_wcs_extension.models.creation_v4 import BASIC_V4_CODE

from .test_wcs import TestWcs


class TestWcsOrchestration(TestWcs):
    def _v4_picking(self, example='ready', incoming=False, confirmed=True, loose=False):
        picking, line, operation = self._picking(incoming=incoming, confirmed=confirmed)
        if loose:
            if not incoming:
                raise AssertionError('Loose test helper expects incoming; native outbound uses carrier stock.')
            line.result_package_id = False
        profile = self.env['blue.config.profile'].create({'name': 'V4 ' + example,
            'template_id': self.env.ref('blue_wcs_extension.template_' + example + '_v4').id})
        profile.action_load_example()
        profile.action_validate()
        profile.action_publish()
        operation.blue_wcs_profile_id = profile
        return picking, line, operation, profile

    def test_same_data_double_runs_both_programs_then_validates_stock_once(self):
        picking, line, operation, profile = self._v4_picking('repeat', confirmed=False)
        picking.with_user(self.worker).action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertEqual(first.goods_mode, 'primary')
        self.assertEqual(second.goods_mode, 'repeat')
        self.assertEqual(first.location_res_id, second.location_res_id)
        self.assertEqual(first.location_dest_id, second.location_dest_id)
        self.assertEqual(first._prepared_payload()['items'], second._prepared_payload()['items'])
        self.assertEqual(sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 10)
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)
        first.action_simulate_accept()
        first._receive_event('take-only', 'take', point=first.source_point)
        first._receive_event('point-only', 'point', point=first.destination_point)
        self.assertEqual(second.state, 'waiting')
        with self.assertRaises(UserError):
            second.action_simulate_accept()
        with self.assertRaises(UserError):
            picking.button_validate()
        first.action_simulate_end()
        self.assertEqual(second.state, 'pending_send')
        second.action_simulate_accept()
        with self.assertRaises(UserError):
            picking.button_validate()
        second.action_simulate_end()
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        quants = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.destination.id)])
        self.assertEqual(sum(quants.mapped('quantity')), 10)
        self.assertEqual(sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 10)
        second.action_simulate_end()
        self.assertEqual(sum(quants.mapped('quantity')), 10)
        with self.assertRaises(UserError):
            picking.action_create_wcs_request_from_button()

    def test_repeat_second_program_rechecks_reservation(self):
        picking, line, operation, profile = self._v4_picking('repeat')
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        first.action_simulate_accept()
        first.action_simulate_end()
        self.env['stock.quant'].search([('package_id', '=', line.package_id.id)]).reserved_quantity = 0
        with self.assertRaisesRegex(UserError, 'Reserved stock changed'):
            second.action_simulate_accept()
        self.assertEqual(second.state, 'pending_send')

    def test_repeat_failed_or_unknown_first_never_releases_second(self):
        picking, line, operation, profile = self._v4_picking('repeat')
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        first.with_context(blue_wcs_token=WCS_TOKEN).state = 'failed'
        self.assertEqual(second.state, 'waiting')
        with self.assertRaises(UserError):
            first._receive_event('illegal-failed-end', 'end')
        first.with_context(blue_wcs_token=WCS_TOKEN).state = 'unknown'
        first._receive_event('unknown-point', 'point', point='B')
        self.assertEqual(second.state, 'waiting')
        self.assertEqual(sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 10)

    def test_line_decisions_see_all_lines_and_exclusions_do_not_hide_waits(self):
        picking, line, operation, profile = self._v4_picking('filter', incoming=True, loose=True)
        manual = self.env['product.product'].create({'name': 'Manual goods', 'default_code': 'MANUAL', 'is_storable': True})
        excluded = line.copy({'product_id': manual.id, 'quantity': 2})
        waiting = line.copy({'quantity': 3, 'picked': False})
        self.assertEqual(set(item['line_id'] for item in picking._wcs4_input()['candidates']), {line.id, excluded.id, waiting.id})
        preview = picking._wcs_preview(profile)
        self.assertEqual({item['action'] for row in preview for item in row['line_decisions']}, {'create', 'wait', 'exclude'})
        self.assertFalse(picking.wcs_plan_ids)
        picking.action_create_wcs_request_from_button()
        self.assertEqual(picking.wcs_plan_ids.line_ids.move_line_id, line)
        picking.wcs_request_ids.action_simulate_accept()
        picking.wcs_request_ids.action_simulate_end()
        with self.assertRaisesRegex(UserError, 'Plan and complete'):
            picking.button_validate()
        waiting.picked = True
        picking.action_create_wcs_request_from_button()
        new_task = picking.wcs_request_ids.filtered(lambda task: task.state == 'pending_send')
        new_task.action_simulate_accept()
        new_task.action_simulate_end()
        self.assertEqual(picking._wcs4_excluded_lines(), excluded)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertNotIn(excluded, picking.wcs_plan_ids.line_ids.move_line_id)

    def test_excluded_fingerprint_cannot_exempt_changed_goods(self):
        picking, line, operation, profile = self._v4_picking('filter', incoming=True, loose=True)
        manual = self.env['product.product'].create({'name': 'Manual goods', 'default_code': 'MANUAL', 'is_storable': True})
        excluded = line.copy({'product_id': manual.id, 'quantity': 2})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(picking._wcs4_excluded_lines(), excluded)
        excluded.quantity = 3
        self.assertFalse(picking._wcs4_excluded_lines())
        with self.assertRaises(AccessError):
            picking.write({'blue_wcs_decision_snapshot': {}})

    def test_line_and_whole_picking_confirmation_are_different(self):
        picking, line, operation, profile = self._v4_picking('all_picked', incoming=True, loose=True)
        other = line.copy({'quantity': 1, 'picked': False})
        picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_request_ids)
        other.picked = True
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)

    def test_container_all_picked_is_not_whole_picking(self):
        picking, line, operation, profile = self._v4_picking('container', incoming=True)
        other_package = self.env['stock.package'].create({'name': 'Other not picked carrier'})
        other = line.copy({'quantity': 1, 'result_package_id': other_package.id, 'picked': False})
        profile.action_new_draft()
        code = profile.draft_code.replace('        action = "create"', '        action = "create" if candidate["carrier_all_picked"] else "wait"').replace('        quantity = candidate["available_quantity"]', '        quantity = candidate["available_quantity"] if candidate["carrier_all_picked"] else 0')
        profile.draft_code = code
        # Existing synthetic trials have all carrier lines picked, and remain exact.
        profile.action_validate()
        profile.action_publish()
        picking.action_create_wcs_request_from_button()
        self.assertEqual(picking.wcs_plan_ids.line_ids.move_line_id, line)
        self.assertNotIn(other, picking.wcs_plan_ids.line_ids.move_line_id)

    def test_explicit_weight_threshold_and_missing_data_wait(self):
        picking, line, operation, profile = self._v4_picking('weight', incoming=True)
        self.product.weight = 0
        self.assertIn('重量基础数据', picking._wcs_preview()[0]['waiting'])
        self.product.weight = 0.5
        self.assertIn('重量阈值', picking._wcs_preview()[0]['waiting'])
        self.product.weight = 1
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_container_combines_different_goods_and_lots_once(self):
        picking, line, operation, profile = self._v4_picking('container', incoming=True)
        product = self.env['product.product'].create({'name': 'Other carrier item', 'is_storable': True})
        other = line.copy({'product_id': product.id, 'quantity': 3})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_plan_ids), 1)
        self.assertEqual(set(picking.wcs_plan_ids.line_ids.move_line_id.ids), {line.id, other.id})
        self.assertEqual(len(picking.wcs_request_ids._payload()['items']), 2)

    def test_filter_cannot_move_carrier_with_unplanned_other_goods(self):
        picking, line, operation, profile = self._v4_picking('filter', incoming=True)
        manual = self.env['product.product'].create({'name': 'Manual carrier item', 'default_code': 'MANUAL', 'is_storable': True})
        line.copy({'product_id': manual.id, 'quantity': 2})
        picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_request_ids)
        self.assertTrue(any('同载具' in row['waiting'] for row in picking._wcs_preview()))

    def test_scope_mapping_preserves_inventory_and_accepts_only_planned_exact_bin(self):
        picking, line, operation, profile = self._v4_picking('scope')
        area = self.env['stock.location'].create({'name': 'Device destination area', 'location_id': self.source.id, 'usage': 'internal', 'company_id': self.env.company.id})
        self.destination.location_id = area
        picking.location_dest_id = area
        line.location_dest_id = self.destination
        picking.action_create_wcs_request_from_button()
        task = picking.wcs_request_ids
        self.assertEqual(task.location_dest_id, picking.location_dest_id)
        self.assertEqual(line.location_dest_id, self.destination)
        self.assertEqual(task.destination_ref, 'picking_destination')
        self.assertTrue(task.destination_scope)
        task.action_simulate_accept()
        with self.assertRaises(ValidationError):
            task._receive_event('wrong-assigned-bin', 'end', actual_destination='UNPLANNED_BIN')
        task._receive_event('correct-planned-bin', 'end', actual_destination=self.destination.agv_map_point)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(line.location_dest_id, self.destination)

    def test_scope_mapping_cannot_leave_inventory_scope(self):
        picking, line, operation, profile = self._v4_picking('scope')
        picking.location_dest_id = self.env.ref('stock.stock_location_customers')
        line.location_dest_id = self.destination
        with self.assertRaisesRegex(UserError, 'scopes must contain'):
            picking.action_create_wcs_request_from_button()

    def test_v4_relay_actual_creation_and_completion(self):
        picking, line, operation, profile = self._v4_picking('relay')
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        self.assertEqual(first.location_dest_id, second.location_res_id)
        self.assertEqual(second.equipment_id, self.device2)
        first.action_simulate_accept()
        first.action_simulate_end()
        second.action_simulate_accept()
        second.action_simulate_end()
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def test_v4_empty_carrier_step_remains_point_triggered(self):
        picking, line, operation, profile = self._v4_picking('empty')
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        first.action_simulate_accept()
        first._receive_event('unapproved-point', 'take', point='NO')
        self.assertEqual(second.state, 'waiting')
        first._receive_event('approved-point', 'take', point=first.source_point)
        self.assertEqual(second.state, 'pending_send')
        self.assertEqual(second._payload()['items'], [])

    def test_v4_automatic_creation_respects_manual_switch_and_policy_wait(self):
        picking, line, operation, profile = self._v4_picking('all_picked', confirmed=False)
        operation.auto_create_wcs_request_execute = True
        self.env['stock.picking']._cron_create_wcs()
        self.assertFalse(picking.wcs_request_ids)
        line.picked = True
        operation.auto_create_wcs_request_execute = False
        self.env['stock.picking']._cron_create_wcs()
        self.assertFalse(picking.wcs_request_ids)
        operation.auto_create_wcs_request_execute = True
        self.env['stock.picking']._cron_create_wcs()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        self.assertFalse(operation.is_auto_validate)
        self.assertFalse(operation.is_wcs_required_for_validate)

    def test_v4_trials_all_templates_and_restricted_syntax(self):
        for key in ('ready', 'repeat', 'filter', 'all_picked', 'container', 'weight', 'scope', 'relay', 'empty'):
            profile = self.env['blue.config.profile'].create({'name': key, 'template_id': self.env.ref('blue_wcs_extension.template_' + key + '_v4').id})
            profile.action_load_example()
            profile.action_validate()
            self.assertTrue(profile.validated_version_id)
            self.assertFalse(profile.active_release_id)
        engine = self.env['blue.extension.contract']
        for code in ('import os', 'result = request.get("x")', 'result = [candidate for candidate in candidates]', 'result = candidates[0]', 'result = []\nrequest["x"] = 1'):
            with self.assertRaises(ValidationError):
                engine._run(code, {'request': {'phase': 'lines'}, 'candidates': []}, 'wcs_creation/4')

    def test_v4_does_not_auto_upgrade_already_fixed_basic_or_release(self):
        picking, line, operation = self._loose_incoming()
        picking.action_create_wcs_request_from_button()
        profile = self.env['blue.config.profile'].create({'name': 'Later double', 'template_id': self.env.ref('blue_wcs_extension.template_repeat_v4').id})
        profile.action_load_example()
        profile.action_validate()
        profile.action_publish()
        operation.blue_wcs_profile_id = profile
        other = line.copy({'quantity': 2})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)
        self.assertFalse(picking.blue_wcs_release_id)
        self.assertEqual(picking.wcs_plan_ids.line_ids.move_line_id, line | other)

    def test_same_data_three_programs_have_sequential_identity_and_single_coverage(self):
        picking, line, operation, profile = self._v4_picking('triple')
        picking.action_create_wcs_request_from_button()
        tasks = picking.wcs_request_ids.sorted('step')
        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks.mapped('state'), ['pending_send', 'waiting', 'waiting'])
        self.assertEqual(sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 10)
        for task in tasks:
            task.action_simulate_accept()
            task.action_simulate_end()
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def test_v4_cannot_forge_manual_task_type_equipment_or_repeat_dependency(self):
        picking, line, operation, profile = self._v4_picking('repeat')
        payload = picking._wcs_preview(profile)[0]['input']
        first = payload['request']['base_task']
        repeat = dict(first, movement='repeat', dependency_step=1)
        engine = self.env['blue.extension.contract']
        for bad in (dict(first, equipment_id=999999), dict(first, task_type='AI_CHANGED'),
                    dict(first, source_ref='picking_source', location_res_id=999999)):
            with self.assertRaises(ValidationError):
                engine._run('result = ' + repr([bad]), payload, 'wcs_creation/4')
        for bad in (dict(repeat, dependency_step=0), dict(repeat, dependency_event='take', dependency_point='A'),
                    dict(repeat, location_res_id=self.destination.id, source_ref='line_destination')):
            with self.assertRaises(ValidationError):
                engine._run('result = ' + repr([first, bad]), payload, 'wcs_creation/4')
        self.assertEqual(operation.task_type, 'TRANSFER')
        self.assertEqual(operation.equipment_id, self.device)

    def test_v4_cannot_omit_duplicate_or_overstate_input_lines(self):
        picking, line, operation, profile = self._v4_picking()
        payload = picking._wcs4_input()
        decision = picking._wcs4_run(payload)[0]
        for result in ([], [decision, decision], [dict(decision, quantity=11)], [dict(decision, action='exclude', quantity=10)]):
            with self.assertRaises(ValidationError):
                self.env['blue.extension.contract']._run('result = ' + repr(result), payload, 'wcs_creation/4')

    def test_real_device_repeat_and_scope_require_declared_capabilities(self):
        picking, line, operation, profile = self._v4_picking('repeat')
        self.device.adapter_code = 'json'
        with self.assertRaisesRegex(UserError, 'supports repeated'):
            picking._wcs_preview(profile)
        self.device.supports_repeated_goods = True
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        self.assertEqual(first._prepared_payload()['items'], second._prepared_payload()['items'])
        self.assertEqual(first.goods_mode, 'primary')
        self.assertEqual(second.goods_mode, 'repeat')

    def test_grouped_loose_rows_aggregate_reservation_before_dispatch(self):
        picking, line, operation, profile = self._v4_picking('scope')
        # Use two rows in the same carrier, each below the later aggregate reservation.
        line.with_context(blue_wcs_token=WCS_TOKEN).quantity = 5
        other = line.copy({'quantity': 5})
        self.env['stock.quant'].search([('package_id', '=', line.package_id.id)]).reserved_quantity = 10
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        quant = self.env['stock.quant'].search([('package_id', '=', line.package_id.id)])
        quant.reserved_quantity = 5
        with self.assertRaisesRegex(UserError, 'Reserved stock changed'):
            picking.wcs_request_ids.action_simulate_accept()

    def test_carrier_new_contents_after_planning_are_checked_again_before_send(self):
        picking, line, operation, profile = self._v4_picking('container', incoming=True)
        picking.action_create_wcs_request_from_button()
        line.copy({'quantity': 2})
        with self.assertRaisesRegex(UserError, 'Carrier contents changed'):
            picking.wcs_request_ids.action_simulate_accept()

    def test_exclusion_does_not_exempt_new_goods_on_already_planned_carrier(self):
        picking, line, operation, profile = self._v4_picking('filter', incoming=True)
        picking.action_create_wcs_request_from_button()
        picking.wcs_request_ids.action_simulate_accept()
        picking.wcs_request_ids.action_simulate_end()
        manual = self.env['product.product'].create({'name': 'Later manual goods', 'default_code': 'MANUAL', 'is_storable': True})
        line.copy({'product_id': manual.id, 'quantity': 2})
        picking.action_create_wcs_request_from_button()
        self.assertFalse(picking._wcs4_excluded_lines())
        with self.assertRaisesRegex(UserError, 'Plan and complete'):
            picking.button_validate()

    def test_legacy_v1_published_binding_runs_original_route_filter_with_manual_scope(self):
        picking, line, operation = self._picking()
        operation.wcs_request_mode = 'single'
        code = 'result = []\nfor candidate in candidates:\n    if request["ready"]:\n        result.append({"route_id": candidate["route_id"], "score": candidate["priority"], "reason": "原线路选择"})'
        template = self.env['blue.scene.template'].create({'name': 'Legacy /1', 'hook_code': 'wcs_creation',
            'contract': 'wcs_creation/1', 'requirements': 'Keep the original route selector and human equipment scope.', 'code_text': code, 'test_cases': json.dumps([
                {'name': 'route', 'input': {'request': {'ready': True}, 'candidates': [{'route_id': 1, 'priority': 10, 'mode': 'single'}]}, 'expected_order': [1]}])})
        legacy = self.env['blue.config.profile'].create({'name': 'Legacy published', 'template_id': template.id})
        legacy.action_load_example()
        legacy.action_validate()
        legacy.action_publish()
        operation.blue_wcs_profile_id = legacy
        route = self.env['wcs.route'].create({'name': 'Original authorized route', 'company_id': self.env.company.id,
            'picking_type_id': operation.id, 'source_id': line.location_id.id, 'destination_id': line.location_dest_id.id,
            'source_point': 'A', 'destination_point': 'B', 'equipment_id': self.device.id, 'mode': 'single'})
        release = legacy.active_release_id
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        self.assertEqual(picking.wcs_plan_ids.route_id, route)
        self.assertEqual(picking.blue_wcs_release_id, release)
        self.assertEqual(json.loads(picking.wcs_plan_ids.snapshot)['contract'], 'wcs_creation/1')
        self.assertEqual(release.version_id.code_text, code)
        self.assertEqual(picking.wcs_request_ids.equipment_id, operation.equipment_id)
        self.assertEqual(picking.wcs_request_ids.task_type, operation.task_type)
        picking.wcs_request_ids.action_simulate_accept()
        picking.wcs_request_ids.action_simulate_end()
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def test_same_carrier_keeps_distinct_lots_in_one_physical_plan(self):
        picking, line, operation, profile = self._v4_picking('container', incoming=True)
        self.product.tracking = 'lot'
        lots = self.env['stock.lot'].create([{'name': name, 'product_id': self.product.id, 'company_id': self.env.company.id}
            for name in ('ORCH-LOT-A', 'ORCH-LOT-B')])
        line.lot_id = lots[0]
        line.copy({'quantity': 3, 'lot_id': lots[1].id})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_plan_ids), 1)
        self.assertEqual(picking.wcs_plan_ids.line_ids.lot_id, lots)
        self.assertEqual({item['lot'] for item in picking.wcs_request_ids._payload()['items']}, set(lots.mapped('name')))
