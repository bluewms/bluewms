import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.addons.base.tests.common import BaseCommon

from ..models.guard import ERP_TOKEN
from .common import done, make_interface, message


@tagged('post_install', '-at_install')
class TestErpWorkflow(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'ERP Warehouse', 'code': 'ERP'})
        cls.product = cls.env['product.product'].create({'name': 'ERP product', 'default_code': 'ERP-PRODUCT', 'is_storable': True})

    def _receive(self, interface=None, **values):
        interface = interface or make_interface(self.env, self.warehouse, self.product)
        interface._receive(message(self.product, **values))
        document = interface.document_ids
        return interface, document, document.picking_ids

    def test_new_interface_has_empty_asset(self):
        interface = make_interface(self.env, self.warehouse, self.product, publish=False)
        interface.profile_id.write({'draft_code': '', 'draft_tests': ''})
        self.assertTrue(interface.profile_id)
        self.assertEqual(interface.profile_id.contract, 'erp_mapping/1')
        self.assertFalse(interface.profile_id.active_release_id)
        self.assertIn('erp_mapping', interface.profile_id._blue_ai_contracts())

    def test_receive_duplicate_is_idempotent_after_completion(self):
        interface, document, picking = self._receive()
        self.assertEqual(picking.state, 'assigned')
        done(picking, 10)
        interface._receive(message(self.product))
        self.assertEqual(interface.document_ids, document)
        self.assertEqual(len(document.picking_ids), 1)
        self.assertEqual(len(document.event_ids), 1)
        picking._erp_enqueue_completion()
        self.assertEqual(len(document.event_ids), 1)

    def test_changed_same_id_and_unknown_product_do_not_overwrite(self):
        interface, document, picking = self._receive()
        for payload in [message(self.product, quantity=9), message(self.product, external_id='ERP-BAD')]:
            if payload['id'] == 'ERP-BAD':
                payload['lines'][0]['product'] = 'MISSING'
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                interface._receive(payload)
        self.assertEqual(picking.move_ids.product_uom_qty, 10)
        self.assertEqual(len(interface.document_ids), 1)

    def test_wrong_unit_and_out_of_scope_location_roll_back(self):
        interface = make_interface(self.env, self.warehouse, self.product)
        for values in [{'source': 'UNKNOWN'}, {'destination': 'UNKNOWN'}]:
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                interface._receive(message(self.product, **values))
        payload = message(self.product)
        payload['lines'][0]['unit'] = 'Unknown unit'
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            interface._receive(payload)
        self.assertFalse(interface.document_ids)

    def test_partial_completion_and_backorder_keep_external_line(self):
        interface, document, first = self._receive()
        action = done(first, 6)
        self.assertEqual(action['res_model'], 'stock.backorder.confirmation')
        wizard = self.env['stock.backorder.confirmation'].with_context(action['context']).create({})
        wizard.process()
        second = document.picking_ids - first
        self.assertEqual(len(second), 1)
        self.assertEqual(second.move_ids.blue_erp_line_id, '10')
        done(second, 4)
        events = document.event_ids.sorted('id')
        self.assertEqual(len(events), 2)
        self.assertEqual([e.input_snapshot['candidates'][0]['quantity'] for e in events], [6, 4])
        self.assertEqual(events[-1].input_snapshot['candidates'][0]['cumulative_quantity'], 10)
        self.assertNotEqual(events[0].event_key, events[1].event_key)

    def test_overdelivery_is_rejected_before_stock_changes(self):
        interface, document, picking = self._receive()
        with self.assertRaises(ValidationError):
            done(picking, 11)
        self.assertNotEqual(picking.state, 'done')
        self.assertFalse(document.event_ids)

    def test_completion_never_sends_http_and_keeps_version(self):
        interface, document, picking = self._receive()
        release = document.release_id
        interface.profile_id.action_new_draft()
        interface.profile_id.write({'draft_code': 'result = {}'})
        with patch('odoo.addons.blue_erp_interface.tools.transport.requests.post') as post:
            done(picking, 10)
        post.assert_not_called()
        event = document.event_ids
        self.assertEqual(event.release_id, release)
        event._prepare()
        self.assertEqual(event.delivery_ids.body['lines'][0]['quantity'], 10)

    def test_inventory_difference_snapshot_survives_native_reset(self):
        interface = make_interface(self.env, self.warehouse, self.product, kind='inventory')
        quant = self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 10)
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.warehouse.lot_stock_id.id)])
        quant.inventory_quantity = 7
        with patch('odoo.addons.blue_erp_interface.tools.transport.requests.post') as post:
            quant.action_apply_inventory()
        post.assert_not_called()
        self.assertEqual(quant.quantity, 7)
        row = interface.event_ids.input_snapshot['candidates'][0]
        self.assertEqual((row['book_quantity'], row['counted_quantity'], row['difference_quantity']), (10, 7, -3))
        interface.event_ids._prepare()
        self.assertEqual(interface.event_ids.delivery_ids.operation, 'count_loss')

    def test_zero_count_difference_does_not_create_event(self):
        interface = make_interface(self.env, self.warehouse, self.product, kind='inventory')
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 10)
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.warehouse.lot_stock_id.id)])
        quant.inventory_quantity = 10
        quant.action_apply_inventory()
        self.assertFalse(interface.event_ids)

    def test_overlap_count_interface_is_rejected(self):
        make_interface(self.env, self.warehouse, self.product, kind='inventory')
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            make_interface(self.env, self.warehouse, self.product, kind='inventory')

    def test_pending_event_blocks_connection_and_interface_changes(self):
        interface, document, picking = self._receive()
        done(picking, 10)
        with self.assertRaises(UserError):
            interface.connection_id.app_key = 'replacement'
        with self.assertRaises(UserError):
            interface.inbound_lines_key = 'details'

    def test_unknown_delivery_requires_explicit_reconciliation(self):
        interface, document, picking = self._receive()
        done(picking, 10)
        event = document.event_ids
        event._prepare()
        delivery = event.delivery_ids
        delivery._finish('unknown')
        with self.assertRaises(UserError):
            event.action_retry()
        with self.assertRaises(UserError):
            delivery.action_confirm_not_sent()
        delivery.reconciliation_note = 'ERP administrator confirmed no matching event.'
        delivery.action_confirm_not_sent()
        self.assertEqual(delivery.state, 'pending')
        delivery._finish('unknown')
        delivery.reconciliation_note = 'ERP document exists and was checked.'
        delivery.action_confirm_done()
        self.assertEqual(event.state, 'done')
        with self.assertRaises(UserError):
            delivery.action_confirm_not_sent()

    def test_public_rpc_cannot_forge_assets_or_history(self):
        interface, document, picking = self._receive()
        with self.assertRaises(AccessError):
            document.normalized = {}
        with self.assertRaises(AccessError):
            picking.blue_erp_document_id = False
        done(picking, 10)
        event = document.event_ids
        with self.assertRaises(AccessError):
            event.state = 'done'
        event._prepare()
        with self.assertRaises(AccessError):
            event.delivery_ids.body = {'forged': True}

    def test_credentials_and_cross_company_records_are_inaccessible(self):
        interface, document, picking = self._receive()
        user = new_test_user(self.env, login='erp_stock_operator', groups='stock.group_stock_user',
                             company_id=self.env.company.id, company_ids=[(6, 0, self.env.company.ids)])
        with self.assertRaises(AccessError):
            interface.connection_id.with_user(user).read(['app_key'])
        with self.assertRaises(AccessError):
            interface.with_user(user).action_publish()
        other = self.env['res.company'].create({'name': 'Other ERP company'})
        remote_user = new_test_user(self.env, login='erp_remote_operator', groups='stock.group_stock_manager',
                                    company_id=other.id, company_ids=[(6, 0, other.ids)])
        self.assertFalse(document.with_user(remote_user).search([('id', '=', document.id)]))

    def test_split_groups_create_distinct_pickings_with_same_source(self):
        interface = make_interface(self.env, self.warehouse, self.product)
        payload = message(self.product)
        payload['lines'][0]['group'] = 'first'
        payload['lines'].append({**payload['lines'][0], 'id': '20', 'group': 'second'})
        interface._receive(payload)
        self.assertEqual(len(interface.document_ids.picking_ids), 2)
        self.assertEqual(set(interface.document_ids.picking_ids.move_ids.mapped('blue_erp_line_id')), {'10', '20'})

    def test_outbound_shortage_remains_native_waiting(self):
        interface = make_interface(self.env, self.warehouse, self.product, kind='outgoing')
        interface._receive(message(self.product))
        self.assertNotEqual(interface.document_ids.picking_ids.state, 'done')
        self.assertEqual(interface.document_ids.picking_ids.move_ids.product_uom_qty, 10)

    def test_future_publish_does_not_replace_existing_document_version(self):
        interface, document, picking = self._receive()
        original = document.release_id
        interface.action_new_draft()
        interface.profile_id.write({'draft_code': interface.code + '\n'})
        interface.action_validate()
        interface.action_publish()
        self.assertNotEqual(interface.profile_id.active_release_id, original)
        done(picking, 10)
        self.assertEqual(document.event_ids.release_id, original)

    def test_config_cannot_change_while_source_picking_is_unfinished(self):
        interface, document, picking = self._receive()
        with self.assertRaises(UserError):
            interface.connection_id.app_key = 'changed'
        with self.assertRaises(UserError):
            interface.location_dest_id = self.warehouse.view_location_id

    def test_response_steps_keep_successful_step_and_snapshot(self):
        interface, document, picking = self._receive()
        done(picking, 10)
        event = document.event_ids
        event._prepare()
        first = event.delivery_ids
        second = self.env['blue.erp.delivery'].with_context(blue_erp_token=ERP_TOKEN).create({
            'event_id': event.id, 'company_id': self.env.company.id, 'sequence': 2,
            'operation': 'complete', 'path': '/complete', 'body': {'second': True}})
        first._finish('done', external_number='ERP-1')
        second._finish('unknown')
        self.assertEqual(event.state, 'unknown')
        second.reconciliation_note = 'Verified second step has not executed.'
        second.action_confirm_not_sent()
        self.assertEqual(first.state, 'done')
        self.assertEqual(first.external_number, 'ERP-1')
        self.assertEqual(second.state, 'pending')

    def test_internal_transfer_creates_and_completes_native_document(self):
        interface = make_interface(self.env, self.warehouse, self.product, kind='internal',
            location_src_id=self.warehouse.lot_stock_id.id, location_dest_id=self.warehouse.lot_stock_id.id)
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 10)
        interface._receive(message(self.product))
        picking = interface.document_ids.picking_ids
        done(picking, 10)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(interface.event_ids.input_snapshot['request']['kind'], 'internal')

    def test_manual_change_to_unapproved_location_cannot_complete(self):
        interface, document, picking = self._receive()
        outside = self.env['stock.location'].create({'name': 'Outside ERP scope', 'usage': 'internal',
            'location_id': self.warehouse.view_location_id.id, 'company_id': self.env.company.id})
        picking.move_line_ids.location_dest_id = outside
        with self.assertRaises(ValidationError):
            done(picking, 10)

    def test_reordered_erp_lines_return_same_document(self):
        interface = make_interface(self.env, self.warehouse, self.product)
        payload = message(self.product)
        payload['lines'].append({**payload['lines'][0], 'id': '20'})
        interface._receive(payload)
        original = interface.document_ids
        payload['lines'].reverse()
        interface._receive(payload)
        self.assertEqual(interface.document_ids, original)
