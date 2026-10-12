from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user


class TestStockRules(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['product.category'].create({'name': 'Blue rules category'})
        cls.product = cls.env['product.product'].create({'name': 'Blue protected stock', 'is_storable': True, 'categ_id': cls.category.id})
        cls.parent = cls.env['stock.location'].create({'name': 'Blue rules area', 'usage': 'view', 'location_rank': 'area', 'company_id': cls.env.company.id})
        cls.locations = cls.env['stock.location'].create([
            {'name': name, 'usage': 'internal', 'location_id': cls.parent.id, 'company_id': cls.env.company.id}
            for name in ('Blue rules A', 'Blue rules B')
        ])
        cls.transit = cls.env['stock.location'].create({'name': 'Blue rules transit', 'usage': 'transit', 'company_id': cls.env.company.id})
        cls.supplier = cls.env.ref('stock.stock_location_suppliers')
        cls.customer = cls.env.ref('stock.stock_location_customers')
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)

    def _update(self, quantity, location=None, **values):
        return self.env['stock.quant']._update_available_quantity(self.product, location or self.locations[0], quantity, **values)

    def test_negative_internal_stock_is_rejected_and_rolled_back(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._update(-1)
        self.assertFalse(self.env['stock.quant'].search([('product_id', '=', self.product.id)]))

    def test_negative_transit_stock_is_rejected(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._update(-1, self.transit)

    def test_external_locations_keep_native_negative_balance(self):
        self._update(-3, self.supplier)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.supplier, allow_negative=True), -3)

    def test_product_exception_is_explicit(self):
        self.product.allow_negative_stock = True
        self._update(-2)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.locations[0], allow_negative=True), -2)

    def test_category_exception_does_not_leak_to_subcategories(self):
        self.category.allow_negative_stock = True
        self._update(-1)
        child = self.env['product.category'].create({'name': 'Blue rules child', 'parent_id': self.category.id})
        other = self.env['product.product'].create({'name': 'Blue rules child product', 'is_storable': True, 'categ_id': child.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['stock.quant']._update_available_quantity(other, self.locations[0], -1)

    def test_location_exception_is_not_a_warehouse_wide_exception(self):
        self.locations[0].allow_negative_stock = True
        self._update(-1)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._update(-1, self.locations[1])

    def test_context_cannot_disable_negative_stock_check(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['stock.quant'].with_context(skip_negative_qty_check=True, test_stock_no_negative=False)._update_available_quantity(self.product, self.locations[0], -1)

    def test_available_stock_can_be_consumed_to_zero(self):
        self._update(3)
        self._update(-3)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.locations[0]), 0)

    def test_positive_stock_in_another_lot_cannot_cover_a_negative_lot(self):
        self.product.tracking = 'lot'
        lots = self.env['stock.lot'].create([
            {'name': name, 'product_id': self.product.id, 'company_id': self.env.company.id}
            for name in ('Blue rules lot A', 'Blue rules lot B')
        ])
        self._update(5, lot_id=lots[0])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._update(-1, lot_id=lots[1])

    def test_incoming_block_can_be_enabled_on_an_occupied_location(self):
        self._update(3)
        self.locations[0].block_stock_entrance = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._update(1)
        self._update(-1)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.locations[0]), 2)

    def test_frozen_location_blocks_both_stock_directions(self):
        self._update(3)
        self.locations[0].is_locking = True
        for quantity in (1, -1):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self._update(quantity)

    def test_parent_policy_applies_to_children_and_putaway(self):
        self.parent.block_stock_entrance = True
        self.assertEqual(self.parent.child_none_count, 0)
        self.assertEqual(self.locations[0].child_none_count, 0)
        self.assertFalse(self.locations[0]._check_can_be_used(self.product, quantity=1))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._update(1)
        self.parent.block_stock_entrance = False
        self.parent.is_locking = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._update(1)

    def test_frozen_jobs_can_release_reservations_but_not_create_them(self):
        self._update(3)
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], reserved_quantity=2)
        self.locations[0].is_locking = True
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], reserved_quantity=-2)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], reserved_quantity=1)
        quant = self.env['stock.quant'].search([('product_id','=',self.product.id)])
        self.assertEqual(quant.reserved_quantity, 0)

    def test_direct_quantity_edits_obey_location_policies(self):
        self._update(3)
        quant = self.env['stock.quant'].search([('product_id','=',self.product.id)])
        self.locations[0].block_stock_entrance = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            quant.write({'quantity': 4})
        self.locations[0].is_locking = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            quant.write({'quantity': 2})

    def test_moving_a_quant_to_a_protected_location_is_rejected(self):
        self._update(1)
        quant = self.env['stock.quant'].search([('product_id','=',self.product.id)])
        self.locations[1].block_stock_entrance = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            quant.write({'location_id': self.locations[1].id})
        self.assertEqual(quant.location_id, self.locations[0])

    def test_non_inventory_manager_cannot_grant_policy_exceptions(self):
        user = new_test_user(self.env, login='blue_rules_product_manager', groups='product.group_product_manager')
        for record in (self.product.product_tmpl_id, self.category):
            with self.assertRaises(AccessError), self.cr.savepoint():
                record.with_user(user).write({'allow_negative_stock': True})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['product.template'].with_user(user).create({'name':'Unauthorized exception','allow_negative_stock':True})

    def _picking(self, quantity, operation, source, destination):
        picking = self.env['stock.picking'].create({'picking_type_id': operation.id, 'location_id': source.id, 'location_dest_id': destination.id})
        move = self.env['stock.move'].create({'product_id': self.product.id, 'uom_id': self.product.uom_id.id,
            'product_uom_qty': quantity, 'picking_id': picking.id, 'location_id': source.id, 'location_dest_id': destination.id})
        picking.action_confirm()
        picking.action_assign()
        if move.move_line_ids:
            move.move_line_ids.write({'quantity': quantity, 'picked': True})
        else:
            self.env['stock.move.line'].create({'move_id':move.id,'picking_id':picking.id,'product_id':self.product.id,
                'uom_id':self.product.uom_id.id,'quantity':quantity,'picked':True,'location_id':source.id,'location_dest_id':destination.id})
        return picking

    def test_over_delivery_fails_without_committing_a_stock_change(self):
        self._update(2)
        picking = self._picking(3, self.warehouse.out_type_id, self.locations[0], self.customer)
        quants = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.locations[0].id)])
        before = [(quant.id, quant.quantity, quant.reserved_quantity) for quant in quants]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            picking.button_validate()
        self.assertNotEqual(picking.state, 'done')
        self.assertEqual([(quant.id, quant.quantity, quant.reserved_quantity) for quant in quants], before)
        self.assertEqual(sum(quants.mapped('quantity')), 2)
        self.assertFalse(self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.customer.id)]))

    def test_normal_receipt_transfer_and_delivery_work_with_rules_enabled(self):
        flows=[(5,self.warehouse.in_type_id,self.supplier,self.locations[0]),
               (2,self.warehouse.int_type_id,self.locations[0],self.locations[1]),
               (3,self.warehouse.out_type_id,self.locations[0],self.customer)]
        for quantity,operation,source,destination in flows:
            picking=self._picking(quantity,operation,source,destination)
            picking.button_validate()
            self.assertEqual(picking.state,'done')
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product,self.locations[0]),0)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product,self.locations[1]),2)

    def test_cancel_releases_a_frozen_pickings_reservation(self):
        self._update(3)
        picking = self._picking(2, self.warehouse.out_type_id, self.locations[0], self.customer)
        self.locations[0].is_locking = True
        picking.action_cancel()
        quants = self.env['stock.quant'].search([('product_id', '=', self.product.id)])
        self.assertEqual(picking.state, 'cancel')
        self.assertEqual(sum(quants.mapped('reserved_quantity')), 0)
        self.assertEqual(sum(quants.mapped('quantity')), 3)

    def test_frozen_stock_cannot_be_removed_by_unlink(self):
        self._update(3)
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id)])
        self.locations[0].is_locking = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            quant.unlink()
        self.assertTrue(quant.exists())
        self.assertEqual(quant.quantity, 3)

    def test_noop_quant_updates_are_allowed_while_frozen(self):
        self._update(3)
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id)])
        self.locations[0].is_locking = True
        quant.write({'quantity': 3, 'location_id': self.locations[0].id, 'product_id': self.product.id})
        self.assertEqual(quant.quantity, 3)

    def test_negative_check_uses_odoo_unit_precision(self):
        digits = self.env['decimal.precision'].precision_get('Product Unit')
        self._update(-10 ** (-digits - 3))
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id)])
        self.assertEqual(quant.uom_id.compare(quant.quantity, 0), 0)

    def test_receipt_block_allows_a_normal_outbound_picking(self):
        self._update(3)
        self.locations[0].block_stock_entrance = True
        picking = self._picking(2, self.warehouse.out_type_id, self.locations[0], self.customer)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', '=', self.locations[0].id)])
        self.assertEqual(quant.quantity, 1)

    def test_receipt_into_a_blocked_location_is_rolled_back(self):
        self.locations[0].block_stock_entrance = True
        picking = self._picking(2, self.warehouse.in_type_id, self.supplier, self.locations[0])
        before = self.env['stock.quant'].search([('product_id', '=', self.product.id)]).ids
        with self.assertRaises(ValidationError), self.cr.savepoint():
            picking.button_validate()
        self.assertNotEqual(picking.state, 'done')
        self.assertEqual(self.env['stock.quant'].search([('product_id', '=', self.product.id)]).ids, before)

    def test_relabelling_legacy_negative_stock_obeys_the_current_policy(self):
        self.product.allow_negative_stock = True
        self._update(-1)
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id)])
        self.product.allow_negative_stock = False
        owner = self.env['res.partner'].create({'name': 'Blue negative-policy owner'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            quant.write({'owner_id': owner.id})
        self.assertFalse(quant.owner_id)

    def test_receipt_block_allows_repacking_but_full_freeze_blocks_it(self):
        package = self.env['stock.package'].create({})
        self._update(3, package_id=package)
        self.locations[0].block_stock_entrance = True
        package.unpack()
        quant = self.env['stock.quant'].search([('product_id', '=', self.product.id)])
        self.assertFalse(quant.package_id)
        self.assertEqual(quant.quantity, 3)
        other = self.env['stock.package'].create({})
        quant.package_id = other
        self.locations[0].is_locking = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            other.unpack()
        self.assertEqual(quant.package_id, other)
        self.assertEqual(quant.quantity, 3)

    def test_rpc_context_cannot_forge_a_same_location_move(self):
        self.locations[0].block_stock_entrance = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['stock.quant'].with_context(blue_stock_same_location_token=True, blue_stock_move_line_id=999999)._update_available_quantity(self.product, self.locations[0], 1)
