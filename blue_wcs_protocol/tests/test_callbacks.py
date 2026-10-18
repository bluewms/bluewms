from odoo.tests import HttpCase, tagged

from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN

from .common import make_category, make_task


@tagged('post_install', '-at_install')
class TestProtocolCallbacks(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Callback protocol warehouse', 'code': 'PCLB'})
        cls.root = cls.warehouse.lot_stock_id
        cls.destination = cls.env['stock.location'].create({'name': 'Callback protocol bin',
            'location_id': cls.root.id, 'company_id': cls.env.company.id, 'agv_map_point': 'B'})
        cls.product = cls.env['product.product'].create({'name': 'Callback protocol goods', 'is_storable': True})
        cls.category = make_category(cls.env, cls.root)
        cls.task, cls.line, cls.package = make_task(cls.env, cls.category, cls.warehouse, cls.destination, cls.product)
        cls.task.with_context(blue_wcs_token=WCS_TOKEN).state = 'accepted'

    def test_legacy_tusk_callback_needs_no_new_header_and_is_idempotent(self):
        body = {'taskId': self.task.name, 'deviceId': 'ROBOT-1', 'targetPoint': 'B-03'}
        for unused in range(2):
            response = self.url_open('/api/blue_wcs_tusk/feedbackTask', json=body, method='POST')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'code': 200, 'msg': 'success'})
        self.task.invalidate_recordset()
        self.package.invalidate_recordset()
        self.assertEqual(self.task.state, 'completed')
        self.assertEqual(self.package.package_removal_priority, 'B-03')
        self.assertEqual(len(self.task.event_ids), 1)

    def test_wrong_category_and_unknown_task_cannot_change_task(self):
        response = self.url_open('/blue_wcs/v1/categories/2147483647/callback',
            json={'taskId': self.task.name, 'targetPoint': 'B-03'}, method='POST')
        self.assertNotEqual(response.status_code, 200)
        response = self.url_open('/api/blue_wcs_tusk/feedbackTask',
            json={'taskId': 'not-a-task', 'targetPoint': 'B-03'}, method='POST')
        self.assertEqual(response.status_code, 404)
        self.task.invalidate_recordset()
        self.assertEqual(self.task.state, 'accepted')

    def test_invalid_callback_goes_to_reconciliation_without_writes(self):
        response = self.url_open('/api/blue_wcs_tusk/feedbackTask', json={'taskId': self.task.name}, method='POST')
        self.assertEqual(response.status_code, 409)
        self.task.invalidate_recordset()
        self.package.invalidate_recordset()
        self.assertEqual(self.task.state, 'unknown')
        self.assertFalse(self.package.package_removal_priority)
        self.assertFalse(self.task.event_ids)

    def test_bearer_mode_keeps_authentication_for_configured_categories(self):
        category = make_category(self.env, self.root, protocol_callback_mode='bearer', callback_token='protocol-callback-secret')
        task, line, package = make_task(self.env, category, self.warehouse, self.destination, self.product)
        task.with_context(blue_wcs_token=WCS_TOKEN).state = 'accepted'
        path = '/blue_wcs/v1/categories/%s/callback' % category.id
        body = {'taskId': task.name, 'targetPoint': 'B-03'}
        self.assertEqual(self.url_open(path, json=body, method='POST').status_code, 401)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'accepted')
        self.assertEqual(self.url_open(path, json=body, method='POST',
            headers={'Authorization': 'Bearer protocol-callback-secret'}).status_code, 200)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'completed')
