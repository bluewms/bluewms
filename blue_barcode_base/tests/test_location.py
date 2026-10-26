from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged('post_install', '-at_install')
class TestLocationBarcode(BaseCommon):
    def test_preview_follows_unsaved_barcode_edits_and_clearing(self):
        location = self.env['stock.location'].new({'name': 'Preview', 'barcode': 'LOC-001'})
        first = location.barcode_img.content
        self.assertTrue(first.startswith(b'\x89PNG\r\n\x1a\n'))
        location.barcode = 'LOC-002'
        self.assertNotEqual(location.barcode_img.content, first)
        location.barcode = False
        self.assertFalse(location.barcode_img)

    def test_unsupported_preview_keeps_location_editable(self):
        location = self.env['stock.location'].new({'name': 'Preview', 'barcode': 'LOC-001'})
        with patch.object(type(self.env['ir.actions.report']), 'barcode', side_effect=ValueError('unsupported')):
            self.assertFalse(location.barcode_img)
        self.assertEqual(location.barcode, 'LOC-001')
