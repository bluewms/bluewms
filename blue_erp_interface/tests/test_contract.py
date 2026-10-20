from copy import deepcopy
from unittest.mock import Mock, patch

import requests

from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon

from ..tools.contract import ProtocolError, mapping_schema, run_mapping
from ..tools.transport import send
from .common import fixture


@tagged('post_install', '-at_install')
class TestErpContract(BaseCommon):
    def test_declared_cases_match_exactly(self):
        example = fixture()
        for case in example['cases'] + example['inventory_cases']:
            with self.subTest(case=case['name']):
                self.assertEqual(run_mapping(example['code'], case['input']), case['expected_result'])
        self.assertEqual(mapping_schema()['contract'], 'erp_mapping/1')

    def test_import_and_unbounded_python_are_rejected(self):
        data = fixture()['cases'][0]['input']
        for code in ['import os', 'result = env["stock.quant"]', 'while True: pass', 'result = request.__class__',
                     'request = {}', 'result = {"documents": []}']:
            with self.subTest(code=code), self.assertRaises(ProtocolError):
                run_mapping(code, data)

    def test_invalid_numbers_and_repeated_rows_are_rejected(self):
        example = fixture()
        for qty in [0, -1, float('nan'), float('inf'), True]:
            data = deepcopy(example['cases'][0]['input'])
            data['candidates'][0]['qty'] = qty
            with self.subTest(qty=qty), self.assertRaises(ProtocolError):
                run_mapping(example['code'], data)
        data = deepcopy(example['cases'][0]['input'])
        data['candidates'] *= 2
        with self.assertRaises(ProtocolError):
            run_mapping(example['code'], data)

    def test_output_cannot_request_arbitrary_url_or_model(self):
        data = fixture()['cases'][1]['input']
        for code in ['result = {"actions": [{"operation": "https://bad.invalid", "body": {}}]}',
                     'result = {"actions": [{"operation": "complete", "body": {}, "model": "stock.quant"}]}']:
            with self.assertRaises(ProtocolError):
                run_mapping(code, data)

    def _connection(self):
        return {'url': 'https://erp.invalid/complete', 'app_key': 'test-only-key', 'app_secret': 'test-only-secret',
                'auth_mode': 'bearer', 'idempotency_key': 'stable-event:1'}

    def test_http_uses_stable_key_and_local_credentials(self):
        response = Mock(status_code=200)
        response.iter_content.return_value = [b'{"success":true,"number":"ERP-DONE"}']
        with patch('odoo.addons.blue_erp_interface.tools.transport.requests.post', return_value=response) as post:
            result = send(self._connection(), 'complete', {'qty': 6}, {'X-App-Secret': '$app_secret'}, fixture()['code'], fixture()['cases'][1]['input'])
        self.assertEqual(result, ('done', 'ERP-DONE'))
        self.assertEqual(post.call_args.kwargs['headers']['Idempotency-Key'], 'stable-event:1')
        self.assertEqual(post.call_args.kwargs['headers']['X-App-Secret'], 'test-only-secret')
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        response.close.assert_called_once()

    def test_timeout_and_invalid_response_remain_unknown(self):
        with patch('odoo.addons.blue_erp_interface.tools.transport.requests.post', side_effect=requests.Timeout):
            self.assertEqual(send(self._connection(), 'complete', {}, {}, fixture()['code'], fixture()['cases'][1]['input']), ('unknown', ''))
        response = Mock(status_code=200)
        response.iter_content.return_value = [b'not json']
        with patch('odoo.addons.blue_erp_interface.tools.transport.requests.post', return_value=response):
            self.assertEqual(send(self._connection(), 'complete', {}, {}, fixture()['code'], fixture()['cases'][1]['input']), ('unknown', ''))

    def test_header_injection_sends_nothing(self):
        with patch('odoo.addons.blue_erp_interface.tools.transport.requests.post') as post:
            self.assertEqual(send(self._connection(), 'complete', {}, {'Host': 'other.invalid'}, fixture()['code'], fixture()['cases'][1]['input']), ('failed', ''))
            post.assert_not_called()
