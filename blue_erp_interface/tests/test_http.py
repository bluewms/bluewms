from odoo.tests import HttpCase, new_test_user, tagged

from .common import make_interface, message


@tagged('post_install', '-at_install')
class TestErpHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'ERP HTTP warehouse', 'code': 'ERPH'})
        cls.product = cls.env['product.product'].create({'name': 'HTTP ERP goods', 'default_code': 'ERP-PRODUCT', 'is_storable': True})
        cls.service_user = new_test_user(cls.env, login='erp_http_service', groups='stock.group_stock_manager,base.group_system',
            company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)])
        cls.interface = make_interface(cls.env(user=cls.service_user.id), cls.warehouse, cls.product)

    def _post(self, payload, token='erp-test-inbound'):
        return self.url_open('/blue_erp/v1/interfaces/%s/documents' % self.interface.id,
            method='POST', json=payload, headers={'Authorization': 'Bearer ' + token})

    def test_authentication_precedes_business_writes(self):
        response = self._post(message(self.product), token='wrong')
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.interface.document_ids)

    def test_http_receive_and_duplicate_return_same_documents(self):
        first = self._post(message(self.product))
        second = self._post(message(self.product))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.interface.invalidate_recordset()
        self.assertEqual(len(self.interface.document_ids), 1)

    def test_bad_later_row_rolls_back_entire_batch(self):
        payload = message(self.product)
        payload['lines'].append({**payload['lines'][0], 'id': '20', 'product': 'UNKNOWN'})
        response = self._post(payload)
        self.assertEqual(response.status_code, 409)
        self.interface.invalidate_recordset()
        self.assertFalse(self.interface.document_ids)

    def test_disabled_service_identity_is_rejected(self):
        self.interface.connection_id.service_user_id.with_env(self.env).active = False
        self.assertEqual(self._post(message(self.product)).status_code, 403)
