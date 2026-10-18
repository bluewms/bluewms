import json
from unittest.mock import Mock, patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.addons.base.tests.common import BaseCommon

from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN

from ..models.transport import send_protocol
from .common import fixture, make_category, make_task


@tagged('post_install', '-at_install')
class TestDeviceProtocol(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Protocol warehouse', 'code': 'PROT'})
        cls.root = cls.warehouse.lot_stock_id
        cls.destination = cls.env['stock.location'].create({'name': 'Protocol planned bin', 'location_id': cls.root.id,
            'company_id': cls.env.company.id, 'barcode': 'PROTOCOL-BIN-B', 'agv_map_point': 'B'})
        cls.actual = cls.env['stock.location'].create({'name': 'Protocol actual bin', 'location_id': cls.root.id,
            'company_id': cls.env.company.id, 'barcode': 'PROTOCOL-BIN-C', 'agv_map_point': 'C'})
        cls.product = cls.env['product.product'].create({'name': 'Protocol goods', 'default_code': 'PROTOCOL-SKU', 'is_storable': True})

    def _task(self, name='tusk-subposition', **settings):
        category = make_category(self.env, self.root, name, **settings)
        task, line, package = make_task(self.env, category, self.warehouse, self.destination, self.product)
        return category, task, line, package

    def _accept(self, task):
        task._preflight()
        task.with_context(blue_wcs_token=WCS_TOKEN).write({'state': 'accepted'})

    def _callback(self, task, point='B-03', **values):
        return task._protocol_receive({'taskId': task.name, 'targetPoint': point, **values})

    def test_empty_category_has_asset_without_local_example(self):
        category = self.env['wcs.equipment.category'].create({'name': 'Manual new vendor', 'adapter_code': 'protocol'})
        self.assertTrue(category.protocol_profile_id)
        self.assertFalse(category.protocol_code)
        self.assertFalse(category.protocol_tests)
        self.assertFalse(category.protocol_release_id)

    def test_request_uses_manual_path_and_fixed_task_template(self):
        category, task, line, package = self._task()
        body = task._payload()
        self.assertEqual(body, {'taskId': task.name, 'targets': ['A', 'B'], 'configId': 'TRANSFER'})
        self.assertEqual(task._dispatch_connection()['endpoint'], 'http://127.0.0.1:9/rpc/createTask')
        self.assertEqual(task.protocol_task_snapshot['request']['task']['carrier'], package.name)

    def test_subposition_survives_stock_validation_and_duplicate_callback(self):
        category, task, line, package = self._task()
        self._accept(task)
        response = self._callback(task)
        self.assertEqual(response, {'code': 200, 'msg': 'success'})
        self.assertEqual(task.state, 'completed')
        self.assertEqual(package.package_removal_priority, 'B-03')
        self.assertEqual(line.location_dest_id, self.destination)
        self.assertEqual(task.protocol_planned_location_id, self.destination)
        self.assertEqual(task.event_ids.protocol_report['targetPoint'], 'B-03')
        task.picking_id.button_validate()
        self.assertEqual(task.picking_id.state, 'done')
        self.assertEqual(package.package_removal_priority, 'B-03')
        self.assertEqual(self._callback(task), response)
        self.assertEqual(len(task.event_ids), 1)
        quants = self.env['stock.quant'].search([('package_id', '=', package.id), ('location_id', '=', self.destination.id)])
        self.assertEqual(sum(quants.mapped('quantity')), 10)

    def test_actual_stock_destination_is_synchronized_and_stock_posted_once(self):
        category, task, line, package = self._task('tusk-destination')
        self._accept(task)
        self._callback(task, self.actual.barcode)
        self.assertEqual(task.location_dest_id, self.actual)
        self.assertEqual(task.protocol_actual_location_id, self.actual)
        self.assertEqual(task.protocol_planned_location_id, self.destination)
        self.assertEqual(line.location_dest_id, self.actual)
        task.picking_id.button_validate()
        self.assertEqual(task.picking_id.state, 'done')
        self._callback(task, self.actual.barcode)
        quants = self.env['stock.quant'].search([('package_id', '=', package.id), ('location_id', '=', self.actual.id)])
        self.assertEqual(sum(quants.mapped('quantity')), 10)
        self.assertEqual(len(task.event_ids), 1)

    def test_unmatched_or_duplicate_location_does_not_complete(self):
        category, task, line, package = self._task('tusk-destination')
        self._accept(task)
        for code in ['MISSING', 'DUPLICATE']:
            if code == 'DUPLICATE':
                self.actual.agv_map_point = code
                self.destination.agv_map_point = code
            with self.subTest(code=code), self.assertRaises(ValidationError), self.cr.savepoint():
                self._callback(task, code)
            self.assertEqual(task.state, 'accepted')
            self.assertEqual(line.location_dest_id, self.destination)
            self.assertFalse(task.event_ids)

    def test_frozen_destination_is_rejected(self):
        category, task, line, package = self._task('tusk-destination')
        self._accept(task)
        self.actual.is_locking = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task, self.actual.barcode)
        self.assertEqual(line.location_dest_id, self.destination)

    def test_original_storage_capacity_is_enforced(self):
        category, task, line, package = self._task('tusk-destination')
        self._accept(task)
        storage = self.env['stock.storage.category'].create({'name': 'Only five units', 'allow_new_product': 'mixed', 'max_weight': 1000})
        self.env['stock.storage.category.capacity'].create({'storage_category_id': storage.id, 'product_id': self.product.id, 'quantity': 5})
        self.actual.storage_category_id = storage
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task, self.actual.barcode)
        self.assertFalse(task.protocol_actual_location_id)

    def test_protocol_version_is_pinned_across_publication_and_rollback(self):
        category, task, line, package = self._task()
        old_release = task.protocol_release_id
        profile = category.protocol_profile_id
        profile.action_new_draft()
        profile.requirements = '新版本说明'
        profile.action_validate()
        profile.action_publish()
        self.assertNotEqual(profile.active_release_id, old_release)
        self.assertEqual(task.protocol_release_id, old_release)
        profile.action_rollback()
        self.assertEqual(profile.active_release_id, old_release)
        self._accept(task)
        self._callback(task)
        self.assertEqual(package.package_removal_priority, 'B-03')

    def test_active_tasks_freeze_manual_connections_and_device_binding(self):
        category, task, line, package = self._task()
        for record, changes in [(category, {'ip_post': 'http://other'}), (category, {'protocol_allow_subposition': False}),
                                (task.equipment_id, {'category_id': False})]:
            with self.subTest(changes=changes), self.assertRaises(UserError):
                record.write(changes)
        self.assertEqual(category.ip_post, 'http://127.0.0.1:9')

    def test_no_device_secret_fallback_and_no_secret_in_asset_scope(self):
        category, task, line, package = self._task()
        task.equipment_id.write({'api_key': 'old-device-key', 'api_secret': 'old-device-secret', 'endpoint': 'http://old-device'})
        connection = task._dispatch_connection()
        self.assertEqual(connection['api_key'], '')
        self.assertNotIn('old-device', json.dumps(category.protocol_profile_id._scope_snapshot()))

    def test_ordinary_callback_and_direct_workflow_changes_are_rejected(self):
        category, task, line, package = self._task()
        self._accept(task)
        with self.assertRaises(UserError):
            task._receive_event('ordinary-end', 'end')
        for vals in [{'state': 'completed'}, {'protocol_subposition': 'forged'}, {'location_dest_id': self.actual.id}]:
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                task.with_context(blue_wcs_token=False).write(vals)
        with self.assertRaises(AccessError):
            category.write({'protocol_profile_id': False})

    def test_missing_phase_cannot_be_published(self):
        category, task, line, package = self._task()
        category.protocol_profile_id.action_new_draft()
        category.protocol_tests = json.dumps(fixture()['cases'][:3])
        with self.assertRaises(ValidationError):
            category.action_protocol_validate()

    def test_changed_completion_cannot_overwrite_completed_package(self):
        category, task, line, package = self._task()
        self._accept(task)
        self._callback(task)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task, 'C-99')
        self.assertEqual(package.package_removal_priority, 'B-03')

    def test_unknown_outcome_does_not_blindly_become_accepted(self):
        category, task, line, package = self._task()
        connection = task._dispatch_connection()
        response = Mock(status_code=200)
        response.iter_content.return_value = [b'{"msg":"unknown"}']
        with patch('odoo.addons.blue_wcs_protocol.models.transport.requests.post', return_value=response):
            self.assertEqual(send_protocol(connection, task._payload())[0], 'unknown')
        response.close.assert_called_once()
        response = Mock(status_code=500)
        with patch('odoo.addons.blue_wcs_protocol.models.transport.requests.post', return_value=response):
            self.assertEqual(send_protocol(connection, task._payload())[0], 'unknown')

    def test_other_company_location_is_not_resolved(self):
        category, task, line, package = self._task('tusk-destination')
        self._accept(task)
        outside = self.env['stock.location'].create({'name': 'Outside root', 'usage': 'internal',
            'location_id': self.warehouse.view_location_id.id, 'company_id': self.env.company.id,
            'barcode': 'PROTOCOL-OUTSIDE'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task, outside.barcode)

    def test_readonly_inventory_user_cannot_edit_code_or_read_credentials(self):
        category, task, line, package = self._task()
        worker = new_test_user(self.env, login='protocol_readonly_worker', groups='stock.group_stock_user',
                               company_id=self.env.company.id)
        with self.assertRaises(AccessError):
            category.with_user(worker).read(['app_secret'])
        with self.assertRaises(AccessError):
            category.with_user(worker).write({'protocol_code': 'result = {}'})
        with self.assertRaises(AccessError):
            category.with_user(worker).action_protocol_publish()

    def test_valid_location_rolls_back_if_subposition_permission_fails(self):
        example = fixture('tusk-destination')
        code = example['code'].replace('"subposition": ""', '"subposition": "C-03"')
        category = self.env['wcs.equipment.category'].create({'name': 'Atomic callback category',
            'adapter_code': 'protocol', 'ip_post': 'http://127.0.0.1:9', 'submit_path': '/rpc/createTask',
            'protocol_allow_destination': True, 'protocol_destination_root_id': self.root.id,
            'protocol_allow_subposition': False})
        cases = example['cases']
        cases[-1]['expected_result']['subposition'] = 'C-03'
        category.protocol_profile_id.write({'draft_code': code, 'draft_tests': json.dumps(cases)})
        category.action_protocol_validate()
        category.action_protocol_publish()
        task, line, package = make_task(self.env, category, self.warehouse, self.destination, self.product)
        self._accept(task)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task, self.actual.barcode)
        self.assertEqual(line.location_dest_id, self.destination)
        self.assertFalse(task.protocol_actual_location_id)
        self.assertFalse(task.event_ids)

    def test_unsent_and_intermediate_tasks_cannot_apply_completion_updates(self):
        category, task, line, package = self._task()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task)
        other = self.env['wcs.request'].with_context(blue_wcs_token=WCS_TOKEN).create({
            'company_id': task.company_id.id, 'plan_id': task.plan_id.id, 'equipment_id': task.equipment_id.id,
            'step': 2, 'role': 'goods', 'source_point': 'B', 'destination_point': 'C',
            'location_res_id': self.destination.id, 'location_dest_id': self.actual.id,
            'task_type': 'TRANSFER', 'predecessor_id': task.id, 'state': 'waiting'})
        self._accept(task)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task)
        self.assertEqual(other.state, 'waiting')
        self.assertFalse(package.package_removal_priority)

    def test_partial_line_cannot_redirect_unrelated_quantities(self):
        category = make_category(self.env, self.root, 'tusk-destination')
        task, line, package = make_task(self.env, category, self.warehouse, self.destination, self.product)
        line.with_context(blue_wcs_token=WCS_TOKEN).quantity = 15
        self._accept(task)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task, self.actual.barcode)
        self.assertEqual(line.location_dest_id, self.destination)

    def test_accepted_response_uses_pinned_code_and_manual_transport(self):
        category, task, line, package = self._task()
        response = Mock(status_code=200)
        response.iter_content.return_value = [b'{"msg":"success"}']
        with patch('odoo.addons.blue_wcs_protocol.models.transport.requests.post', return_value=response) as post:
            result = send_protocol(task._dispatch_connection(), task._payload())
        self.assertEqual(result[0], 'accepted')
        self.assertEqual(post.call_args.args[0], 'http://127.0.0.1:9/rpc/createTask')
        self.assertEqual(post.call_args.kwargs['json']['taskId'], task.name)
        self.assertFalse(post.call_args.kwargs['allow_redirects'])

    def test_category_parameters_are_versioned_and_cannot_contain_credential_keys(self):
        category = self.env['wcs.equipment.category'].create({'name': 'Parameter category', 'adapter_code': 'protocol',
            'protocol_parameters': {'warehouseCode': 'WH-1'}})
        self.assertEqual(category.protocol_profile_id._scope_snapshot()['device_scope']['parameters'], {'warehouseCode': 'WH-1'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            category.protocol_parameters = {'api_key': 'forbidden-secret'}

    def test_empty_unpublished_category_can_be_removed_without_orphan_asset(self):
        category = self.env['wcs.equipment.category'].create({'name': 'Draft category', 'adapter_code': 'protocol'})
        profile = category.protocol_profile_id
        category.unlink()
        self.assertFalse(profile.exists())

    def test_pending_completed_callback_reserves_a_configured_subposition(self):
        category, first, line, package = self._task()
        self.env['stock.location.coordinate'].create({'name': '3', 'location_code': 'B-03',
                                                     'location_id': self.destination.id})
        self._accept(first)
        self._callback(first)
        second, other_line, other_package = make_task(self.env, category, self.warehouse, self.destination, self.product)
        self._accept(second)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(second)
        self.assertFalse(other_package.package_removal_priority)
        self.assertEqual(second.state, 'accepted')

    def test_original_pallet_capacity_is_enforced(self):
        category, task, line, package = self._task('tusk-destination')
        kind = self.env['stock.package.type'].create({'name': 'Protocol pallet'})
        package.package_type_id = kind
        occupied = self.env['stock.package'].create({'name': 'Occupied protocol pallet', 'package_type_id': kind.id})
        self.env['stock.quant']._update_available_quantity(self.product, self.actual, 1, package_id=occupied)
        storage = self.env['stock.storage.category'].create({'name': 'One pallet slot', 'allow_new_product': 'mixed', 'max_weight': 1000})
        self.env['stock.storage.category.capacity'].create({'storage_category_id': storage.id,
                                                         'package_type_id': kind.id, 'quantity': 1})
        self.actual.storage_category_id = storage
        self._accept(task)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._callback(task, self.actual.barcode)
        self.assertEqual(line.location_dest_id, self.destination)
