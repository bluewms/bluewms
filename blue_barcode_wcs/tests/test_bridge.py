from unittest.mock import patch
from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon


@tagged('post_install', '-at_install')
class TestBarcodeWcs(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    def _session(self):
        warehouse = self.env['stock.warehouse'].create({'name': 'Barcode WCS', 'code': 'BWCS'})
        warehouse.in_type_id.blue_wcs_enabled = True
        product = self.env['product.product'].create({'name': 'Bridge product', 'barcode': 'WCS_SCAN_PRODUCT', 'is_storable': True})
        picking = self.env['stock.picking'].create({'picking_type_id': warehouse.in_type_id.id,
            'location_id': warehouse.in_type_id.default_location_src_id.id, 'location_dest_id': warehouse.lot_stock_id.id})
        self.env['stock.move'].create({'picking_id': picking.id, 'product_id': product.id, 'product_uom_qty': 10,
            'uom_id': product.uom_id.id, 'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id})
        picking.action_confirm()
        client = 'wcs_scan_client_0001'
        view = self.env['blue.barcode.service'].open_session('picking', picking.id, client)
        session = self.env['blue.barcode.session'].browse(view['id'])
        session.action_event(client, 'wcs_scan_event_0001', 0, {'raw': product.barcode})
        return session, client, picking

    def test_wcs_uses_formal_entry_without_arbitrary_line_ids(self):
        session, client, picking = self._session()
        with patch.object(type(picking), 'action_create_wcs_request_from_button', autospec=True, return_value=True) as create:
            session.action_execute(client, session.revision, 'wcs')
        create.assert_called_once_with(picking)
        self.assertEqual(picking.move_line_ids.quantity, 1)
        self.assertEqual(picking.state, 'assigned')

    def test_wcs_failure_keeps_previously_saved_scan(self):
        session, client, picking = self._session()
        with self.assertRaises(UserError), self.cr.savepoint():
            with patch.object(type(picking), 'action_create_wcs_request_from_button', side_effect=UserError('device unavailable')):
                session.action_execute(client, session.revision, 'wcs')
        self.assertEqual(picking.move_line_ids.quantity, 1)
        self.assertEqual(len(session.event_ids), 1)

    def test_barcode_settings_follow_wcs_in_one_notebook(self):
        view = self.env['stock.picking.type'].get_view(
            view_id=self.env.ref('stock.view_picking_type_form').id, view_type='form')
        arch = etree.fromstring(view['arch'])
        pages = arch.xpath('//notebook/page')
        names = [page.get('name') for page in pages]
        self.assertEqual(len(arch.xpath('//sheet/notebook')), 1)
        self.assertEqual(names.count('blue_barcode'), 1)
        self.assertEqual(names.index('blue_barcode'), names.index('wcs_app') + 1)
