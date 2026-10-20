from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged
from odoo.addons.base.tests.common import BaseCommon


@tagged('post_install', '-at_install')
class TestInventory(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Inventory warehouse', 'code': 'INVT'})
        cls.root = cls.warehouse.lot_stock_id
        cls.bin_a = cls.env['stock.location'].create({'name': 'Count A', 'location_id': cls.root.id, 'company_id': cls.env.company.id})
        cls.bin_b = cls.env['stock.location'].create({'name': 'Count B', 'location_id': cls.root.id, 'company_id': cls.env.company.id})
        cls.product = cls.env['product.product'].create({'name': 'Count product', 'is_storable': True, 'default_code': 'COUNT-1'})
        cls.other = cls.env['product.product'].create({'name': 'Count other', 'is_storable': True, 'default_code': 'COUNT-2'})

    def _quant(self, quantity=10, product=None, location=None, lot=None, package=None, owner=None):
        product, location = product or self.product, location or self.bin_a
        self.env['stock.quant']._update_available_quantity(product, location, quantity,
            lot_id=lot, package_id=package, owner_id=owner)
        return self.env['stock.quant'].search([('product_id', '=', product.id), ('location_id', '=', location.id),
            ('lot_id', '=', lot.id if lot else False), ('package_id', '=', package.id if package else False),
            ('owner_id', '=', owner.id if owner else False)])

    def _inventory(self, start=True, **values):
        inventory = self.env['stock.inventory'].create({'location_ids': [Command.set(self.root.ids)], **values})
        if start:
            inventory.action_start()
        return inventory

    def test_start_creates_lines_without_changing_quantity(self):
        quant = self._quant()
        inventory = self._inventory()
        self.assertEqual(inventory.state, 'in_progress')
        self.assertEqual(inventory.line_ids.theoretical_qty, 10)
        self.assertEqual(inventory.line_ids.product_qty, 10)
        self.assertFalse(inventory.line_ids.counted)
        self.assertEqual(quant.quantity, 10)
        self.assertEqual(quant.current_inventory_id, inventory)

    def test_count_loss_applies_once_and_links_exact_ledger(self):
        quant = self._quant()
        inventory = self._inventory()
        inventory.line_ids.product_qty = 7
        with patch('requests.post') as post:
            inventory.action_state_to_done()
        post.assert_not_called()
        self.assertEqual(quant.quantity, 7)
        self.assertEqual(inventory.state, 'done')
        self.assertTrue(inventory.line_ids.applied)
        self.assertEqual(inventory.line_ids.theoretical_qty, 10)
        self.assertEqual(inventory.line_ids.difference_qty, -3)
        self.assertEqual(inventory.stock_move_ids.quantity, 3)
        self.assertEqual(inventory.stock_move_ids.inventory_line_id, inventory.line_ids)
        self.assertFalse(quant.current_inventory_id)
        with self.assertRaises(UserError):
            inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 7)

    def test_count_gain_uses_native_move(self):
        quant = self._quant()
        inventory = self._inventory()
        inventory.line_ids.product_qty = 12
        inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 12)
        self.assertEqual(inventory.stock_move_ids.quantity, 2)
        self.assertEqual(inventory.stock_move_ids.location_dest_id, self.bin_a)

    def test_missing_stock_creates_zero_quant_then_adjustment(self):
        inventory = self._inventory(start_empty=True)
        line = self.env['stock.inventory.line'].create({'inventory_id': inventory.id, 'product_id': self.product.id,
            'location_id': self.bin_a.id, 'product_qty': 5})
        self.assertEqual(line.theoretical_qty, 0)
        self.assertFalse(line._quants())
        inventory.action_state_to_done()
        self.assertEqual(line._book_quantity(), 5)
        self.assertEqual(inventory.stock_move_ids.quantity, 5)

    def test_zero_prefill_requires_explicit_confirmation(self):
        quant = self._quant()
        inventory = self._inventory(prefill_counted_quantity='zero')
        self.assertEqual(inventory.line_ids.product_qty, 0)
        with self.assertRaises(UserError):
            inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 10)
        inventory.action_mark_counted()
        inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 0)

    def test_zero_difference_finishes_without_stock_change(self):
        quant = self._quant()
        inventory = self._inventory()
        inventory.action_mark_counted()
        inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 10)
        self.assertFalse(quant.current_inventory_id)

    def test_book_change_requires_refresh_and_recount(self):
        quant = self._quant()
        inventory = self._inventory()
        inventory.line_ids.product_qty = 7
        self.env['stock.quant']._update_available_quantity(self.product, self.bin_a, 2)
        with self.assertRaises(UserError):
            inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 12)
        inventory.line_ids.action_refresh_book()
        self.assertEqual(inventory.line_ids.theoretical_qty, 12)
        self.assertFalse(inventory.line_ids.counted)
        inventory.line_ids.product_qty = 9
        inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 9)

    def test_owner_and_package_dimensions_are_independent(self):
        owner = self.env['res.partner'].create({'name': 'Count owner'})
        package = self.env['stock.package'].create({'name': 'Count package'})
        first = self._quant(quantity=4)
        second = self._quant(quantity=8, package=package)
        third = self._quant(quantity=6, owner=owner)
        inventory = self._inventory()
        self.assertEqual(len(inventory.line_ids), 3)
        inventory.action_mark_counted()
        inventory.line_ids.filtered(lambda l: l.package_id == package).product_qty = 5
        inventory.action_state_to_done()
        self.assertEqual((first.quantity, second.quantity, third.quantity), (4, 5, 6))
        self.assertEqual(inventory.stock_move_ids.package_id, package)

    def test_nested_locations_and_exact_location_option(self):
        self._quant(location=self.root)
        self._quant(quantity=3)
        inventory = self._inventory(exclude_sublocation=True)
        self.assertEqual(inventory.line_ids.location_id, self.root)
        inventory.action_state_to_cancel()
        expanded = self._inventory()
        self.assertEqual(set(expanded.line_ids.location_id.ids), {self.root.id, self.bin_a.id})

    def test_category_scope_includes_descendants(self):
        category = self.env['product.category'].create({'name': 'Count parent'})
        child = self.env['product.category'].create({'name': 'Count child', 'parent_id': category.id})
        self.product.categ_id = child
        self._quant()
        self._quant(product=self.other)
        inventory = self._inventory(product_selection='category', category_id=category.id)
        self.assertEqual(inventory.line_ids.product_id, self.product)

    def test_lot_scope_and_serial_quantities(self):
        self.product.tracking = 'lot'
        lot_a, lot_b = self.env['stock.lot'].create([{'name': n, 'product_id': self.product.id,
            'company_id': self.env.company.id} for n in ['COUNT-LOT-A', 'COUNT-LOT-B']])
        self._quant(lot=lot_a)
        self._quant(quantity=4, lot=lot_b)
        inventory = self._inventory(product_selection='lot', product_ids=[Command.set(self.product.ids)], lot_ids=[Command.set(lot_a.ids)])
        self.assertEqual(inventory.line_ids.prod_lot_id, lot_a)
        inventory.line_ids.product_qty = 8
        inventory.action_state_to_done()
        self.assertEqual(inventory.stock_move_ids.lot_id, lot_a)

    def test_serial_count_cannot_be_two(self):
        self.product.tracking = 'serial'
        lot = self.env['stock.lot'].create({'name': 'COUNT-SERIAL', 'product_id': self.product.id, 'company_id': self.env.company.id})
        self._quant(quantity=1, lot=lot)
        inventory = self._inventory()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            inventory.line_ids.product_qty = 2

    def test_overlap_rejected_even_with_empty_location(self):
        inventory = self._inventory(start_empty=True)
        other = self._inventory(start=False)
        with self.assertRaises(ValidationError):
            other.action_start()
        self.assertEqual(other.state, 'draft')
        inventory.action_state_to_cancel()
        other.action_start()

    def test_disjoint_products_can_be_counted_in_parallel(self):
        self._quant()
        self._quant(product=self.other)
        first = self._inventory(product_selection='one', product_ids=[Command.set(self.product.ids)])
        second = self._inventory(product_selection='one', product_ids=[Command.set(self.other.ids)])
        self.assertEqual((first.state, second.state), ('in_progress', 'in_progress'))

    def test_scope_cannot_change_after_start(self):
        self._quant()
        inventory = self._inventory()
        with self.assertRaises(UserError):
            inventory.location_ids = [Command.set(self.bin_b.ids)]

    def test_only_assigned_worker_can_count_and_manager_applies(self):
        worker = new_test_user(self.env, login='inventory_worker', groups='stock.group_stock_user',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        stranger = new_test_user(self.env, login='inventory_stranger', groups='stock.group_stock_user',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        quant = self._quant()
        inventory = self._inventory(responsible_id=worker.id)
        with self.assertRaises(AccessError):
            inventory.line_ids.with_user(stranger).product_qty = 6
        inventory.line_ids.with_user(worker).product_qty = 6
        with self.assertRaises(AccessError):
            inventory.line_ids.with_user(worker).unlink()
        with self.assertRaises(AccessError):
            inventory.with_user(worker).action_state_to_done()
        inventory.action_state_to_done()
        self.assertEqual(quant.quantity, 6)

    def test_rpc_cannot_forge_status_snapshot_or_ledger(self):
        quant = self._quant()
        inventory = self._inventory()
        for record, vals in [(inventory, {'state': 'done'}), (inventory.line_ids, {'theoretical_qty': 100}),
                (inventory.line_ids, {'applied': True}), (quant, {'current_inventory_id': False})]:
            with self.assertRaises(AccessError):
                record.write(vals)
        with self.assertRaises(AccessError):
            self.env['stock.inventory'].create({'state': 'done'})

    def test_native_quant_apply_and_forged_context_cannot_bypass_plan(self):
        quant = self._quant()
        inventory = self._inventory()
        with self.assertRaises(UserError):
            quant.inventory_quantity = 4
        with self.assertRaises(UserError):
            quant.with_context(blue_stock_inventory_token=True, blue_stock_inventory_id=inventory.id).action_apply_inventory()

    def test_cancel_and_return_to_draft_release_without_stock_change(self):
        quant = self._quant()
        inventory = self._inventory()
        inventory.line_ids.product_qty = 5
        inventory.action_state_to_draft()
        self.assertFalse(quant.current_inventory_id)
        self.assertEqual(quant.quantity, 10)
        inventory.action_start()
        inventory.action_state_to_cancel()
        self.assertFalse(quant.current_inventory_id)
        self.assertEqual(quant.quantity, 10)

    def test_applied_history_cannot_be_changed_cancelled_or_deleted(self):
        self._quant()
        inventory = self._inventory()
        inventory.line_ids.product_qty = 7
        inventory.line_ids.action_apply()
        for action in [inventory.action_state_to_draft, inventory.action_state_to_cancel, inventory.line_ids.unlink, inventory.unlink]:
            with self.assertRaises(UserError):
                action()
        with self.assertRaises(UserError):
            inventory.line_ids.product_qty = 5
        with self.assertRaises(UserError):
            inventory.stock_move_ids.quantity = 1
        with self.assertRaises(UserError):
            inventory.stock_move_ids.unlink()

    def test_all_lines_apply_can_auto_complete(self):
        self.env.company.stock_inventory_auto_complete = True
        self._quant()
        inventory = self._inventory()
        inventory.line_ids.product_qty = 8
        inventory.line_ids.action_apply()
        self.assertEqual(inventory.state, 'done')

    def test_batch_error_rolls_back_all_stock_and_flags(self):
        first = self._quant()
        second = self._quant(product=self.other)
        inventory = self._inventory()
        inventory.line_ids.write({'product_qty': 7})
        self.env['stock.quant']._update_available_quantity(self.other, self.bin_a, 1)
        with self.assertRaises(UserError):
            inventory.action_state_to_done()
        self.assertEqual((first.quantity, second.quantity), (10, 11))
        self.assertFalse(inventory.line_ids.filtered('applied'))
        self.assertFalse(inventory.stock_move_ids)

    def test_cross_company_lines_are_rejected(self):
        other_company = self.env['res.company'].create({'name': 'Other count company'})
        location = self.env['stock.location'].create({'name': 'Other count bin', 'usage': 'internal', 'company_id': other_company.id})
        inventory = self._inventory(start_empty=True)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['stock.inventory.line'].create({'inventory_id': inventory.id, 'product_id': self.product.id,
                'location_id': location.id, 'product_qty': 2})

    def test_duplicate_dimensions_are_rejected(self):
        self._quant()
        inventory = self._inventory()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['stock.inventory.line'].create({'inventory_id': inventory.id, 'product_id': self.product.id,
                'location_id': self.bin_a.id, 'product_qty': 2})

    def test_context_defaults_cannot_forge_completion_or_history(self):
        inventory = self.env['stock.inventory'].with_context(default_state='done', default_completed_at='2026-10-20 00:00:00').create({
            'location_ids': [Command.set(self.root.ids)], 'start_empty': True})
        self.assertEqual(inventory.state, 'draft')
        self.assertFalse(inventory.completed_at)
        inventory.action_start()
        line = self.env['stock.inventory.line'].with_context(default_applied=True).create({
            'inventory_id': inventory.id, 'product_id': self.product.id, 'location_id': self.bin_a.id, 'product_qty': 2})
        self.assertFalse(line.applied)
        with self.assertRaises(AccessError):
            self.env['stock.quant'].with_context(default_current_inventory_id=inventory.id).create({
                'product_id': self.other.id, 'location_id': self.bin_a.id})

    def test_changed_unit_requires_new_inventory_line(self):
        inventory = self._inventory(start_empty=True)
        line = self.env['stock.inventory.line'].create({'inventory_id': inventory.id, 'product_id': self.product.id,
            'location_id': self.bin_a.id, 'product_qty': 2})
        original = line.product_uom_id
        self.product.uom_id = self.env.ref('uom.product_uom_kgm')
        self.assertEqual(line.product_uom_id, original)
        with self.assertRaises(UserError):
            inventory.action_state_to_done()

    def test_record_rules_hide_another_company_inventory(self):
        inventory = self._inventory(start=False)
        company = self.env['res.company'].create({'name': 'Other inventory access company'})
        user = new_test_user(self.env, login='other_inventory_reader', groups='stock.group_stock_user',
            company_id=company.id, company_ids=[Command.set(company.ids)])
        self.assertFalse(inventory.with_user(user).search([('id', '=', inventory.id)]))
        with self.assertRaises(AccessError):
            inventory.with_user(user).read(['name'])

    def test_owner_filter_does_not_count_other_stock(self):
        owner = self.env['res.partner'].create({'name': 'Selected count owner'})
        self._quant(quantity=5, owner=owner)
        untouched = self._quant(quantity=8)
        inventory = self._inventory(owner_id=owner.id)
        self.assertEqual(inventory.line_ids.partner_id, owner)
        inventory.line_ids.product_qty = 4
        inventory.action_state_to_done()
        self.assertEqual(untouched.quantity, 8)

    def test_unfinished_empty_scope_blocks_direct_native_adjustment(self):
        inventory = self._inventory(start_empty=True)
        quant = self._quant()
        quant.inventory_quantity = 6
        with self.assertRaises(UserError):
            quant.action_apply_inventory()
        self.assertEqual(quant.quantity, 10)
        inventory.action_state_to_cancel()

    def test_form_can_create_empty_plan_and_enter_count(self):
        with Form(self.env['stock.inventory']) as form:
            form.location_ids.add(self.root)
            form.start_empty = True
        inventory = form.record
        inventory.action_start()
        with Form(inventory) as form:
            with form.line_ids.new() as line:
                line.product_id = self.product
                line.location_id = self.bin_a
                line.product_qty = 3
        inventory.action_state_to_done()
        self.assertEqual(inventory.line_ids._book_quantity(), 3)

    def test_finishing_clears_unlisted_zero_quant_markers(self):
        self._quant()
        zero = self.env['stock.quant'].create({'product_id': self.other.id, 'location_id': self.bin_a.id, 'quantity': 0})
        inventory = self._inventory()
        self.assertEqual(zero.current_inventory_id, inventory)
        inventory.action_mark_counted()
        inventory.action_state_to_done()
        self.assertFalse(zero.current_inventory_id)
        self.assertFalse(zero.to_do)
