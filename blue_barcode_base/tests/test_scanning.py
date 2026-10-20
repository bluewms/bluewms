from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.addons.base.tests.common import BaseCommon


@tagged('post_install', '-at_install')
class TestBarcodeScanning(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Scan warehouse', 'code': 'SCAN'})
        cls.product = cls.env['product.product'].create({'name': 'Scan product', 'is_storable': True, 'barcode': '000SCAN1'})
        cls.client = 'client_barcode_000001'
        cls.service = cls.env['blue.barcode.service']

    def _picking(self, quantity=10):
        picking = self.env['stock.picking'].create({'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.warehouse.in_type_id.default_location_src_id.id,
            'location_dest_id': self.warehouse.lot_stock_id.id})
        self.env['stock.move'].create({'picking_id': picking.id,
            'product_id': self.product.id, 'product_uom_qty': quantity, 'uom_id': self.product.uom_id.id,
            'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id})
        picking.action_confirm()
        return picking

    def _session(self, picking=None):
        picking = picking or self._picking()
        view = self.service.open_session('picking', picking.id, self.client)
        return self.env['blue.barcode.session'].browse(view['id'])

    def _scan(self, session, event='barcode_event_000001', payload=None, revision=None):
        return session.action_event(self.client, event, session.revision if revision is None else revision,
                                    payload or {'raw': self.product.barcode})

    def test_two_real_scans_add_twice_but_retry_once(self):
        session = self._session()
        result = self._scan(session)
        self.assertEqual(result['event']['quantity'], 1)
        replay = self._scan(session, revision=0)
        self.assertTrue(replay['replayed'])
        self.assertEqual(session.picking_id.move_line_ids.quantity, 1)
        self._scan(session, event='barcode_event_000002')
        self.assertEqual(session.picking_id.move_line_ids.quantity, 2)
        self.assertEqual(len(session.event_ids), 2)

    def test_reused_id_with_different_payload_rejected(self):
        session = self._session()
        self._scan(session)
        with self.assertRaises(ValidationError):
            self._scan(session, payload={'raw': 'DIFFERENT'})
        self.assertEqual(session.picking_id.move_line_ids.quantity, 1)

    def test_reservation_is_not_already_scanned(self):
        picking = self._picking()
        values = {'move_id': picking.move_ids.id, 'picking_id': picking.id,
            'product_id': self.product.id, 'uom_id': self.product.uom_id.id,
            'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id,
            'quantity': 10, 'picked': False}
        if picking.move_line_ids:
            picking.move_line_ids.write({'quantity': 10, 'picked': False})
        else:
            self.env['stock.move.line'].create(values)
        session = self._session(picking)
        self.assertEqual(session._rows()[0]['quantity'], 0)
        self._scan(session)
        self.assertEqual(picking.move_line_ids.quantity, 1)
        self.assertTrue(picking.move_line_ids.picked)

    def test_overquantity_and_negative_total_rejected(self):
        session = self._session(self._picking(1))
        self._scan(session)
        with self.assertRaises(UserError):
            self._scan(session, event='barcode_event_000002')
        with self.assertRaises(ValidationError):
            self._scan(session, event='barcode_event_000003', payload={'row_key': session._rows()[0]['key'], 'total': -1})
        self.assertEqual(session.picking_id.move_line_ids.quantity, 1)

    def test_manual_total_then_increment(self):
        session = self._session()
        row = session._rows()[0]
        self._scan(session, payload={'row_key': row['key'], 'total': 8})
        self._scan(session, event='barcode_event_000002')
        self.assertEqual(session.picking_id.move_line_ids.quantity, 9)

    def test_second_terminal_requires_explicit_takeover(self):
        session = self._session()
        with self.assertRaises(UserError):
            self.service.open_session('picking', session.picking_id.id, 'client_barcode_000002')
        other = self.service.open_session('picking', session.picking_id.id, 'client_barcode_000002', takeover=True)
        self.assertNotEqual(other['id'], session.id)
        self.assertEqual(session.state, 'closed')
        with self.assertRaises(UserError):
            self._scan(session)

    def test_external_demand_change_stops_stale_session(self):
        session = self._session()
        session.picking_id.move_ids.product_uom_qty = 4
        with self.assertRaises(UserError):
            self._scan(session)
        self.assertFalse(session.event_ids)

    def test_arbitrary_crud_blocked(self):
        session = self._session()
        with self.assertRaises(AccessError):
            session.write({'revision': 100})
        with self.assertRaises(AccessError):
            self.env['blue.barcode.event'].create({'session_id': session.id, 'event_key': 'injected', 'payload_hash': 'x', 'result': {}})
        with self.assertRaises(AccessError):
            session.unlink()

    def test_other_user_cannot_use_session(self):
        session = self._session()
        other = new_test_user(self.env, login='barcode_other', groups='stock.group_stock_user', company_id=self.env.company.id)
        with self.assertRaises(AccessError):
            session.with_user(other).action_event(self.client, 'barcode_event_000001', 0, {'raw': self.product.barcode})

    def test_regular_stock_worker_can_scan_own_session(self):
        picking = self._picking()
        worker = new_test_user(self.env, login='barcode_worker', groups='stock.group_stock_user', company_id=self.env.company.id)
        view = self.service.with_user(worker).open_session('picking', picking.id, self.client)
        session = self.env['blue.barcode.session'].with_user(worker).browse(view['id'])
        session.action_event(self.client, 'barcode_event_000001', 0, {'raw': self.product.barcode})
        self.assertEqual(picking.move_line_ids.quantity, 1)

    def test_batch_keeps_picking_ownership(self):
        first, second = self._picking(), self._picking()
        batch = self.env['stock.picking.batch'].create({'picking_type_id': self.warehouse.in_type_id.id,
            'picking_ids': [Command.set((first | second).ids)]})
        view = self.service.open_session('batch', batch.id, self.client)
        session = self.env['blue.barcode.session'].browse(view['id'])
        with self.assertRaises(UserError):
            self._scan(session)
        row = next(r for r in view['rows'] if r['picking_id'] == second.id)
        self._scan(session, payload={'raw': self.product.barcode, 'group': row['group']})
        self.assertFalse(first.move_line_ids.filtered('picked'))
        self.assertEqual(second.move_line_ids.quantity, 1)

    def test_batch_resume_excludes_cancelled_pickings(self):
        first, second = self._picking(), self._picking()
        batch = self.env['stock.picking.batch'].create({'picking_type_id': self.warehouse.in_type_id.id,
            'picking_ids': [Command.set((first | second).ids)]})
        first.action_cancel()
        view = self.service.open_session('batch', batch.id, self.client)
        self.assertTrue(view['rows'])
        self.assertEqual({row['picking_id'] for row in view['rows']}, {second.id})

    def test_home_lookup_is_readonly(self):
        root = self.warehouse.lot_stock_id
        root.barcode = 'SCAN_LOCATION_1'
        before = self.env['stock.picking'].search_count([])
        matches = self.service.lookup(root.barcode)
        self.assertEqual(matches, [{'id': root.id, 'kind': 'location', 'name': root.display_name}])
        self.assertEqual(self.env['stock.picking'].search_count([]), before)
        self.assertEqual(len(self.service.menu_entries()), 4)

    def test_native_validation_records_only_scanned_quantity(self):
        session = self._session(self._picking(1))
        self._scan(session)
        result = session.action_execute(self.client, session.revision, 'validate')
        self.assertFalse(result['action'])
        self.assertEqual(session.picking_id.state, 'done')
        self.assertEqual(session.picking_id.move_ids.quantity, 1)

    def test_product_then_lot_counts_only_after_complete(self):
        self.product.tracking = 'lot'
        lot = self.env['stock.lot'].create({'name': 'LOT-SCAN-1', 'product_id': self.product.id, 'company_id': self.env.company.id})
        session = self._session()
        result = self._scan(session)
        self.assertTrue(result['event']['pending'])
        self.assertFalse(session.picking_id.move_line_ids.picked)
        self._scan(session, event='barcode_event_000002', payload={'raw': lot.name})
        self.assertEqual(session.picking_id.move_line_ids.lot_id, lot)
        self.assertEqual(session.picking_id.move_line_ids.quantity, 1)
        self.assertFalse((session.scan_context or {}).get('pending'))

    def test_new_lot_requires_manual_authorization(self):
        self.product.tracking = 'lot'
        session = self._session()
        self._scan(session)
        with self.assertRaises(UserError):
            self._scan(session, event='barcode_event_000002', payload={'raw': 'UNAUTHORIZED-LOT'})
        self.assertFalse(self.env['stock.lot'].search([('name', '=', 'UNAUTHORIZED-LOT')]))

    def test_cancel_pending_product_does_not_change_quantity(self):
        self.product.tracking = 'lot'
        session = self._session()
        self._scan(session)
        session.cancel_pending_product(self.client, session.revision)
        self.assertFalse((session.scan_context or {}).get('pending'))
        self.assertFalse(session.picking_id.move_line_ids.picked)

    def test_packaging_barcode_converts_once(self):
        box = self.env['uom.uom'].create({'name': 'Scan Box 12', 'relative_uom_id': self.product.uom_id.id, 'relative_factor': 12})
        self.env['product.uom'].create({'product_id': self.product.id, 'uom_id': box.id, 'barcode': 'SCANBOX12'})
        session = self._session(self._picking(100))
        self._scan(session, payload={'raw': 'SCANBOX12'})
        self.assertEqual(session.picking_id.move_line_ids.quantity, 12)
        explicit = {'quantity': 12, 'uom': self.product.uom_id.name, 'code': 'SCANBOX12'}
        self.assertEqual(session._quantity_in_product_uom(self.product, explicit), 12)

    def test_event_status_distinguishes_saved_and_never_submitted(self):
        session = self._session()
        self._scan(session)
        self.assertTrue(session.event_status(self.client, 'barcode_event_000001')['found'])
        self.assertFalse(session.event_status(self.client, 'barcode_event_000002')['found'])

    def test_gs1_product_lot_quantity_uses_native_parser(self):
        nomenclature = self.env['barcode.nomenclature'].create({'name': 'Scan GS1', 'is_gs1_nomenclature': True})
        self.env['barcode.rule'].create([
            {'name': 'GTIN', 'barcode_nomenclature_id': nomenclature.id, 'type': 'product', 'encoding': 'gs1-128',
             'pattern': r'(01)(\d{14})', 'gs1_content_type': 'identifier', 'sequence': 1},
            {'name': 'Lot', 'barcode_nomenclature_id': nomenclature.id, 'type': 'lot', 'encoding': 'gs1-128',
             'pattern': r'(10)([A-Z0-9]+)', 'gs1_content_type': 'alpha', 'sequence': 2},
            {'name': 'Qty', 'barcode_nomenclature_id': nomenclature.id, 'type': 'quantity', 'encoding': 'gs1-128',
             'pattern': r'(30)(\d{1,8})', 'gs1_content_type': 'measure', 'sequence': 3}])
        self.env.company.nomenclature_id = nomenclature
        self.product.write({'tracking': 'lot', 'barcode': '09506000134352'})
        lot = self.env['stock.lot'].create({'name': 'LOT1', 'product_id': self.product.id, 'company_id': self.env.company.id})
        session = self._session(self._picking(100))
        self._scan(session, payload={'raw': '010950600013435210LOT1\x1d3012'})
        self.assertEqual(session.picking_id.move_line_ids.quantity, 12)
        self.assertEqual(session.picking_id.move_line_ids.lot_id, lot)

    def test_changed_manual_capability_invalidates_session(self):
        session = self._session()
        session.picking_id.picking_type_id.blue_barcode_allow_overquantity = True
        with self.assertRaises(UserError):
            self._scan(session)

    def test_pack_action_requires_capability_and_selected_group(self):
        picking = self._picking()
        picking.picking_type_id.blue_barcode_allow_pack = True
        session = self._session(picking)
        self._scan(session)
        group = session._rows()[0]['group']
        result = session.action_execute(self.client, session.revision, 'pack', group)
        self.assertEqual(len(picking.move_line_ids.result_package_id), 1)
        self.assertEqual(picking.move_line_ids.quantity, 1)

    def test_confirmed_destination_cannot_count_into_different_page(self):
        picking = self._picking()
        first, second = self.env['stock.location'].create([
            {'name': 'Scan destination A', 'location_id': self.warehouse.lot_stock_id.id,
             'company_id': self.env.company.id, 'barcode': 'SCAN_DEST_A'},
            {'name': 'Scan destination B', 'location_id': self.warehouse.lot_stock_id.id,
             'company_id': self.env.company.id, 'barcode': 'SCAN_DEST_B'}])
        picking.move_line_ids.location_dest_id = first
        move = self.env['stock.move'].create({'picking_id': picking.id, 'product_id': self.product.id,
            'product_uom_qty': 10, 'uom_id': self.product.uom_id.id,
            'location_id': picking.location_id.id, 'location_dest_id': second.id})
        move._action_confirm()
        session = self._session(picking)
        self._scan(session, payload={'raw': first.barcode})
        group = next(row['group'] for row in session._rows() if row['destination_id'] == second.id)
        with self.assertRaises(UserError):
            self._scan(session, event='barcode_event_000002', payload={'raw': self.product.barcode, 'group': group})
        self.assertFalse(picking.move_line_ids.filtered('picked'))
