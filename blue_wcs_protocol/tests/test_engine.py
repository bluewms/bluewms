import copy

from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon

from ..tools.protocol import ProtocolError, run_protocol, validate_protocol
from .common import fixture


@tagged('post_install', '-at_install')
class TestProtocolEngine(BaseCommon):
    def test_full_published_examples_have_exact_three_phase_results(self):
        for name in ['tusk-subposition', 'tusk-destination']:
            example = fixture(name)
            for case in example['cases']:
                with self.subTest(name=name, phase=case['name']):
                    self.assertEqual(run_protocol(example['code'], case['input']), case['expected_result'])

    def test_imports_private_attributes_and_arbitrary_calls_rejected(self):
        for code in ['import os', 'result = request.__class__', 'result = eval("1")',
                     'result = open("/etc/passwd")', 'while True: pass', 'request = {}',
                     'request["phase"] = "callback"', 'result = {"body": request.get.__globals__}']:
            with self.subTest(code=code), self.assertRaises(ProtocolError):
                validate_protocol(code)

    def test_input_aliases_cannot_mutate_original_data(self):
        data = fixture()['cases'][0]['input']
        before = copy.deepcopy(data)
        result = run_protocol('items = candidates\nitems.append({"extra": 1})\nresult = {"body": {"items": items}}', data)
        self.assertEqual(data, before)
        self.assertEqual(len(result['body']['items']), 2)

    def test_connection_and_foreign_task_outputs_rejected(self):
        case = fixture()['cases'][0]
        with self.assertRaises(ProtocolError):
            run_protocol('result = {"body": {}, "url": "http://other"}', case['input'])
        callback = fixture()['cases'][-1]
        code = fixture()['code'].replace('request["message"]["taskId"]', '"another-task"')
        with self.assertRaises(ProtocolError):
            run_protocol(code, callback['input'])

    def test_oversized_and_nonfinite_input_rejected(self):
        for changes in [{'candidates': [{}] * 201}, {'request': {'phase': float('nan')}},
                        {'candidates': [{'text': 'x' * 8193}]}]:
            data = {**fixture()['cases'][0]['input'], **changes}
            with self.subTest(changes=list(changes)), self.assertRaises(ProtocolError):
                run_protocol(fixture()['code'], data)

    def test_vendor_field_slicing_and_bounded_goods_loop(self):
        data = fixture()['cases'][0]['input']
        code = 'items = []\nfor candidate in candidates:\n    items.append({"sku": candidate["product_code"], "qty": str(candidate["quantity"])})\nresult = {"body": {"prefix": request["task"]["destination"][:1], "items": items}}'
        result = run_protocol(code, data)
        self.assertEqual(result['body']['items'], [{'sku': 'SKU-1', 'qty': '10'}])
        self.assertEqual(result['body']['prefix'], 'B')

    def test_repeated_local_list_copy_cannot_amplify_memory(self):
        data = copy.deepcopy(fixture()['cases'][0]['input'])
        data['candidates'] = [{}] * 200
        code = 'items = []\nfor candidate in candidates:\n    items.append(items)\nresult = {"body": {"items": items}}'
        with self.assertRaises(ProtocolError):
            run_protocol(code, data)
