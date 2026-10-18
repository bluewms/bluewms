import json
from unittest.mock import Mock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user
from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN
from odoo.addons.blue_wcs_base.models.transport import send


from .fixtures import load_legacy_examples


class TestWcs(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_legacy_examples(cls.env)
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'WCS test', 'code': 'WCST'})
        cls.source = cls.warehouse.lot_stock_id
        cls.destination = cls.env['stock.location'].create({'name': 'WCS target', 'usage': 'internal', 'location_id': cls.source.id, 'company_id': cls.env.company.id})
        cls.product = cls.env['product.product'].create({'name': 'WCS goods', 'is_storable': True, 'tracking': False})
        cls.category = cls.env['wcs.equipment.category'].create({'name': 'WCS simulated category', 'company_id': cls.env.company.id})
        cls.device = cls.env['wcs.equipment'].create({'name': 'WCS simulated', 'company_id': cls.env.company.id, 'category_id': cls.category.id})
        cls.device2 = cls.env['wcs.equipment'].create({'name': 'WCS simulated leg 2', 'company_id': cls.env.company.id})
        cls.profile = cls.env['blue.config.profile'].create({'name': 'WCS strategy', 'template_id': cls.env.ref('blue_wcs_extension.template_relay_v3').id})
        cls.profile.action_load_example()
        cls.profile.action_validate()
        cls.profile.action_publish()
        cls.worker = new_test_user(cls.env, login='wcs_worker', groups='stock.group_stock_user')

    def _policy_code(self, mode, group=True, condition='ready', basis=None):
        basis_code = repr(basis) if basis else '"confirmed" if request["operation"] == "incoming" else "reserved"'
        return ('if request["phase"] == "configure":\n'
                '    result = {"condition": "%s", "mode": "%s", "quantity_basis": %s, "group_by_container": %s}\n'
                'else:\n    result = []\n    for candidate in candidates:\n'
                '        if request["ready"] and request["default_condition_met"]:\n'
                '            result.append(candidate)\n') % (condition, mode, basis_code, group)

    def _publish_mode(self, mode, group=True, condition='ready', basis=None):
        self.profile.action_new_draft()
        self.profile.draft_code = self._policy_code(mode, group, condition, basis)
        settings = {'condition': condition, 'mode': mode, 'quantity_basis': basis or 'reserved', 'group_by_container': group}
        self.profile.draft_tests = json.dumps([
            {'name': 'configure', 'input': {'request': {'phase': 'configure', 'operation': 'internal'}, 'candidates': []}, 'expected_result': settings},
            {'name': 'wait', 'input': {'request': {'phase': 'tasks'}, 'candidates': []}, 'expected_result': []}])
        self.profile.action_validate()
        self.profile.action_publish()

    def _picking(self, incoming=False, confirmed=True, qty=10):
        operation = self.warehouse.in_type_id if incoming else self.warehouse.int_type_id
        operation.write({'blue_wcs_enabled': True, 'blue_wcs_ready_mode': 'confirmed' if incoming else 'reserved', 'blue_wcs_profile_id': self.profile.id})
        source = self.env.ref('stock.stock_location_suppliers') if incoming else self.source
        picking = self.env['stock.picking'].create({'picking_type_id': operation.id, 'location_id': source.id, 'location_dest_id': self.destination.id})
        package = self.env['stock.package'].create({'name': 'WCS carrier ' + str(picking.id)})
        move = self.env['stock.move'].create({'picking_id': picking.id, 'product_id': self.product.id, 'uom_id': self.product.uom_id.id,
                                            'product_uom_qty': qty, 'location_id': source.id, 'location_dest_id': self.destination.id})
        if not incoming:
            self.env['stock.quant']._update_available_quantity(self.product, source, qty, package_id=package)
        picking.action_confirm()
        picking.action_assign()
        if move.move_line_ids:
            line = move.move_line_ids[0]
            line.write({'quantity': qty, 'picked': confirmed, 'package_id': package.id if not incoming else False,
                        'result_package_id': package.id, 'location_dest_id': self.destination.id})
        else:
            line = self.env['stock.move.line'].create({'picking_id': picking.id, 'move_id': move.id, 'product_id': self.product.id,
                'uom_id': self.product.uom_id.id, 'quantity': qty, 'picked': confirmed, 'location_id': source.id,
                'location_dest_id': self.destination.id, 'result_package_id': package.id})
        source.agv_map_point = 'A'
        self.destination.agv_map_point = 'B'
        intermediate = self.env['stock.location'].create({'name': 'WCS handoff', 'location_id': self.source.id,
            'usage': 'internal', 'company_id': self.env.company.id, 'agv_map_point': 'HANDOFF'})
        operation.write({'wcs_type': 'in' if incoming else 'out', 'equipment_category_id': self.category.id, 'wcs_secondary_task_type': 'TRANSFER', 'equipment_id': self.device.id, 'task_type': 'TRANSFER', 'is_create_wcs_by_container': True,
                         'wcs_request_mode': 'relay', 'wcs_secondary_equipment_id': self.device2.id,
                         'wcs_intermediate_location_id': intermediate.id})
        return picking, line, operation

    def test_outbound_before_confirmation_creates_two_legs(self):
        picking, line, route = self._picking(confirmed=False)
        picking.with_user(self.worker).action_create_wcs_request_from_button()
        self.assertNotEqual(picking.state, 'done')
        tasks = picking.wcs_request_ids.sorted('step')
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks.mapped('state'), ['pending_send', 'waiting'])
        self.assertEqual(sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 10)
        self.assertEqual(tasks[0].destination_point, tasks[1].source_point)

    def test_inbound_waits_for_confirmed_quantity(self):
        picking, line, route = self._picking(incoming=True, confirmed=False)
        picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_plan_ids)
        line.picked = True
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)

    def test_repeat_planning_is_idempotent(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_plan_ids), 1)
        self.assertEqual(len(picking.wcs_request_ids), 2)

    def test_preview_does_not_create_or_fix_version(self):
        picking, line, route = self._picking()
        preview = picking._wcs_preview(self.profile)
        self.assertEqual(len(preview[0]['tasks']), 2)
        self.assertFalse(picking.blue_wcs_policy_fixed)
        self.assertFalse(picking.wcs_request_ids)

    def test_relay_releases_only_after_completion(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        first.action_simulate_accept()
        first._receive_event('point-1', 'point', point='HANDOFF')
        self.assertEqual(second.state, 'waiting')
        first.action_simulate_end()
        self.assertEqual(second.state, 'pending_send')
        second.action_simulate_accept()
        second.action_simulate_end()
        self.assertEqual(len(first.event_ids), 2)
        first.action_simulate_end()
        self.assertEqual(len(first.event_ids), 2)

    def test_early_release_checks_approved_point(self):
        picking, line, route = self._picking(incoming=True)
        self._publish_mode('double_in')
        line.location_id.agv_map_point = 'SAFE'
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        self.assertEqual(second.role, 'empty_return')
        self.assertEqual(second._payload()['items'], [])
        first.action_simulate_accept()
        first._receive_event('wrong-point', 'point', point='OTHER')
        self.assertEqual(second.state, 'waiting')
        first._receive_event('right-point', 'point', point='SAFE')
        self.assertEqual(second.state, 'pending_send')

    def test_wrong_actual_destination_is_rejected(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids.sorted('step')[0]
        first.action_simulate_accept()
        with self.assertRaises(ValidationError):
            first._receive_event('end-wrong', 'end', actual_destination='WRONG')
        self.assertEqual(first.state, 'accepted')

    def test_direct_state_and_version_forgery_rejected(self):
        picking, line, route = self._picking()
        with self.assertRaises(AccessError):
            picking.write({'blue_wcs_release_id': self.profile.active_release_id.id})
        picking.action_create_wcs_request_from_button()
        with self.assertRaises(AccessError):
            picking.wcs_request_ids[0].write({'state': 'completed'})
        with self.assertRaises(UserError):
            line.quantity = 20

    def test_sent_plan_cannot_be_cancelled_as_unsent(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids.sorted('step')[0]
        first.action_simulate_accept()
        with self.assertRaises(UserError):
            first.action_cancel_unsent()

    def test_cancel_unsent_recreates_new_revision(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        picking.wcs_request_ids.action_cancel_unsent()
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_plan_ids), 2)
        self.assertEqual(picking.wcs_plan_ids.mapped('revision'), [2, 1])

    def test_fixed_version_survives_new_publication(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        fixed = picking.blue_wcs_release_id
        self.profile.action_new_draft()
        self._publish_mode('single')
        self.profile.action_new_draft()
        self.profile.action_load_example()
        self.profile.action_validate()
        self.profile.action_publish()
        self.assertNotEqual(fixed, self.profile.active_release_id)
        self.assertEqual(picking.blue_wcs_release_id, fixed)

    def test_bad_candidate_and_code_rejected(self):
        engine = self.env['blue.extension.contract']
        payload = {'request': {'allowed_location_ids': [1,2], 'allowed_equipment_ids': [1]}, 'candidates': []}
        task = {'equipment_id': 999, 'location_res_id': 1, 'location_dest_id': 2, 'role': 'goods',
                'task_type': 'TRANSFER', 'dependency_step': 0, 'dependency_event': 'end', 'dependency_point': '', 'reason': 'bad'}
        with self.assertRaises(ValidationError):
            engine._run('result = [' + repr(task) + ']', payload, 'wcs_creation/2')
        with self.assertRaises(ValidationError):
            engine._validate_code('import os', 'wcs_creation/2')

    def test_blocked_destination_cannot_plan(self):
        picking, line, route = self._picking()
        self.destination.block_stock_entrance = True
        with self.assertRaises(UserError):
            picking.action_create_wcs_request_from_button()

    def test_creation_configuration_cannot_use_blocked_handoff(self):
        picking, line, operation = self._picking()
        operation.wcs_intermediate_location_id.block_stock_entrance = True
        with self.assertRaises(UserError):
            picking.action_create_wcs_request_from_button()

    def test_pending_tasks_block_stock_validation(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_original_optional_wcs_allows_manual_stock_validation(self):
        picking, line, operation = self._picking()
        self.assertFalse(operation.is_wcs_required_for_validate)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertFalse(picking.wcs_request_ids)

    def test_original_required_wcs_blocks_validation_without_tasks(self):
        picking, line, operation = self._picking(incoming=True, confirmed=False)
        operation.is_wcs_required_for_validate = True
        with self.assertRaises(UserError):
            picking.button_validate()
        self.assertNotEqual(picking.state, 'done')

    def test_original_container_switch_changes_planning_groups(self):
        picking, line, operation = self._picking(incoming=True)
        second = line.copy({'quantity': 3})
        self.assertEqual(len(picking._wcs_units()), 1)
        self._publish_mode('single', group=False)
        units = picking._wcs_units()
        self.assertEqual(len(units), 2)
        self.assertEqual(sorted(lines.id for key, lines in units), sorted([line.id, second.id]))

    def test_simulation_cannot_complete_live_devices(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        self.device.adapter_code = 'json'
        with self.assertRaises(AccessError):
            picking.wcs_request_ids.sorted('step')[0].action_simulate_end()

    def test_timeout_is_unknown_without_retry(self):
        import requests
        connection = {'adapter_code': 'json', 'endpoint': 'https://example.invalid/tasks', 'api_key': 'test-only', 'api_secret': ''}
        with patch('odoo.addons.blue_wcs_base.models.transport.requests.post', side_effect=requests.Timeout):
            state, message = send(connection, {'task_id': 'same-id'})
        self.assertEqual(state, 'unknown')

    def test_two_leg_plan_can_finish_and_validate_stock_once(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        for task in picking.wcs_request_ids.sorted('step'):
            task.action_simulate_accept()
            task.action_simulate_end()
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        quants = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.destination.id)])
        self.assertEqual(sum(quants.mapped('quantity')), 10)

    def test_event_same_id_different_content_rejected(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids.sorted('step')[0]
        first.action_simulate_accept()
        first._receive_event('event-1', 'point', point='A')
        with self.assertRaises(ValidationError):
            first._receive_event('event-1', 'point', point='B')

    def test_non_manager_cannot_complete_simulation(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        with self.assertRaises(AccessError):
            picking.wcs_request_ids.with_user(self.worker).action_simulate_accept()

    def test_second_task_creation_failure_rolls_back_whole_plan(self):
        picking, line, route = self._picking()
        method = type(self.env['wcs.request']).create
        def reject_second(tasks, vals_list):
            if isinstance(vals_list, dict) and vals_list.get('step') == 2:
                raise ValidationError('Test-only second step failure')
            return method(tasks, vals_list)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            with patch.object(type(self.env['wcs.request']), 'create', reject_second):
                picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_plan_ids)

    def test_hik_signature_and_tls_verification(self):
        accepted = Mock(status_code=200, content=b'ok')
        accepted.json.return_value = {'code': 'SUCCESS'}
        connection = {'adapter_code': 'hik', 'endpoint': 'https://hik.invalid/rcs/rtas/api/robot/controller/task/submit',
                      'api_key': 'test-only', 'api_secret': 'test-only'}
        with patch('odoo.addons.blue_wcs_base.models.transport.requests.post', return_value=accepted) as post:
            self.assertEqual(send(connection, {'robotTaskCode': 'stable'})[0], 'accepted')
            self.assertIn('?sign=', post.call_args.args[0])
            self.assertNotIn('verify', post.call_args.kwargs)
            self.assertFalse(post.call_args.kwargs['allow_redirects'])

    def test_unknown_keeps_coverage_and_retries_same_task_after_reconciliation(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids.sorted('step')[0]
        first.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'unknown'})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_plan_ids), 1)
        original_name = first.name
        wizard = self.env['wcs.reconciliation'].create({'request_id': first.id, 'outcome': 'not_accepted',
            'evidence': 'Test device query confirms that the original task was never accepted.'})
        wizard.action_apply()
        self.assertEqual(first.state, 'pending_send')
        self.assertEqual(first.name, original_name)

    def test_insufficient_reconciliation_evidence_rejected(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids.sorted('step')[0]
        first.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'unknown'})
        wizard = self.env['wcs.reconciliation'].create({'request_id': first.id, 'outcome': 'not_accepted', 'evidence': 'guess'})
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_worker_cannot_read_device_secrets(self):
        device = self.device.with_user(self.worker)
        with self.assertRaises(AccessError):
            device.read(['callback_token'])

    def test_cross_company_strategy_rejected(self):
        picking, line, route = self._picking()
        other_company = self.env['res.company'].create({'name': 'WCS other tenant'})
        other_profile = self.env['blue.config.profile'].create({'name': 'Other WCS scene', 'company_id': other_company.id,
            'template_id': self.env.ref('blue_wcs_extension.template_relay_v3').id})
        with self.assertRaises(ValidationError):
            picking._wcs_preview(other_profile)

    def test_stock_cancel_blocked_until_unsent_tasks_cancelled(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        with self.assertRaises(UserError):
            picking.action_cancel()
        picking.wcs_request_ids.action_cancel_unsent()
        picking.action_cancel()
        self.assertEqual(picking.state, 'cancel')

    def test_inbound_explicit_confirmation_uses_native_picked(self):
        picking, line, route = self._picking(incoming=True, confirmed=False)
        picking.with_user(self.worker).action_confirm_wcs_quantities()
        self.assertTrue(line.picked)
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)

    def test_task_payload_remains_fixed_after_device_template_change(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids.sorted('step')[0]
        original = first.payload
        self.device.task_type = 'CHANGED'
        route.wcs_intermediate_location_id.agv_map_point = 'CHANGED'
        first.action_simulate_accept()
        self.assertEqual(first.payload, original)
        self.assertEqual(first.destination_point, 'HANDOFF')

    def test_device_protocol_change_blocks_fixed_task(self):
        picking, line, route = self._picking()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids.sorted('step')[0]
        self.device.write({'adapter_code': 'json', 'callback_token': 'test-only'})
        with self.assertRaises(UserError):
            first._preflight()

    def test_goods_after_empty_supply_rechecks_reservation(self):
        picking, line, route = self._picking()
        self._publish_mode('double_out')
        picking.action_create_wcs_request_from_button()
        first, second = picking.wcs_request_ids.sorted('step')
        self.assertEqual(first.role, 'empty_supply')
        self.assertFalse(first.carrier_code)
        first.action_simulate_accept()
        first.action_simulate_end()
        quants = self.env['stock.quant'].search([('package_id', '=', line.package_id.id), ('product_id', '=', self.product.id)])
        quants.write({'reserved_quantity': 0})
        with self.assertRaises(UserError):
            second.action_simulate_accept()

    def test_auto_validate_requires_every_leg_completed(self):
        picking, line, route = self._picking()
        picking.picking_type_id.blue_wcs_auto_validate = True
        picking.action_create_wcs_request_from_button()
        self.env['stock.picking']._cron_validate_wcs()
        self.assertNotEqual(picking.state, 'done')
        first, second = picking.wcs_request_ids.sorted('step')
        first.action_simulate_accept()
        first.action_simulate_end()
        self.env['stock.picking']._cron_validate_wcs()
        self.assertNotEqual(picking.state, 'done')
        second.action_simulate_accept()
        second.action_simulate_end()
        self.env['stock.picking']._cron_validate_wcs()
        self.assertEqual(picking.state, 'done')

    def test_no_route_records_needed_for_creation(self):
        picking, line, operation = self._picking()
        self.assertFalse(self.env['wcs.route'].search([('picking_type_id', '=', operation.id)]))
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)
        self.assertFalse(picking.wcs_plan_ids.route_id)
        self.assertEqual(picking.wcs_request_ids.sorted('step')[0].location_res_id, line.location_id)

    def test_creation_configuration_changes_task_count_and_endpoints(self):
        picking, line, operation = self._picking()
        self._publish_mode('single')
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        self.assertEqual(picking.wcs_request_ids.location_dest_id, line.location_dest_id)

    def test_original_single_mode_defaults_work_without_configuration(self):
        picking, line, operation = self._picking()
        operation.write({'blue_wcs_profile_id': False, 'wcs_request_mode': 'single'})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        self.assertEqual(picking.wcs_request_ids.equipment_id, operation.equipment_id)

    def test_original_default_all_picked_waits_and_does_not_pin_version(self):
        picking, line, operation = self._picking(confirmed=False)
        self._publish_mode('relay', condition='all_confirmed')
        picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_request_ids)
        self.assertFalse(picking.blue_wcs_policy_fixed)
        line.picked = True
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)

    def test_original_views_and_configuration_menu(self):
        view = self.env['wcs.request'].get_view(view_type='form')['arch']
        for name in ('product_id', 'product_qty', 'lot_id', 'package_id', 'location_res_id', 'location_dest_id', 'category_id', 'stage_id'):
            self.assertIn('name="' + name + '"', view)
        operation_view = self.env['stock.picking.type'].get_view(view_type='form')['arch']
        self.assertIn('name="wcs_app"', operation_view)
        self.assertIn('name="equipment_category_id"', operation_view)
        self.assertNotIn('name="wcs_request_mode"', operation_view)
        self.assertEqual(self.env.ref('blue_wcs_extension.wcs_policy_menu').name, 'AI创建配置')
        self.assertFalse(self.env.ref('blue_wcs_base.route_menu').active)

    def _loose_incoming(self, confirmed=True):
        picking, line, operation = self._picking(incoming=True, confirmed=confirmed)
        operation.blue_wcs_profile_id = False
        line.result_package_id = False
        return picking, line, operation

    def test_basic_loose_lines_ignore_all_legacy_policy_fields(self):
        picking, line, operation = self._loose_incoming()
        second_destination = self.env['stock.location'].create({'name': 'Other end', 'location_id': self.source.id, 'usage': 'internal', 'company_id': self.env.company.id})
        second = line.copy({'quantity': 3, 'location_dest_id': second_destination.id})
        operation.write({'wcs_request_mode': 'relay', 'wcs_generate_condition': 'all_picked', 'is_create_wcs_by_container': True,
                         'wcs_secondary_equipment_id': False, 'wcs_secondary_task_type': False, 'wcs_intermediate_location_id': False})
        picking.with_user(self.worker).action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_plan_ids), 2)
        self.assertEqual(len(picking.wcs_request_ids), 2)
        for row in picking.wcs_plan_ids.line_ids:
            task = row.plan_id.request_ids
            self.assertEqual(task.location_res_id, row.move_line_id.location_id)
            self.assertEqual(task.location_dest_id, row.move_line_id.location_dest_id)
            self.assertEqual(task.equipment_id, self.device)
            self.assertEqual(task.task_type, operation.task_type)
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)
        self.assertEqual(set(picking.wcs_plan_ids.line_ids.move_line_id.ids), {line.id, second.id})

    def test_basic_adds_uncovered_line_while_other_line_in_flight(self):
        picking, line, operation = self._loose_incoming()
        picking.action_create_wcs_request_from_button()
        first = picking.wcs_request_ids
        first.action_simulate_accept()
        second = line.copy({'quantity': 4})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_plan_ids), 2)
        self.assertEqual(sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 14)
        self.assertEqual(len(picking.wcs_plan_ids.filtered(lambda plan: second in plan.line_ids.move_line_id)), 1)

    def test_basic_new_carrier_not_skipped_by_existing_plan(self):
        picking, line, operation = self._picking(incoming=True)
        operation.blue_wcs_profile_id = False
        picking.action_create_wcs_request_from_button()
        package = self.env['stock.package'].create({'name': 'Extra actual carrier'})
        second = line.copy({'quantity': 4, 'result_package_id': package.id})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)
        self.assertEqual(set(picking.wcs_plan_ids.line_ids.move_line_id.ids), {line.id, second.id})

    def test_basic_automatic_creation_requires_manual_switch(self):
        picking, line, operation = self._loose_incoming()
        operation.auto_create_wcs_request_execute = False
        self.env['stock.picking']._cron_create_wcs()
        self.assertFalse(picking.wcs_request_ids)
        operation.auto_create_wcs_request_execute = True
        self.env['stock.picking']._cron_create_wcs()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        self.assertFalse(operation.is_auto_validate)
        self.assertNotEqual(picking.state, 'done')

    def test_basic_inbound_confirm_and_legacy_all_picked_ignored(self):
        picking, line, operation = self._loose_incoming(confirmed=False)
        operation.wcs_generate_condition = 'all_picked'
        picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_request_ids)
        picking.with_user(self.worker).action_confirm_wcs_quantities()
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_basic_outbound_uses_reservation_even_with_legacy_confirmed_setting(self):
        picking, line, operation = self._picking(confirmed=False)
        operation.write({'blue_wcs_profile_id': False, 'blue_wcs_ready_mode': 'confirmed', 'wcs_generate_condition': 'all_picked'})
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_ai_quantity_basis_runs_before_readiness(self):
        picking, line, operation = self._picking(confirmed=False)
        self._publish_mode('single', basis='confirmed')
        operation.blue_wcs_ready_mode = 'reserved'
        self.assertEqual(picking._wcs_preview()[0]['waiting'], '等待实际数量确认')
        self._publish_mode('single', basis='reserved')
        operation.blue_wcs_ready_mode = 'confirmed'
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_ai_container_grouping_precedes_old_line_switch_and_preserves_multigoods(self):
        picking, line, operation = self._picking(incoming=True)
        product2 = self.env['product.product'].create({'name': 'Second goods', 'is_storable': True})
        second = line.copy({'product_id': product2.id, 'quantity': 3})
        operation.is_create_wcs_by_container = False
        self._publish_mode('single', group=True)
        preview = picking._wcs_preview(self.profile)
        self.assertEqual(len(preview), 1)
        self.assertFalse(picking.wcs_plan_ids)
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        self.assertEqual(set(picking.wcs_plan_ids.line_ids.product_id.ids), {self.product.id, product2.id})
        self.assertEqual(sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 13)

    def test_basic_multiline_whole_carrier_reports_conflict(self):
        picking, line, operation = self._picking(incoming=True)
        operation.blue_wcs_profile_id = False
        line.copy({'quantity': 2})
        with self.assertRaisesRegex(UserError, 'One carrier contains several product lines'):
            picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_request_ids)

    def test_unplanned_carrier_contents_rejected(self):
        picking, line, operation = self._picking()
        other_product = self.env['product.product'].create({'name': 'Unplanned carrier goods', 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(other_product, line.location_id, 1, package_id=line.package_id)
        with self.assertRaisesRegex(UserError, 'Plan all contents'):
            picking.action_create_wcs_request_from_button()

    def test_ai_cannot_use_unselected_same_company_device_or_change_task_type(self):
        picking, line, operation = self._picking()
        unauthorized = self.env['wcs.equipment'].create({'name': 'Not authorized', 'company_id': self.env.company.id})
        payload = picking._wcs_payload(line, {line.id: 10})
        self.assertNotIn(unauthorized.id, payload['request']['allowed_equipment_ids'])
        task = dict(payload['candidates'][0], equipment_id=unauthorized.id)
        engine = self.env['blue.extension.contract']
        with self.assertRaises(ValidationError):
            engine._run('result = ' + repr([task]), payload, 'wcs_creation/3')
        task = dict(payload['candidates'][0], task_type='AI_CHANGED')
        with self.assertRaises(ValidationError):
            engine._run('result = ' + repr([task]), payload, 'wcs_creation/3')
        task = dict(payload['candidates'][0], equipment_id=self.device2.id, location_dest_id=line.location_dest_id.id)
        with self.assertRaises(ValidationError):
            engine._run('result = ' + repr([task]), payload, 'wcs_creation/3')
        self.assertEqual(operation.equipment_id, self.device)

    def test_missing_manual_device_does_not_autoselect_single_category_device(self):
        picking, line, operation = self._loose_incoming()
        operation.equipment_id = False
        with self.assertRaises(UserError):
            picking.action_create_wcs_request_from_button()

    def test_loose_goods_adapter_capability_is_explicit(self):
        picking, line, operation = self._loose_incoming()
        self.device.adapter_code = 'hik'
        with self.assertRaisesRegex(UserError, '未支持无容器'):
            picking._wcs_preview()
        self.device.adapter_code = 'json'
        with self.assertRaisesRegex(UserError, '未支持无容器'):
            picking._wcs_preview()
        self.device.supports_loose_goods = True
        picking.with_user(self.worker).action_create_wcs_request_from_button()
        self.assertFalse(picking.wcs_plan_ids.carrier_id)
        self.assertEqual(len(json.loads(picking.wcs_request_ids.payload)['items']), 1)

    def test_ai_cannot_select_reserved_for_incoming_or_add_switches(self):
        engine = self.env['blue.extension.contract']
        settings = {'condition': 'ready', 'mode': 'single', 'quantity_basis': 'reserved', 'group_by_container': False}
        payload = {'request': {'phase': 'configure', 'operation': 'incoming'}, 'candidates': []}
        with self.assertRaises(ValidationError):
            engine._run('result = ' + repr(settings), payload, 'wcs_creation/3')
        settings.update(quantity_basis='confirmed', is_auto_validate=True)
        with self.assertRaises(ValidationError):
            engine._run('result = ' + repr(settings), payload, 'wcs_creation/3')

    def test_old_released_strategy_keeps_compatible_manual_orchestration(self):
        picking, line, operation = self._picking()
        old = self.env['blue.config.profile'].create({'name': 'Old release', 'template_id': self.env.ref('blue_wcs_extension.template_ready').id})
        old.action_load_example()
        old.action_validate()
        old.action_publish()
        code = old.active_release_id.version_id.code_text
        operation.blue_wcs_profile_id = old
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)
        self.assertEqual(old.active_release_id.version_id.code_text, code)
        self.assertEqual(old.contract, 'wcs_creation/2')
        operation.blue_wcs_profile_id = False
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 2)

    def test_unpublished_binding_can_be_removed_for_basic_creation(self):
        picking, line, operation = self._loose_incoming()
        draft = self.env['blue.config.profile'].create({'name': 'Not released', 'template_id': self.env.ref('blue_wcs_extension.template_ready_v3').id})
        operation.blue_wcs_profile_id = draft
        with self.assertRaisesRegex(UserError, '尚未发布'):
            picking.action_create_wcs_request_from_button()
        operation.blue_wcs_profile_id = False
        picking.action_create_wcs_request_from_button()
        self.assertFalse(picking.blue_wcs_release_id)
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_every_v3_template_trials_pass_and_contract_is_available(self):
        for key in ('ready', 'all_confirmed', 'relay', 'container', 'empty_return'):
            profile = self.env['blue.config.profile'].create({'name': key, 'template_id': self.env.ref('blue_wcs_extension.template_' + key + '_v3').id})
            profile.action_load_example()
            profile.action_validate()
            self.assertFalse(profile.active_release_id)
            self.assertTrue(profile.validated_version_id)
        schema = self.env['blue.extension.contract']._describe('wcs_creation/3')
        self.assertEqual(schema['tasks_output']['maxItems'], 4)
        self.assertEqual(schema['contract'], 'wcs_creation/3')

    def test_completed_operations_cannot_be_reissued_and_loose_completion_validates(self):
        picking, line, operation = self._loose_incoming()
        picking.action_create_wcs_request_from_button()
        picking.wcs_request_ids.action_simulate_accept()
        picking.wcs_request_ids.action_simulate_end()
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        with self.assertRaises(UserError):
            picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_completed_carrier_does_not_silently_move_added_contents_again(self):
        picking, line, operation = self._picking(incoming=True)
        self._publish_mode('single')
        picking.action_create_wcs_request_from_button()
        picking.wcs_request_ids.action_simulate_accept()
        picking.wcs_request_ids.action_simulate_end()
        line.copy({'quantity': 1})
        with self.assertRaisesRegex(UserError, 'already moved'):
            picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_preflight_rechecks_actual_confirmation_and_handoff_freeze(self):
        picking, line, operation = self._picking(incoming=True)
        picking.action_create_wcs_request_from_button()
        task = picking.wcs_request_ids.sorted('step')[0]
        line.picked = False
        with self.assertRaisesRegex(UserError, 'no longer confirmed'):
            task.action_simulate_accept()
        line.picked = True
        operation.wcs_intermediate_location_id.block_stock_entrance = True
        with self.assertRaisesRegex(UserError, 'task locations are blocked'):
            task.action_simulate_accept()

    def test_legacy_inbound_quantity_field_does_not_gate_basic_creation(self):
        picking, line, operation = self._loose_incoming()
        operation.blue_wcs_ready_mode = 'reserved'
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)

    def test_basic_real_preview_wizard_without_ai_is_read_only(self):
        picking, line, operation = self._loose_incoming()
        wizard = self.env['wcs.preview'].create({'picking_id': picking.id})
        wizard.action_preview()
        self.assertIn('1 张WCS作业', wizard.result)
        self.assertFalse(picking.wcs_request_ids)
        self.assertFalse(picking.blue_wcs_policy_fixed)

    def test_loose_partial_historical_coverage_creates_only_remaining_quantity(self):
        picking, line, operation = self._loose_incoming()
        picking.action_create_wcs_request_from_button()
        # Trusted upstream quantity change represents a pre-existing partial plan.
        # Normal users still cannot mutate fixed goods through RPC.
        line.with_context(blue_wcs_token=WCS_TOKEN).quantity = 14
        picking.action_create_wcs_request_from_button()
        picking.action_create_wcs_request_from_button()
        self.assertEqual(sorted(picking.wcs_plan_ids.line_ids.mapped('quantity')), [4, 10])
        self.assertEqual(len(picking.wcs_request_ids), 2)

    def test_busy_carrier_waits_without_skipping_other_uncovered_carrier(self):
        first, first_line, operation = self._picking(incoming=True)
        operation.blue_wcs_profile_id = False
        first.action_create_wcs_request_from_button()
        picking, line, operation = self._picking(incoming=True)
        operation.blue_wcs_profile_id = False
        busy_line = line.copy({'quantity': 2, 'result_package_id': first_line.result_package_id.id})
        preview = picking._wcs_preview()
        self.assertTrue(any('在途' in row.get('waiting', '') for row in preview))
        picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        self.assertEqual(picking.wcs_plan_ids.line_ids.move_line_id, line)
        self.assertNotIn(busy_line, picking.wcs_plan_ids.line_ids.move_line_id)
        self.assertFalse(picking.picking_type_id.is_auto_validate)
