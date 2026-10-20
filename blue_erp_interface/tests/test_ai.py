import json
from unittest.mock import patch

from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.blue_ai_client.tests.wiki_fixtures import FakeNativeWiki

from .common import make_interface


@tagged('post_install', '-at_install')
class TestErpAiAsset(BaseCommon):
    _test_user_groups = ('stock.group_stock_manager', 'base.group_system')

    def test_erp_task_reads_contract_then_saves_and_validates_without_publish(self):
        warehouse = self.env['stock.warehouse'].create({'name': 'ERP AI warehouse', 'code': 'ERPA'})
        product = self.env['product.product'].create({'name': 'ERP AI product', 'default_code': 'ERP-PRODUCT', 'is_storable': True})
        interface = make_interface(self.env, warehouse, product, publish=False)
        self.env.ref('blue_ai_client.provider_blue_cloud').active = True
        self.env['blue.ai.connection'].create({'user_id': self.env.uid, 'agent_name': 'erp-test-agent', 'api_key': 'erp-test-ai-key'})
        session_action = interface.action_ai()
        session = self.env['muk_ai.session'].browse(session_action['params']['session_id'])
        self.assertEqual(session.blue_task_name, 'ERP接口')
        tools = self.env['muk_mcp.mixin'].with_context(muk_mcp_session_id=session.id)
        with patch('odoo.addons.blue_ai_client.mcp.code_asset.NativeWiki', FakeNativeWiki):
            asset = tools._mcp_blue_read_code_asset()
            self.assertEqual(asset['contract_schema']['contract'], 'erp_mapping/1')
            self.assertNotIn('test-only-secret', json.dumps(asset))
            for hit in tools._mcp_blue_search_code_knowledge('ERP mapping')['results']:
                tools._mcp_blue_read_code_knowledge(hit['page_ref'])
            saved = tools._mcp_blue_submit_code_draft(interface.code, interface.tests, 'ERP AI generated test', asset['draft_hash'])
            result = tools._mcp_blue_validate_code_draft(saved['draft_hash'])
        self.assertTrue(result['valid'])
        self.assertFalse(interface.profile_id.active_release_id)
        self.assertEqual(interface.profile_id.draft_source, 'ai')
