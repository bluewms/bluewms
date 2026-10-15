from unittest.mock import Mock, patch

from odoo.tests import TransactionCase
from odoo.addons.blue_wcs_base.models.transport import send


class TestWesTransport(TransactionCase):
    def _connection(self):
        return {'adapter_code': 'wes', 'endpoint': 'https://wes.invalid/into-order-hd/manual-order-vzf',
                'api_key': '', 'api_secret': '', 'wes_token_url': 'https://wes.invalid/api-auth/oauth/token',
                'wes_authorization': 'Basic test-only', 'wes_app_id': 'test', 'wes_app_secret': 'test-only'}

    def test_token_then_task_preserves_task_number(self):
        token = Mock(status_code=200, content=b'ok')
        token.json.return_value = {'access_token': 'test-token'}
        accepted = Mock(status_code=200, content=b'ok')
        accepted.json.return_value = {'code': 200}
        payload = {'carBillCode': 'WCS-stable-id'}
        with patch('odoo.addons.blue_wcs_wes.models.wes_transport.requests.post', side_effect=[token, accepted]) as post:
            self.assertEqual(send(self._connection(), payload)[0], 'accepted')
            self.assertEqual(post.call_args.kwargs['json']['carBillCode'], 'WCS-stable-id')
            self.assertEqual(post.call_args.kwargs['headers']['Blade-Auth'], 'test-token')
            self.assertFalse(post.call_args.kwargs['allow_redirects'])

    def test_token_failure_sends_no_task(self):
        response = Mock(status_code=403, content=b'no')
        with patch('odoo.addons.blue_wcs_wes.models.wes_transport.requests.post', return_value=response) as post:
            self.assertEqual(send(self._connection(), {})[0], 'failed')
            self.assertEqual(post.call_count, 1)

    def test_task_timeout_is_unknown(self):
        import requests
        token = Mock(status_code=200, content=b'ok')
        token.json.return_value = {'access_token': 'test-token'}
        with patch('odoo.addons.blue_wcs_wes.models.wes_transport.requests.post', side_effect=[token, requests.Timeout]):
            self.assertEqual(send(self._connection(), {'carBillCode': 'same'})[0], 'unknown')

    def test_missing_credentials_sends_nothing(self):
        connection = self._connection()
        connection['wes_app_secret'] = ''
        with patch('odoo.addons.blue_wcs_wes.models.wes_transport.requests.post') as post:
            self.assertEqual(send(connection, {})[0], 'failed')
            post.assert_not_called()

    def test_multi_item_completion_does_not_finish_after_first_item(self):
        from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        destination = self.env.ref('stock.stock_location_customers')
        device = self.env['wcs.equipment'].create({'name': 'WES multi-item simulation', 'adapter_code': 'wes',
            'wes_warehouse_code': 'TEST', 'wes_room_code': 'ROOM', 'wes_owner_code': 'OWNER', 'company_id': self.env.company.id})
        picking = self.env['stock.picking'].create({'picking_type_id': warehouse.int_type_id.id,
            'location_id': warehouse.lot_stock_id.id, 'location_dest_id': destination.id})
        route = self.env['wcs.route'].create({'name': 'WES test route', 'picking_type_id': warehouse.int_type_id.id,
            'source_id': picking.location_id.id, 'destination_id': destination.id, 'source_point': 'A',
            'destination_point': 'B', 'equipment_id': device.id, 'company_id': self.env.company.id})
        plan = self.env['wcs.plan'].with_context(blue_wcs_token=WCS_TOKEN).create({'name': 'WES multi item',
            'company_id': self.env.company.id, 'picking_id': picking.id, 'unit_key': 'wes-multi', 'revision': 1,
            'route_id': route.id, 'snapshot': '{}'})
        products = self.env['product.product'].create([{'name': 'WES item 1', 'default_code': 'WES1', 'is_storable': True},
                                                       {'name': 'WES item 2', 'default_code': 'WES2', 'is_storable': True}])
        package = self.env['stock.package'].create({'name': 'WES test carrier'})
        rows = self.env['wcs.plan.line']
        for product in products:
            move = self.env['stock.move'].create({'picking_id': picking.id, 'product_id': product.id, 'uom_id': product.uom_id.id,
                'product_uom_qty': 10, 'location_id': picking.location_id.id, 'location_dest_id': destination.id})
            line = self.env['stock.move.line'].create({'move_id': move.id, 'picking_id': picking.id, 'product_id': product.id,
                'uom_id': product.uom_id.id, 'quantity': 10, 'location_id': picking.location_id.id, 'location_dest_id': destination.id})
            rows |= self.env['wcs.plan.line'].with_context(blue_wcs_token=WCS_TOKEN).create({'plan_id': plan.id,
                'move_line_id': line.id, 'product_id': product.id, 'uom_id': product.uom_id.id, 'quantity': 10, 'package_id': package.id})
        task = self.env['wcs.request'].with_context(blue_wcs_token=WCS_TOKEN).create({'plan_id': plan.id, 'company_id': self.env.company.id,
            'equipment_id': device.id, 'step': 1, 'role': 'goods', 'source_point': 'A', 'destination_point': 'B',
            'task_type': 'TEST', 'state': 'accepted'})
        self.assertEqual(len(task._payload()['planItemVOList']), 2)
        task._receive_wes_item_completion('item-1', str(rows[0].id), 'B')
        self.assertEqual(task.state, 'accepted')
        task._receive_wes_item_completion('item-1', str(rows[0].id), 'B')
        self.assertEqual(len(task.event_ids), 1)
        task._receive_wes_item_completion('item-2', str(rows[1].id), 'B')
        self.assertEqual(task.state, 'completed')
