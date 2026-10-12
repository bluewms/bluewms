from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user


class TestStockBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.area = cls.env['stock.location'].create({
            'name': 'Blue test area', 'usage': 'view', 'location_rank': 'area', 'company_id': cls.company.id,
        })
        cls.locations = cls.env['stock.location'].create([
            {'name': name, 'usage': 'internal', 'location_id': cls.area.id, 'company_id': cls.company.id}
            for name in ('Blue A', 'Blue B')
        ])
        cls.product = cls.env['product.product'].create({'name': 'Blue tracked product', 'is_storable': True, 'tracking': 'lot'})
        cls.lots = cls.env['stock.lot'].create([
            {'name': name, 'product_id': cls.product.id, 'company_id': cls.company.id}
            for name in ('BLUE-LOT-A', 'BLUE-LOT-B')
        ])
        cls.package_type = cls.env['stock.package.type'].create({'name': 'Blue crate'})
        cls.category = cls.env['stock.storage.category'].create({'name': 'Blue capacity', 'company_id': cls.company.id})
        cls.capacity = cls.env['stock.storage.category.capacity'].create({
            'storage_category_id': cls.category.id, 'package_type_id': cls.package_type.id, 'quantity': 2,
        })

    def test_same_product_lots_are_summed_and_zero_quants_are_ignored(self):
        location = self.locations[0]
        Quant = self.env['stock.quant']
        Quant._update_available_quantity(self.product, location, 3, lot_id=self.lots[0])
        Quant._update_available_quantity(self.product, location, 4, lot_id=self.lots[1])
        self.assertEqual(location.single_product_qty, 7)
        self.assertEqual(location.single_uom_id, self.product.uom_id)
        self.assertFalse(location.is_mixed_product)
        Quant._update_available_quantity(self.product, location, -3, lot_id=self.lots[0])
        Quant._update_available_quantity(self.product, location, -4, lot_id=self.lots[1])
        self.assertEqual(location.state, 'none')
        self.assertEqual(location.color, 0)
        self.assertFalse(location.single_product_id)

    def test_mixed_products_do_not_show_a_false_single_product_quantity(self):
        product_b = self.env['product.product'].create({'name': 'Blue product B', 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], 3, lot_id=self.lots[0])
        self.env['stock.quant']._update_available_quantity(product_b, self.locations[0], 5)
        self.assertTrue(self.locations[0].is_mixed_product)
        self.assertFalse(self.locations[0].single_product_id)
        self.assertEqual(self.locations[0].single_product_qty, 0)

    def test_locked_and_archived_locations_are_not_available(self):
        self.assertEqual(self.area.child_none_count, 2)
        self.locations[0].is_locking = True
        self.assertEqual(self.area.child_none_count, 1)
        self.locations[1].active = False
        self.assertEqual(self.area.child_none_count, 0)
        self.locations[1].active = True
        self.area.is_locking = True
        self.assertEqual(self.area.child_none_count, 0)

    def test_capacity_recomputes_when_package_types_change(self):
        self.assertEqual(self.category.capacity_qty, 2)
        other_type = self.env['stock.package.type'].create({'name': 'Blue second crate'})
        other = self.env['stock.storage.category.capacity'].create({
            'storage_category_id': self.category.id, 'package_type_id': other_type.id, 'quantity': 5,
        })
        self.assertEqual(self.category.capacity_qty, 0)
        other.unlink()
        self.assertEqual(self.category.capacity_qty, 2)
        self.capacity.unlink()
        self.assertEqual(self.category.capacity_qty, 0)

    def test_capacity_sync_preserves_existing_numbers_and_ids(self):
        location = self.locations[0]
        location.storage_category_id = self.category
        location.action_sync_coordinates()
        original = {coordinate.name: coordinate.id for coordinate in location.coordinate_ids}
        self.capacity.quantity = 3
        location.action_sync_coordinates()
        current = {coordinate.name: coordinate.id for coordinate in location.coordinate_ids}
        self.assertEqual([current['1'], current['2']], [original['1'], original['2']])
        self.assertEqual(len(current), 3)
        location.action_sync_coordinates()
        self.assertEqual(len(location.coordinate_ids), 3)

    def test_occupied_capacity_position_cannot_be_removed_or_renumbered(self):
        location = self.locations[0]
        location.storage_category_id = self.category
        location.action_sync_coordinates()
        coordinate = location.coordinate_ids.filtered(lambda item: item.name == '2')
        package = self.env['stock.package'].create({'package_removal_priority': '2'})
        self.env['stock.quant']._update_available_quantity(self.product, location, 1, lot_id=self.lots[0], package_id=package)
        with self.assertRaises(UserError):
            coordinate.write({'name': 'new-number'})
        self.capacity.quantity = 1
        with self.assertRaises(UserError):
            location.action_sync_coordinates()
        self.assertTrue(coordinate.exists())

    def test_capacity_editing_is_limited_by_role_and_company(self):
        company_b = self.env['res.company'].create({'name': 'Blue second company'})
        location_b = self.env['stock.location'].create({'name': 'Blue private B', 'usage': 'internal', 'company_id': company_b.id})
        coordinate_a, coordinate_b = self.env['stock.location.coordinate'].create([
            {'name': 'A', 'location_id': self.locations[0].id}, {'name': 'B', 'location_id': location_b.id},
        ])
        user = new_test_user(self.env, login='blue_stock_user', groups='stock.group_stock_user',
                             company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        manager = new_test_user(self.env, login='blue_stock_manager', groups='stock.group_stock_manager',
                                company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        self.assertEqual(coordinate_a.with_user(user).name, 'A')
        with self.assertRaises(AccessError):
            coordinate_a.with_user(user).write({'name': 'changed'})
        with self.assertRaises(AccessError):
            self.locations[0].with_user(user).action_sync_coordinates()
        with self.assertRaises(AccessError):
            _ = coordinate_b.with_user(manager).name
        with self.assertRaises(AccessError):
            self.env['stock.location.coordinate'].with_user(manager).create({'name': 'B2', 'location_id': location_b.id})

    def test_copy_package_creates_empty_packages_with_new_references(self):
        package = self.env['stock.package'].create({'package_type_id': self.package_type.id, 'package_removal_priority': '2'})
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], 3, lot_id=self.lots[0], package_id=package)
        wizard = self.env['copy.package.wizard'].create({'pack': package.id, 'qty': 3})
        action = wizard.action_copy()
        copies = self.env['stock.package'].search(action['domain'])
        self.assertEqual(len(copies), 3)
        self.assertEqual(len(set(copies.mapped('name'))), 3)
        self.assertNotIn(package.name, copies.mapped('name'))
        self.assertFalse(copies.contained_quant_ids)
        self.assertFalse(any(copies.mapped('location_id')))
        self.assertFalse(any(copies.mapped('package_removal_priority')))
        self.assertEqual(wizard.qty, 3)
        self.assertEqual(package.quant_ids.quantity, 3)

    def test_copy_count_is_validated(self):
        package = self.env['stock.package'].create({})
        for quantity in (0, -1, 2001):
            wizard = self.env['copy.package.wizard'].create({'pack': package.id, 'qty': quantity})
            with self.assertRaises(UserError):
                wizard.action_copy()

    def test_emptying_package_resets_position_but_keeps_native_owner_computation(self):
        owner = self.env['res.partner'].create({'name': 'Blue owner'})
        package = self.env['stock.package'].create({'package_removal_priority': '2'})
        quant, _ = self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], 2,
            lot_id=self.lots[0], package_id=package, owner_id=owner)
        self.assertEqual(package.owner_id, owner)
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], -2,
            lot_id=self.lots[0], package_id=package, owner_id=owner)
        self.assertFalse(package.package_removal_priority)

    def test_internal_reservation_preserves_package_and_default_packaging(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        operation = warehouse.int_type_id
        operation.default_package_type = self.package_type
        picking = self.env['stock.picking'].create({'picking_type_id': operation.id,
            'location_id': self.locations[0].id, 'location_dest_id': self.locations[1].id})
        package = self.env['stock.package'].create({})
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], 4, lot_id=self.lots[0], package_id=package)
        move = self.env['stock.move'].create({'product_id': self.product.id,
            'product_uom_qty': 2, 'uom_id': self.product.uom_id.id, 'picking_id': picking.id,
            'location_id': self.locations[0].id, 'location_dest_id': self.locations[1].id})
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(move.move_line_ids.package_id, package)
        self.assertEqual(move.move_line_ids.result_package_id, package)
        packed = move.move_line_ids._put_in_pack(package_name='Blue new crate')
        self.assertEqual(packed.package_type_id, self.package_type)
        self.assertEqual(move.move_line_ids.quantity, 2)

    def test_receipt_delivery_and_internal_transfer_keep_quantities(self):
        product = self.env['product.product'].create({'name': 'Blue flow product', 'is_storable': True})
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        supplier = self.env.ref('stock.stock_location_suppliers')
        customer = self.env.ref('stock.stock_location_customers')
        flows = [(warehouse.in_type_id, supplier, self.locations[0], 5),
                 (warehouse.int_type_id, self.locations[0], self.locations[1], 2),
                 (warehouse.out_type_id, self.locations[0], customer, 3)]
        for operation, source, destination, quantity in flows:
            picking = self.env['stock.picking'].create({'picking_type_id': operation.id,
                'location_id': source.id, 'location_dest_id': destination.id})
            move = self.env['stock.move'].create({'product_id': product.id,
                'product_uom_qty': quantity, 'uom_id': product.uom_id.id, 'picking_id': picking.id,
                'location_id': source.id, 'location_dest_id': destination.id})
            picking.action_confirm()
            picking.action_assign()
            if move.move_line_ids:
                move.move_line_ids.write({'quantity': quantity, 'picked': True})
            else:
                self.env['stock.move.line'].create({'move_id': move.id, 'picking_id': picking.id,
                    'product_id': product.id, 'uom_id': product.uom_id.id, 'quantity': quantity,
                    'location_id': source.id, 'location_dest_id': destination.id, 'picked': True})
            picking.button_validate()
            self.assertEqual(picking.state, 'done')
        self.assertEqual(self.env['stock.quant']._get_available_quantity(product, self.locations[0]), 0)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(product, self.locations[1]), 2)

    def test_mixed_operation_defaults_require_an_explicit_package_type(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        operation_a = warehouse.int_type_id
        operation_a.default_package_type = self.package_type
        operation_b = operation_a.copy({'name': 'Blue different operation', 'default_package_type': False})
        lines = self.env['stock.move.line']
        for operation in (operation_a, operation_b):
            picking = self.env['stock.picking'].create({'picking_type_id': operation.id,
                'location_id': self.locations[0].id, 'location_dest_id': self.locations[1].id})
            lines |= self.env['stock.move.line'].create({'picking_id': picking.id,
                'product_id': self.product.id, 'uom_id': self.product.uom_id.id,
                'location_id': self.locations[0].id, 'location_dest_id': self.locations[1].id,
                'quantity': 1, 'lot_id': self.lots[0].id})
        with self.assertRaises(UserError):
            lines._put_in_pack()

    def test_summary_includes_negative_adjustments_in_the_product_total(self):
        if 'allow_negative_stock' in self.product._fields:
            self.product.allow_negative_stock = True
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], 5, lot_id=self.lots[0])
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], -2, lot_id=self.lots[1])
        self.assertEqual(self.locations[0].single_product_qty, 3)
        self.assertEqual(self.locations[0].single_product_id, self.product)
        self.assertEqual(self.locations[0].state, 'full')
