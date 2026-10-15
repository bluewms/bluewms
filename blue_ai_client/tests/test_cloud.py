import copy
import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.muk_ai.providers.base import PROVIDER_STATE_KEY

from ..providers.chat_completions import BlueCloudProvider, normalize_url


def chunk(delta=None, finish=None, identity='chat-test', usage=None):
    return {'id': identity, 'choices': [{'index': 0, 'delta': delta or {}, 'finish_reason': finish}],
            **({'usage': usage} if usage else {})}


def form(questions):
    return [chunk({'tool_calls': [{'index': 0, 'id': 'call_session_init_test', 'function': {
        'name': 'ask_followup_question', 'arguments': json.dumps({'questions': questions}),
    }}]}, identity='session-init-test'), chunk(finish='tool_calls', identity='session-init-test')]


@tagged('post_install', '-at_install')
class TestBlueCloud(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref('blue_ai_client.provider_blue_cloud')
        cls.provider.active = True
        cls.manager = new_test_user(cls.env, login='blue_ai_manager', groups='stock.group_stock_manager')
        cls.worker = new_test_user(cls.env, login='blue_ai_worker', groups='stock.group_stock_user')
        cls.connection = cls.env['blue.ai.connection'].create({
            'user_id': cls.manager.id, 'agent_name': 'personal-agent', 'api_key': 'private-test-key',
        })
        cls.code = 'result = []\nfor candidate in candidates:\n    result.append({"location_id": candidate["location_id"], "score": 0, "reason": "ok"})'
        cls.tests = json.dumps([{'name': 'empty', 'input': {'request': {}, 'candidates': []}, 'expected_order': []}])
        cls.template = cls.env['blue.scene.template'].create({
            'name': 'Cloud test', 'contract': 'putaway_policy/1', 'code_text': cls.code,
            'test_cases': cls.tests, 'requirements': 'test',
        })
        cls.profile = cls.env['blue.config.profile'].create({'name': 'Cloud scene', 'template_id': cls.template.id})
        cls.profile.with_user(cls.manager).action_load_example()

    def _client(self):
        return self.provider.with_user(self.manager).with_context(blue_ai_session_uuid='stable-test-id')._get_client()

    def _session(self):
        action = self.profile.with_user(self.manager).action_blue_ai_chat()
        return self.env['muk_ai.session'].with_user(self.manager).browse(action['params']['session_id'])

    def test_url_normalization(self):
        base = 'https://odooapi.royalblue56.com/codebuddy/default/v1'
        self.assertEqual(normalize_url(base[:-3]), base)
        self.assertEqual(normalize_url(base + '/chat/completions'), base)
        self.assertEqual(normalize_url('https://example.com/v1/'), 'https://example.com/v1')
        for address in ['http://example.com/v1', 'https://key@example.com/v1', 'https://example.com/?key=x']:
            with self.assertRaises(ValueError):
                normalize_url(address)

    def test_credentials_are_private_and_user_scoped(self):
        self.assertEqual(self._client().headers()['Authorization'], 'Bearer private-test-key')
        with self.assertRaises(AccessError):
            self.connection.with_user(self.manager).read(['api_key'])
        self.assertFalse(self.env['blue.ai.connection'].with_user(self.worker).search([]))
        with self.assertRaises(UserError):
            self.provider.with_user(self.worker)._get_client().headers()
        with self.assertRaises(AccessError):
            self.connection.with_user(self.manager).write({'agent_name': 'other-person'})

    def test_initialization_selects_exact_names_then_streams(self):
        replies = [
            form([{'id': 'asset_confirm', 'options': ['是，关联团队资产', '否，本次不关联']}]),
            form([{'id': 'team', 'options': ['odooAI (team1234)', 'other (other123)']}]),
            form([{'id': 'agent', 'options': ['personal-agent (agent123)']},
                  {'id': 'task', 'options': ['日常任务 (task1234)']}]),
            [chunk({'content': '你好'}), chunk(finish='stop', usage={'prompt_tokens': 3, 'completion_tokens': 2})],
        ]
        sent, deltas = [], []
        def stream(client, path, body):
            sent.append(copy.deepcopy(body))
            return iter(replies.pop(0))
        with patch.object(BlueCloudProvider, '_post_stream', stream):
            result = self._client().request([{'role': 'user', 'content': 'hi'}], on_delta=lambda *args: deltas.append(args))
        self.assertEqual(result['text'], '你好')
        self.assertEqual(result['usage']['input_tokens'], 3)
        self.assertEqual(len(sent), 4)
        answer = json.loads(sent[-1]['messages'][-1]['content'])
        self.assertEqual(answer['result']['answers']['agent'], 'personal-agent (agent123)')
        self.assertEqual([kind for kind, data in deltas], ['text'])

    def test_missing_or_ambiguous_names_fail_closed(self):
        for options in [['someone-else (x)'], ['personal-agent (x)', 'personal-agent (y)']]:
            with patch.object(BlueCloudProvider, '_post_stream', return_value=iter(form([{'id': 'agent', 'options': options}]))):
                with self.assertRaises(UserError):
                    self._client().request([{'role': 'user', 'content': 'hi'}])

    def test_fragmented_tool_calls_and_reasoning_replay(self):
        events = [chunk({'reasoning_content': 'think'}), chunk({'tool_calls': [{
            'index': 0, 'id': 'call1', 'function': {'name': 'blue_read_code_asset', 'arguments': '{'},
        }]}), chunk({'tool_calls': [{'index': 0, 'function': {'arguments': '}'}}]}), chunk(finish='tool_calls')]
        with patch.object(BlueCloudProvider, '_post_stream', return_value=iter(events)):
            result = self._client().request([{'role': 'user', 'content': 'hi'}])
        self.assertEqual(result['tool_calls'][0]['arguments'], {})
        history = BlueCloudProvider._inputs_to_messages(result['carry_inputs'] + [
            {'type': 'function_call_output', 'call_id': 'call1', 'output': {'ok': True}},
        ])
        self.assertEqual(history[0]['reasoning_content'], 'think')
        self.assertEqual(history[0]['tool_calls'][0]['id'], 'call1')
        self.assertEqual(json.loads(history[1]['content']), {'ok': True})

    def test_truncated_and_broken_streams(self):
        with patch.object(BlueCloudProvider, '_post_stream', return_value=iter([chunk({'content': 'partial'}), chunk(finish='length')])):
            result = self._client().request([{'role': 'user', 'content': 'hi'}])
        self.assertIn('truncated', result['text'].lower())
        with patch.object(BlueCloudProvider, '_post_stream', return_value=iter([chunk({'content': 'partial'})])):
            with self.assertRaises(UserError):
                self._client().request([{'role': 'user', 'content': 'hi'}])

    def test_asset_tools_save_validate_without_publish(self):
        session = self._session()
        tools = self.env['muk_mcp.mixin'].with_user(self.manager).with_context(muk_mcp_session_id=session.id)
        asset = tools._mcp_blue_read_code_asset()
        saved = tools._mcp_blue_submit_code_draft(self.code, self.tests, 'generated', asset['draft_hash'])
        result = tools._mcp_blue_validate_code_draft(saved['draft_hash'])
        self.assertTrue(result['valid'])
        self.assertFalse(self.profile.active_release_id)
        self.assertEqual(self.profile.draft_source, 'ai')
        self.assertTrue(self.profile.validated_version_id)

    def test_concurrent_manual_edit_is_not_overwritten(self):
        session = self._session()
        self.profile.with_user(self.manager).requirements = 'manual change after opening chat'
        tools = self.env['muk_mcp.mixin'].with_user(self.manager).with_context(muk_mcp_session_id=session.id)
        with self.assertRaises(UserError):
            tools._mcp_blue_submit_code_draft(self.code, self.tests, 'overwrite', session.blue_draft_hash)
        self.assertEqual(self.profile.with_user(self.manager).requirements, 'manual change after opening chat')

    def test_tools_reject_unbound_or_unauthorized_sessions(self):
        with self.assertRaises(AccessError):
            self.profile.with_user(self.worker).action_blue_ai_chat()
        session = self._session()
        tools = self.env['muk_mcp.mixin'].with_user(self.worker).with_context(muk_mcp_session_id=session.id)
        with self.assertRaises(AccessError):
            tools._mcp_blue_read_code_asset()
        with self.assertRaises(AccessError):
            session.write({'blue_profile_id': False})
        with self.assertRaises(AccessError):
            self.env['muk_ai.session'].with_user(self.manager).create({'name': 'forged', 'blue_profile_id': self.profile.id})

    def test_invalid_code_cannot_be_submitted(self):
        session = self._session()
        tools = self.env['muk_mcp.mixin'].with_user(self.manager).with_context(muk_mcp_session_id=session.id)
        with self.assertRaises(ValidationError):
            tools._mcp_blue_submit_code_draft('import os', self.tests, 'unsafe', session.blue_draft_hash)
        self.assertEqual(self.profile.with_user(self.manager).draft_code, self.code)

    def test_settings_share_provider_and_user_configuration(self):
        settings = self.env['res.config.settings'].with_user(self.env.ref('base.user_admin')).create({})
        self.assertEqual(settings.blue_provider_id, self.provider)
        settings.blue_cloud_url = 'https://example.com/v1'
        self.assertEqual(self.provider.with_user(self.env.ref('base.user_admin')).api_url, 'https://example.com/v1')

    def test_connection_changes_get_a_new_proxy_session(self):
        initial = self._client().headers()['x-conversation-id']
        self.assertEqual(self._client().headers()['x-conversation-id'], initial)
        self.connection.sudo().agent_name = 'new-agent'
        self.assertNotEqual(self._client().headers()['x-conversation-id'], initial)

    def test_redirects_and_http_errors_do_not_expose_secrets(self):
        class Response:
            status_code = 302
            text = 'private-test-key'
            def close(self):
                pass
        with patch.object(BlueCloudProvider, '_http_session') as transport:
            transport.return_value.post.return_value = Response()
            with self.assertRaises(UserError) as raised:
                self._client()._post('/chat/completions', {}, 15)
            self.assertNotIn('private-test-key', str(raised.exception))
            self.assertFalse(transport.return_value.post.call_args.kwargs['allow_redirects'])

    def test_a_published_base_cannot_be_replaced_by_an_old_chat(self):
        session = self._session()
        profile = self.profile.with_user(self.manager)
        profile.action_validate()
        profile.action_publish()
        tools = self.env['muk_mcp.mixin'].with_user(self.manager).with_context(muk_mcp_session_id=session.id)
        with self.assertRaises(UserError):
            tools._mcp_blue_submit_code_draft(self.code, self.tests, 'stale', session.blue_draft_hash)
        self.assertTrue(profile.active_release_id)

    def test_general_tools_stay_blocked_in_a_code_session(self):
        session = self._session()
        session.agent_id = self.env.ref('muk_ai.agent_general')
        result, ok = session._dispatch_tool_call('call_method', {'model': 'blue.config.profile', 'method': 'action_publish'}, 'bad')
        self.assertFalse(ok)
        self.assertIn('error', result)
        names = {entry['name'] for entry in session._get_filtered_catalog()}
        self.assertNotIn('call_method', names)

    def test_shared_reader_cannot_steer_asset_tools(self):
        session = self._session()
        session.share_user_ids = self.worker
        tools = self.env['muk_mcp.mixin'].with_user(self.worker).with_context(muk_mcp_session_id=session.id)
        with self.assertRaises(AccessError):
            tools._mcp_blue_read_code_asset()

    def test_muk_runtime_completes_read_submit_validate_loop(self):
        session = self._session()
        rounds = []
        def stream(client, path, body):
            rounds.append(copy.deepcopy(body))
            number = len(rounds)
            profile = self.profile.with_user(self.manager)
            calls = {
                1: ('blue_read_code_asset', {}),
                2: ('blue_submit_code_draft', {'code': self.code, 'tests': self.tests,
                    'requirements': 'cloud generated', 'expected_hash': profile._draft_hash()}),
                3: ('blue_validate_code_draft', {'expected_hash': profile._draft_hash()}),
            }
            if number == 4:
                return iter([chunk({'content': '草稿已验证，请审阅后发布。'}), chunk(finish='stop')])
            name, arguments = calls[number]
            return iter([chunk({'tool_calls': [{'index': 0, 'id': f'call{number}', 'function': {
                'name': name, 'arguments': json.dumps(arguments),
            }}]}), chunk(finish='tool_calls')])
        with patch.object(BlueCloudProvider, '_post_stream', stream):
            session.start('生成代码并验证')
        self.assertEqual(session.state, 'done', session.error_message)
        self.assertEqual(len(rounds), 4)
        profile = self.profile.with_user(self.manager)
        self.assertTrue(profile.validated_version_id)
        self.assertFalse(profile.active_release_id)
        self.assertEqual(profile.requirements, 'cloud generated')

    def test_archived_connection_cannot_be_reenabled_through_context(self):
        self.connection.sudo().active = False
        with self.assertRaises(UserError):
            self.provider.with_user(self.manager).with_context(active_test=False)._get_client().headers()
