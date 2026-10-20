import json

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon

from ..tools.contract import ProtocolError, between, run_barcode, validate_code

CODE = """if request['phase'] == 'parse':
    raw = request['raw']
    result = {'kind': 'product', 'code': between(raw, '#', 2, 3), 'quantity': float(between(raw, '#', 4, 5)), 'lot': '', 'location': '', 'package': '', 'uom': '', 'reason': ''}
else:
    result = {'action': 'prompt', 'keys': [], 'reason': 'Select a row'}
    if len(candidates) == 1:
        result = {'action': 'count', 'keys': [candidates[0]['key']], 'reason': ''}
"""


def payload(raw='HDR#VENDOR#QRPRODUCT#LOT88#12#END', phase='parse', candidates=None):
    return {'request': {'phase': phase, 'raw': raw, 'context': {}, 'parsed': {}}, 'candidates': candidates or []}


@tagged('post_install', '-at_install')
class TestBarcodeContract(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    def test_delimiter_occurrences_preserve_empty_fields(self):
        self.assertEqual(between('HDR##QRPRODUCT#LOT88#12#END', '#', 2, 3), 'QRPRODUCT')
        self.assertEqual(between('x####z#', '#', 2, 3), '')
        with self.assertRaises(ProtocolError):
            between('HDR#V#P#LOT#12', '#', 4, 5)
        with self.assertRaises(ProtocolError):
            between('###', '#', True, 2)

    def test_parse_product_and_quantity_once(self):
        result = run_barcode(CODE, payload())
        self.assertEqual(result['code'], 'QRPRODUCT')
        self.assertEqual(result['quantity'], 12)
        self.assertFalse(result['lot'])
        for raw in ('HDR#V#P#L#NaN#', 'HDR#V#P#L#-1#', 'HDR#V##L#12#'):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                run_barcode(CODE, payload(raw))

    def test_no_import_eval_attributes_or_unbounded_split(self):
        for code in ("import os", "result = eval('1')", "result = request.__class__", "result = request['raw'].split('#')"):
            with self.subTest(code=code), self.assertRaises(ProtocolError):
                validate_code(code)

    def test_decide_rejects_foreign_keys(self):
        code = "result = {'action': 'count', 'keys': ['other'], 'reason': ''}"
        with self.assertRaises(ProtocolError):
            run_barcode(code, payload(phase='decide', candidates=[{'key': 'allowed'}]))

    def _profile(self):
        return self.env['blue.config.profile'].create({'name': 'QR test policy', 'company_id': self.env.company.id,
            'template_id': self.env.ref('blue_barcode_extension.template_barcode').id})

    def test_exact_trials_and_publication(self):
        profile = self._profile()
        cases = [{'name': 'parse', 'input': payload(), 'expected_result': run_barcode(CODE, payload())},
            {'name': 'decide', 'input': payload(phase='decide', candidates=[{'key': 'line:1'}]),
             'expected_result': {'action': 'count', 'keys': ['line:1'], 'reason': ''}}]
        profile.write({'draft_code': CODE, 'draft_tests': json.dumps(cases)})
        profile.action_validate()
        self.assertFalse(profile.active_release_id)
        profile.action_publish()
        self.assertTrue(profile.active_release_id)
        self.assertEqual(profile.contract, 'barcode_policy/1')

    def test_unpublished_bound_policy_blocks_scan_and_freezes_release(self):
        warehouse = self.env['stock.warehouse'].create({'name': 'QR warehouse', 'code': 'QRS'})
        product = self.env['product.product'].create({'name': 'QR product', 'is_storable': True, 'barcode': 'QRPRODUCT'})
        picking = self.env['stock.picking'].create({'picking_type_id': warehouse.in_type_id.id,
            'location_id': warehouse.in_type_id.default_location_src_id.id, 'location_dest_id': warehouse.lot_stock_id.id})
        self.env['stock.move'].create({'picking_id': picking.id, 'product_id': product.id,
            'product_uom_qty': 100, 'uom_id': product.uom_id.id,
            'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id})
        picking.action_confirm()
        profile = self._profile()
        warehouse.in_type_id.blue_barcode_profile_id = profile
        with self.assertRaises(UserError):
            self.env['blue.barcode.service'].open_session('picking', picking.id, 'qr_client_00000001')
        cases = [{'name': phase, 'input': payload(phase=phase), 'expected_result': run_barcode(CODE, payload(phase=phase))}
                 for phase in ('parse', 'decide')]
        profile.write({'draft_code': CODE, 'draft_tests': json.dumps(cases)})
        profile.action_validate()
        profile.action_publish()
        view = self.env['blue.barcode.service'].open_session('picking', picking.id, 'qr_client_00000001')
        session = self.env['blue.barcode.session'].browse(view['id'])
        frozen = session.policy_snapshot['release_id']
        profile.write({'draft_code': 'result = {}'})
        session.action_event('qr_client_00000001', 'qr_event_00000001', 0, {'raw': payload()['request']['raw']})
        self.assertEqual(picking.move_line_ids.quantity, 12)
        self.assertEqual(session.policy_snapshot['release_id'], frozen)
