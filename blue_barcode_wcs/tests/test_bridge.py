from unittest.mock import patch
from lxml import etree

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN


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

    def test_wcs_primary_button_and_required_validation_guard(self):
        session, client, picking = self._session()
        picking.picking_type_id.is_wcs_required_for_validate = True
        status = session._view()['operation']
        self.assertEqual(status['primary'], 'wcs')
        self.assertTrue(status['wcs'])
        self.assertFalse(status['validate'])
        with self.assertRaises(UserError):
            session.action_execute(client, session.revision, 'validate')

    def test_wcs_rejects_zero_confirmed_quantity(self):
        session, client, picking = self._session()
        session.action_event(client, 'wcs_scan_zero_total', session.revision,
            {'row_key': session._rows()[0]['key'], 'total': 0})
        with patch.object(type(picking), 'action_create_wcs_request_from_button') as create:
            with self.assertRaises(UserError):
                session.action_execute(client, session.revision, 'wcs')
        create.assert_not_called()

    def test_batch_wcs_only_calls_members_with_confirmed_quantity(self):
        session, client, picking = self._session()
        other = picking.copy()
        other.action_confirm()
        # Incoming reservations are not confirmed barcode work.
        other.move_line_ids.write({'picked': False})
        session.action_release(client)
        batch = self.env['stock.picking.batch'].create({'picking_type_id': picking.picking_type_id.id,
            'picking_ids': [Command.set((picking | other).ids)]})
        view = self.env['blue.barcode.service'].open_session('batch', batch.id, client)
        current = self.env['blue.barcode.session'].browse(view['id'])
        with patch.object(type(picking), 'action_create_wcs_request_from_button', autospec=True, return_value=True) as create:
            current.action_execute(client, current.revision, 'wcs')
        create.assert_called_once_with(picking)

    def test_completed_wcs_member_can_validate_without_unscanned_members(self):
        session, client, picking = self._session()
        picking.picking_type_id.is_wcs_required_for_validate = True
        other = picking.copy()
        other.action_confirm()
        other.move_line_ids.write({'picked': False})
        device = self.env['wcs.equipment'].create({'name': 'Terminal status simulation',
            'adapter_code': 'simulation', 'company_id': self.env.company.id})
        plan = self.env['wcs.plan'].with_context(blue_wcs_token=WCS_TOKEN).create({
            'name': 'Terminal status plan', 'company_id': self.env.company.id, 'picking_id': picking.id,
            'unit_key': 'terminal-status', 'revision': 1, 'snapshot': '{}'})
        line = picking.move_line_ids
        self.env['wcs.plan.line'].with_context(blue_wcs_token=WCS_TOKEN).create({
            'plan_id': plan.id, 'move_line_id': line.id, 'product_id': line.product_id.id,
            'uom_id': line.uom_id.id, 'quantity': 1})
        self.env['wcs.request'].with_context(blue_wcs_token=WCS_TOKEN).create({
            'plan_id': plan.id, 'company_id': self.env.company.id, 'equipment_id': device.id,
            'step': 1, 'role': 'goods', 'source_point': 'A', 'destination_point': 'B',
            'task_type': 'TRANSFER', 'state': 'completed'})
        session.action_release(client)
        batch = self.env['stock.picking.batch'].create({'picking_type_id': picking.picking_type_id.id,
            'picking_ids': [Command.set((picking | other).ids)]})
        view = self.env['blue.barcode.service'].open_session('batch', batch.id, client)
        self.assertEqual(view['operation']['primary'], 'validate')
        self.assertTrue(view['operation']['validate'])

    def test_barcode_settings_follow_wcs_in_one_notebook(self):
        view = self.env['stock.picking.type'].get_view(
            view_id=self.env.ref('stock.view_picking_type_form').id, view_type='form')
        arch = etree.fromstring(view['arch'])
        pages = arch.xpath('//notebook/page')
        names = [page.get('name') for page in pages]
        self.assertEqual(len(arch.xpath('//sheet/notebook')), 1)
        self.assertEqual(names.count('blue_barcode'), 1)
        self.assertEqual(names.index('blue_barcode'), names.index('wcs_app') + 1)
