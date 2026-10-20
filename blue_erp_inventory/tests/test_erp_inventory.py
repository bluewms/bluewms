from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.blue_erp_interface.tests.common import make_interface


@tagged('post_install', '-at_install')
class TestErpInventory(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'ERP count warehouse', 'code': 'ERPC'})
        cls.root = cls.warehouse.lot_stock_id
        cls.root.barcode = 'ERP-COUNT-STOCK'
        cls.product = cls.env['product.product'].create({'name': 'ERP count product', 'default_code': 'ERP-PRODUCT', 'is_storable': True})

    def _plan(self, quantity=10):
        self.env['stock.quant']._update_available_quantity(self.product, self.root, quantity)
        inventory = self.env['stock.inventory'].create({'location_ids': [Command.set(self.root.ids)]})
        inventory.action_start()
        return inventory

    def test_count_difference_event_is_pinned_and_linked(self):
        interface = make_interface(self.env, self.warehouse, self.product, kind='inventory')
        inventory = self._plan()
        inventory.line_ids.product_qty = 7
        with patch('requests.post') as post:
            inventory.action_state_to_done()
        post.assert_not_called()
        event = inventory.erp_event_ids
        self.assertEqual(len(event), 1)
        self.assertEqual(event.interface_id, interface)
        self.assertEqual(event.inventory_id, inventory)
        self.assertEqual(event.input_snapshot['request']['number'], inventory.name)
        row = event.input_snapshot['candidates'][0]
        self.assertEqual((row['book_quantity'], row['counted_quantity'], row['difference_quantity']), (10, 7, -3))
        event._prepare()
        self.assertEqual(event.delivery_ids.operation, 'count_loss')
        self.assertEqual(event.release_id, interface.profile_id.active_release_id)

    def test_partial_lines_have_distinct_source_keys(self):
        interface = make_interface(self.env, self.warehouse, self.product, kind='inventory')
        other = self.env['product.product'].create({'name': 'Second count item', 'default_code': 'COUNT-OTHER', 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(other, self.root, 5)
        inventory = self._plan()
        inventory.line_ids.filtered(lambda l: l.product_id == self.product).write({'product_qty': 8})
        inventory.line_ids.filtered(lambda l: l.product_id == self.product).action_apply()
        inventory.line_ids.filtered(lambda l: l.product_id == other).write({'product_qty': 4})
        inventory.action_state_to_done()
        self.assertEqual(len(inventory.erp_event_ids), 2)
        self.assertEqual(len(set(inventory.erp_event_ids.mapped('source_key'))), 2)
        self.assertEqual(inventory.erp_event_ids.interface_id, interface)

    def test_zero_difference_has_no_erp_event(self):
        make_interface(self.env, self.warehouse, self.product, kind='inventory')
        inventory = self._plan()
        inventory.action_mark_counted()
        inventory.action_state_to_done()
        self.assertFalse(inventory.erp_event_ids)

    def test_failed_stock_validation_creates_no_event(self):
        make_interface(self.env, self.warehouse, self.product, kind='inventory')
        inventory = self._plan()
        inventory.line_ids.product_qty = 12
        self.root.is_locking = True
        with self.assertRaises(ValidationError):
            inventory.action_state_to_done()
        self.assertEqual(inventory.state, 'in_progress')
        self.assertFalse(inventory.erp_event_ids)
        self.assertFalse(inventory.line_ids.applied)

    def test_native_adjustment_outside_plan_stays_supported(self):
        interface = make_interface(self.env, self.warehouse, self.product, kind='inventory')
        self.env['stock.quant']._update_available_quantity(self.product, self.root, 10)
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.root.id)])
        quant.inventory_quantity = 8
        unrelated = self.env['stock.inventory'].create({'location_ids': [Command.set(self.root.ids)]})
        quant.with_context(default_inventory_id=unrelated.id).action_apply_inventory()
        self.assertEqual(quant.quantity, 8)
        self.assertFalse(interface.event_ids.inventory_id)

    def test_event_inventory_link_cannot_be_forged(self):
        make_interface(self.env, self.warehouse, self.product, kind='inventory')
        inventory = self._plan()
        inventory.line_ids.product_qty = 8
        inventory.action_state_to_done()
        with self.assertRaises(AccessError):
            inventory.erp_event_ids.inventory_id = False

    def test_context_default_cannot_skip_erp_queue(self):
        make_interface(self.env, self.warehouse, self.product, kind='inventory')
        inventory = self._plan()
        inventory.line_ids.product_qty = 8
        inventory.with_context(default_state='done').action_state_to_done()
        self.assertEqual(inventory.erp_event_ids.state, 'queued')
