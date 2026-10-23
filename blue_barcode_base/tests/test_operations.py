from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon


@tagged('post_install', '-at_install')
class TestBarcodeOperations(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Terminal operations', 'code': 'TERM'})
        cls.product = cls.env['product.product'].create({'name': 'Operation product', 'is_storable': True, 'barcode': 'TERM-1'})
        cls.client = 'terminal_operations_client'

    def _picking(self, amount=10):
        picking = self.env['stock.picking'].create({'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.warehouse.in_type_id.default_location_src_id.id,
            'location_dest_id': self.warehouse.lot_stock_id.id})
        self.env['stock.move'].create({'picking_id': picking.id, 'product_id': self.product.id,
            'product_uom_qty': amount, 'uom_id': self.product.uom_id.id,
            'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id})
        picking.action_confirm()
        return picking

    def _session(self, picking=None, batch=None):
        target = batch or picking or self._picking()
        view = self.env['blue.barcode.service'].open_session('batch' if batch else 'picking', target.id, self.client)
        return self.env['blue.barcode.session'].browse(view['id'])

    def _scan(self, session):
        row = session._rows()[0]
        return session.action_event(self.client, 'terminal_operations_event', session.revision,
            {'raw': self.product.barcode, 'group': row['group'], 'row_key': row['key']})

    def _wizard(self, action):
        self.assertEqual(action['res_model'], 'stock.backorder.confirmation')
        return self.env['stock.backorder.confirmation'].with_context(action['context']).create({})

    def test_reserved_unpicked_quantities_cannot_be_validated(self):
        picking = self._picking()
        if picking.move_line_ids:
            picking.move_line_ids.write({'quantity': 10, 'picked': False})
        else:
            self.env['stock.move.line'].create({'move_id': picking.move_ids.id, 'picking_id': picking.id,
                'product_id': self.product.id, 'uom_id': self.product.uom_id.id,
                'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id,
                'quantity': 10, 'picked': False})
        session = self._session(picking)
        self.assertFalse(session._view()['operation']['validate'])
        with self.assertRaises(UserError):
            session.action_execute(self.client, session.revision, 'validate')
        self.assertNotEqual(picking.state, 'done')
        self.assertFalse(picking.move_line_ids.picked)

    def test_partial_validation_creates_backorder_and_refreshes_completion(self):
        self.warehouse.in_type_id.create_backorder = 'ask'
        session = self._session()
        self._scan(session)
        review = session.action_validation_review(self.client, session.revision)
        self.assertFalse(review['complete'])
        self.assertEqual(review['lines'][0]['remaining'], 9)
        result = session.action_execute(self.client, session.revision, 'validate')
        self.assertEqual(session.picking_id.state, 'assigned')
        self._wizard(result['action']).process()
        view = session.action_view(self.client)
        self.assertEqual(view['state'], 'closed')
        self.assertTrue(view['outcome']['ended'])
        self.assertEqual(session.picking_id.move_ids.quantity, 1)
        self.assertEqual(session.picking_id.backorder_ids.move_ids.product_uom_qty, 9)
        self.assertEqual(view['outcome']['backorders'][0]['id'], session.picking_id.backorder_ids.id)

    def test_partial_validation_can_cancel_remaining_without_inventing_quantity(self):
        self.warehouse.in_type_id.create_backorder = 'ask'
        session = self._session()
        self._scan(session)
        result = session.action_execute(self.client, session.revision, 'validate')
        self._wizard(result['action']).process_cancel_backorder()
        self.assertEqual(session.action_view(self.client)['state'], 'closed')
        self.assertEqual(session.picking_id.move_ids.quantity, 1)
        self.assertFalse(session.picking_id.backorder_ids)

    def test_pending_tracking_blocks_footer_operations(self):
        self.product.tracking = 'lot'
        self.warehouse.in_type_id.blue_barcode_allow_pack = True
        session = self._session()
        self._scan(session)
        status = session._view()['operation']
        self.assertFalse(status['validate'])
        self.assertFalse(status['pack'])
        for action in ('validate', 'pack', 'cancel'):
            with self.assertRaises(UserError):
                session.action_execute(self.client, session.revision, action, session._rows()[0]['group'])

    def test_batch_validation_detaches_unscanned_picking(self):
        self.warehouse.in_type_id.create_backorder = 'ask'
        first, second = self._picking(), self._picking()
        batch = self.env['stock.picking.batch'].create({'picking_type_id': self.warehouse.in_type_id.id,
            'picking_ids': [Command.set((first | second).ids)]})
        session = self._session(batch=batch)
        scanned = self.env['stock.picking'].browse(session._rows()[0]['picking_id'])
        unscanned = (first | second) - scanned
        self._scan(session)
        result = session.action_execute(self.client, session.revision, 'validate')
        self._wizard(result['action']).process()
        view = session.action_view(self.client)
        self.assertEqual(view['state'], 'closed')
        self.assertEqual(scanned.state, 'done')
        self.assertNotIn(unscanned.state, ('done', 'cancel'))
        # Native automatic batching may place the untouched picking in a new batch.
        self.assertNotEqual(unscanned.batch_id, batch)
        self.assertEqual(scanned.move_ids.quantity, 1)

    def test_cancel_batch_preserves_original_stock_operations(self):
        picking = self._picking()
        batch = self.env['stock.picking.batch'].create({'picking_type_id': self.warehouse.in_type_id.id,
            'picking_ids': [Command.set(picking.ids)]})
        session = self._session(batch=batch)
        session.action_execute(self.client, session.revision, 'cancel')
        self.assertEqual(batch.state, 'cancel')
        self.assertNotIn(picking.state, ('done', 'cancel'))
        self.assertFalse(picking.batch_id)

    def test_print_and_document_actions_are_bounded_and_do_not_change_counts(self):
        session = self._session()
        self._scan(session)
        for action, report in [('print_operations', 'stock.report_picking'), ('print_delivery', 'stock.report_deliveryslip')]:
            result = session.action_document(self.client, action)
            self.assertEqual(result['type'], 'ir.actions.report')
            self.assertEqual(result['report_name'], report)
        self.assertEqual(session.action_document(self.client, 'document')['res_id'], session.picking_id.id)
        self.assertEqual(session.action_document(self.client, 'labels')['target'], 'new')
        self.assertEqual(session.picking_id.move_ids.quantity, 1)
        other = self._picking()
        with self.assertRaises(AccessError):
            session.action_document(self.client, 'document', other.id)
        with self.assertRaises(AccessError):
            session.action_document(self.client, 'button_validate')
        with self.assertRaises(ValidationError):
            session.action_document(self.client, 'document', True)

    def test_completed_transfer_exposes_return_without_creating_it(self):
        session = self._session(self._picking(1))
        self._scan(session)
        session.action_execute(self.client, session.revision, 'validate')
        self.assertIn('return_document', [option['key'] for option in session._view()['documents']])
        before = self.env['stock.picking'].search_count([])
        action = session.action_document(self.client, 'return_document')
        self.assertEqual(action['res_id'], session.picking_id.id)
        self.assertEqual(self.env['stock.picking'].search_count([]), before)

    def test_scan_policy_cannot_cancel_the_operation(self):
        session = self._session()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            with patch.object(type(session), '_decide', return_value={
                'action': 'count', 'keys': [session._rows()[0]['key']], 'after': 'cancel'}):
                self._scan(session)
        self.assertNotIn(session.picking_id.state, ('done', 'cancel'))
        self.assertFalse(session.event_ids)
