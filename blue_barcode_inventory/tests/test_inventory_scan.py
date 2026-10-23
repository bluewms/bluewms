from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.addons.base.tests.common import BaseCommon


@tagged('post_install', '-at_install')
class TestInventoryScan(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Scan count warehouse', 'code': 'SCNT'})
        cls.product = cls.env['product.product'].create({'name': 'Count barcode product', 'is_storable': True, 'barcode': '000COUNTSCAN'})
        cls.client = 'inventory_client_0001'

    def _inventory(self, quantity=100):
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, quantity)
        inventory = self.env['stock.inventory'].create({'location_ids': [Command.set(self.warehouse.lot_stock_id.ids)]})
        inventory.action_start()
        return inventory

    def _session(self, inventory):
        view = self.env['blue.barcode.service'].open_session('inventory', inventory.id, self.client)
        return self.env['blue.barcode.session'].browse(view['id'])

    def _event(self, session, event_key='inventory_event_0001', **payload):
        return session.action_event(self.client, event_key, session.revision, payload or {'raw': self.product.barcode})

    def test_first_scan_replaces_prefill_then_accumulates(self):
        inventory = self._inventory()
        line = inventory.line_ids
        self.assertEqual(line.product_qty, 100)
        self.assertFalse(line.counted)
        session = self._session(inventory)
        self._event(session)
        self.assertEqual(line.product_qty, 1)
        self.assertTrue(line.counted)
        self._event(session, 'inventory_event_0002')
        self.assertEqual(line.product_qty, 2)
        self.assertEqual(line.theoretical_qty, 100)
        self.assertEqual(line._quants().quantity, 100)
        self.assertFalse(inventory.stock_move_ids)

    def test_manual_total_zero_and_continue(self):
        inventory = self._inventory()
        session = self._session(inventory)
        self._event(session, row_key=session._rows()[0]['key'], total=0)
        self.assertTrue(inventory.line_ids.counted)
        self.assertEqual(inventory.line_ids.product_qty, 0)
        self._event(session, 'inventory_event_0002', row_key=session._rows()[0]['key'], total=8)
        self._event(session, 'inventory_event_0003')
        self.assertEqual(inventory.line_ids.product_qty, 9)

    def test_retry_does_not_add_and_reopen_keeps_count(self):
        inventory = self._inventory()
        session = self._session(inventory)
        self._event(session)
        self._event(session)
        self.assertEqual(inventory.line_ids.product_qty, 1)
        session.action_release(self.client)
        second = self._session(inventory)
        self._event(second)
        self.assertEqual(inventory.line_ids.product_qty, 2)

    def test_snapshot_refresh_invalidates_old_counting_context(self):
        inventory = self._inventory()
        session = self._session(inventory)
        self._event(session)
        inventory.line_ids.action_refresh_book()
        with self.assertRaises(UserError):
            self._event(session, 'inventory_event_0002')

    def test_applied_line_not_writable(self):
        inventory = self._inventory()
        session = self._session(inventory)
        self._event(session)
        inventory.line_ids.action_apply()
        with self.assertRaises(UserError):
            self._event(session, 'inventory_event_0002')
        self.assertEqual(inventory.line_ids.product_qty, 1)

    def test_draft_inventory_cannot_open_scan(self):
        inventory = self.env['stock.inventory'].create({'location_ids': [Command.set(self.warehouse.lot_stock_id.ids)]})
        with self.assertRaises(UserError):
            self._session(inventory)

    def test_serial_cannot_accumulate_twice(self):
        self.product.tracking = 'serial'
        lot = self.env['stock.lot'].create({'name': 'SCANSERIAL1', 'product_id': self.product.id, 'company_id': self.env.company.id})
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 1, lot_id=lot)
        inventory = self.env['stock.inventory'].create({'location_ids': [Command.set(self.warehouse.lot_stock_id.ids)]})
        inventory.action_start()
        session = self._session(inventory)
        self._event(session)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._event(session, 'inventory_event_0002')
        self.assertEqual(inventory.line_ids.product_qty, 1)

    def test_second_terminal_and_foreign_product_rejected(self):
        inventory = self._inventory()
        session = self._session(inventory)
        with self.assertRaises(UserError):
            self.env['blue.barcode.service'].open_session('inventory', inventory.id, 'inventory_client_0002')
        other = self.env['product.product'].create({'name': 'Outside count', 'barcode': 'OUTSIDE_COUNT'})
        with self.assertRaises(UserError):
            self._event(session, raw=other.barcode)
        self.assertFalse(inventory.line_ids.counted)

    def test_assigned_regular_counter_can_scan_without_manager_rights(self):
        worker = new_test_user(self.env, login='barcode_counter', groups='stock.group_stock_user', company_id=self.env.company.id)
        inventory = self._inventory()
        # Responsible assignment is immutable after start, so use a new draft.
        inventory.action_state_to_cancel()
        draft = self.env['stock.inventory'].create({'location_ids': [Command.set(self.warehouse.lot_stock_id.ids)], 'responsible_id': worker.id})
        draft.action_start()
        view = self.env['blue.barcode.service'].with_user(worker).open_session('inventory', draft.id, self.client)
        session = self.env['blue.barcode.session'].with_user(worker).browse(view['id'])
        session.action_event(self.client, 'inventory_event_0001', 0, {'raw': self.product.barcode})
        self.assertEqual(draft.line_ids.product_qty, 1)
