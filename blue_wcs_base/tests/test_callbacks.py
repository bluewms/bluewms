from odoo.tests import HttpCase, tagged
from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN


@tagged('post_install', '-at_install')
class TestWcsCallbacks(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env['wcs.equipment'].create({'name': 'Callback test', 'adapter_code': 'simulation',
            'company_id': cls.env.company.id, 'callback_token': 'test-callback-token'})
        warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        picking = cls.env['stock.picking'].create({'picking_type_id': warehouse.int_type_id.id,
            'location_id': warehouse.lot_stock_id.id, 'location_dest_id': cls.env.ref('stock.stock_location_customers').id})
        route = cls.env['wcs.route'].create({'name': 'Callback route', 'company_id': cls.env.company.id,
            'picking_type_id': warehouse.int_type_id.id, 'source_id': picking.location_id.id,
            'destination_id': picking.location_dest_id.id, 'source_point': 'A', 'destination_point': 'B', 'equipment_id': cls.device.id})
        plan = cls.env['wcs.plan'].with_context(blue_wcs_token=WCS_TOKEN).create({'name': 'Callback plan', 'picking_id': picking.id,
            'company_id': cls.env.company.id, 'unit_key': 'callback-test', 'revision': 1, 'route_id': route.id, 'snapshot': '{}'})
        cls.task = cls.env['wcs.request'].with_context(blue_wcs_token=WCS_TOKEN).create({'name': 'WCS-callback-test',
            'plan_id': plan.id, 'company_id': cls.env.company.id, 'equipment_id': cls.device.id, 'step': 1,
            'role': 'goods', 'source_point': 'A', 'destination_point': 'B', 'task_type': 'TRANSFER', 'state': 'accepted'})

    def _event(self, headers=None, **changes):
        data = {'task_id': self.task.name, 'event_id': 'end-1', 'event': 'end', 'actual_destination': 'B'}
        data.update(changes)
        return self.url_open('/blue_wcs/v1/devices/%s/events' % self.device.id, json=data,
                             headers=headers or {}, method='POST')

    def test_unauthenticated_callback_rejected(self):
        response = self._event()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.task.state, 'accepted')

    def test_authenticated_callback_and_duplicate(self):
        headers = {'Authorization': 'Bearer test-callback-token'}
        self.assertEqual(self._event(headers).status_code, 200)
        self.task.invalidate_recordset()
        self.assertEqual(self.task.state, 'completed')
        self.assertEqual(self._event(headers).status_code, 200)
        self.task.invalidate_recordset()
        self.assertEqual(len(self.task.event_ids), 1)

    def test_device_token_cannot_update_another_device_task(self):
        other = self.env['wcs.equipment'].create({'name': 'Other callback device', 'company_id': self.env.company.id, 'callback_token': 'other-token'})
        response = self.url_open('/blue_wcs/v1/devices/%s/events' % other.id,
            json={'task_id': self.task.name, 'event_id': 'end', 'event': 'end'},
            headers={'Authorization': 'Bearer other-token'}, method='POST')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.task.state, 'accepted')

    def test_mismatched_actual_destination_rejected(self):
        self.assertEqual(self._event({'Authorization': 'Bearer test-callback-token'}, actual_destination='WRONG').status_code, 400)
        self.task.invalidate_recordset()
        self.assertEqual(self.task.state, 'accepted')
