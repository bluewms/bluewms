from odoo.tests import TransactionCase


class TestBlueMenus(TransactionCase):
    def test_business_menus_are_owned_by_the_web_module(self):
        for external_id in ('menu_product_root', 'menu_package_root', 'menu_location_root'):
            menu = self.env.ref(f'blue_web_theme.{external_id}')
            self.assertFalse(menu.parent_id)
        self.assertEqual(self.env.ref('stock.menu_package').parent_id, self.env.ref('blue_web_theme.menu_package_root'))
        self.assertEqual(self.env.ref('stock.menu_action_location_form').parent_id, self.env.ref('blue_web_theme.menu_location_root'))
        self.assertFalse(self.env.ref('stock.menu_stock_inventory_control').active)
        self.assertEqual(self.env.ref('blue_web_theme.stock_location_coordinate_menu').action,
                         self.env.ref('blue_stock_base.stock_location_coordinate_action'))

    def test_web_uninstall_hook_restores_standard_menus(self):
        from odoo.addons.blue_web_theme.hooks import _uninstall_restore_menus
        _uninstall_restore_menus(self.env)
        self.assertEqual(self.env.ref('stock.menu_package').parent_id, self.env.ref('stock.menu_stock_inventory_control'))
        self.assertEqual(self.env.ref('stock.menu_action_production_lot_form').parent_id, self.env.ref('stock.menu_stock_inventory_control'))
        self.assertTrue(self.env.ref('stock.menu_stock_inventory_control').active)
