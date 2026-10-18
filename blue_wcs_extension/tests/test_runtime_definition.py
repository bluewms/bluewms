from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .test_wcs import TestWcs


class TestWcsRuntimeDefinition(TransactionCase):
    def test_production_wcs_definition_has_no_generation_examples(self):
        definition = self.env.ref('blue_wcs_extension.blue_scene_template_wcs')
        self.assertTrue(definition.active)
        self.assertTrue(definition.cloud_managed)
        self.assertEqual(definition.contract, 'wcs_creation/4')
        self.assertFalse(definition.code_text)
        self.assertFalse(definition.requirements)
        self.assertFalse(definition.test_cases)
        profile = self.env['blue.config.profile'].create({'name': 'Cloud WCS', 'template_id': definition.id})
        with self.assertRaises(UserError):
            profile.action_load_example()
        old = self.env.ref('blue_wcs_extension.template_repeat_v4')
        self.assertFalse(old.active)
        self.assertTrue(old.cloud_managed)
        self.assertFalse(old.code_text)


class TestWcsOfflineExecution(TestWcs):
    def test_basic_and_published_execution_need_no_cloud(self):
        picking, line, operation = self._loose_incoming()
        with patch('odoo.addons.blue_ai_client.mcp.code_asset.read_policy_knowledge', side_effect=UserError('cloud unavailable')):
            picking.action_create_wcs_request_from_button()
        self.assertEqual(len(picking.wcs_request_ids), 1)
        other, line, operation = self._picking()
        with patch('odoo.addons.blue_ai_client.mcp.code_asset.read_policy_knowledge', side_effect=UserError('cloud unavailable')):
            other.action_create_wcs_request_from_button()
        self.assertEqual(len(other.wcs_request_ids), 2)
