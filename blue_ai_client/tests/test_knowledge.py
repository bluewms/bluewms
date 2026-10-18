import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon

from ..providers.knowledge import MAX_RESPONSE, RESOURCE_PATHS, SKILL_NAME, WCS_RESOURCE_PATHS, read_policy_knowledge


@tagged('post_install', '-at_install')
class TestCloudKnowledge(BaseCommon):
    def setUp(self):
        super().setUp()
        self.skill = {
            'skill_id': 'skl-approved', 'name': SKILL_NAME, 'version': 7, 'status': 'active',
            'metadata': {'approved': True, 'purpose': 'odoo_runtime_policy'},
            'content': 'Approved project policy reference',
            'manifest': [{'path': path, 'is_executable': False} for path in RESOURCE_PATHS],
        }
        self.requests = []
        self.responses = []
        self.transport = Mock()
        self.transport.post.side_effect = self._post
        self.client = SimpleNamespace(env=self.env, api_url='https://cloud.example/codebuddy/default/v1',
                                      headers=lambda: {'Authorization': 'Bearer private-test-key',
                                                       'x-conversation-id': 'bound-session'},
                                      _http_session=lambda: self.transport)

    def _response(self, data, status=200):
        response = Mock()
        response.status_code = status
        response.iter_content.return_value = [json.dumps({'code': 0, 'data': data}).encode()]
        self.responses.append(response)
        return response

    def _post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        operation = url.rsplit('/', 1)[-1]
        if operation == 'search':
            return self._response({'items': [{'name': SKILL_NAME, 'skill_id': 'skl-approved'}]})
        if operation == 'get':
            return self._response(copy.deepcopy(self.skill))
        path = kwargs['json']['path']
        content = 'Approved cloud body'
        if path in WCS_RESOURCE_PATHS[1:]:
            content = '<!-- bluewms-knowledge ' + json.dumps(getattr(self, 'wcs_header', {})) + ' -->\nWCS approved body'
        return self._response({'path': path, 'version': 7, 'encoding': 'utf-8', 'content': content})

    def test_reads_acl_filtered_approved_version_and_manifest_resources(self):
        bundle, reference = read_policy_knowledge(self.client)
        self.assertEqual(reference['version'], 7)
        self.assertEqual(len(bundle['resources']), 3)
        self.assertNotIn('content', reference)
        self.assertTrue(all('content' not in item for item in reference['resources']))
        self.assertTrue(all(len(item['sha256']) == 64 for item in reference['resources']))
        self.assertEqual(self.requests[0][0], 'https://cloud.example/skill-bridge/v3/skill/search')
        for _, call in self.requests:
            self.assertFalse(call['allow_redirects'])
            self.assertNotIn('user_id', call['json'])
            self.assertNotIn('team_id', call['json'])
            self.assertLessEqual(call['timeout'][1], 10)
        self.assertTrue(all(response.close.called for response in self.responses))
        self.requests.clear()
        self.assertEqual(read_policy_knowledge(self.client, reference)[1], reference)
        self.assertEqual(self.requests[1][1]['json']['version'], 7)

    def test_unapproved_inactive_or_missing_resource_is_rejected(self):
        for change in ({'metadata': {'approved': False}}, {'status': 'archived'},
                       {'manifest': []}, {'name': 'other-project'}):
            original = copy.deepcopy(self.skill)
            self.skill.update(change)
            with self.subTest(change=change), self.assertRaises(UserError):
                read_policy_knowledge(self.client)
            self.skill = original

    def test_private_or_ambiguous_skill_is_never_read(self):
        for items in ([], [{'name': SKILL_NAME, 'skill_id': 'one'}, {'name': SKILL_NAME, 'skill_id': 'two'}]):
            self.transport.post.side_effect = lambda *args, **kwargs: self._response({'items': items})
            with self.assertRaises(UserError):
                read_policy_knowledge(self.client)

    def test_version_or_content_drift_cannot_silently_replace_references(self):
        _, reference = read_policy_knowledge(self.client)
        self.skill['version'] = 8
        with self.assertRaises(UserError):
            read_policy_knowledge(self.client, reference)
        self.skill['version'] = 7
        self.skill['content'] = 'mutated same-version reference'
        with self.assertRaises(UserError):
            read_policy_knowledge(self.client, reference)

    def test_redirect_oversize_and_transport_errors_do_not_leak_vendor_data(self):
        for status, content in ((302, b'private-test-key'), (200, b'x' * (MAX_RESPONSE + 1))):
            response = self._response({}, status)
            response.iter_content.return_value = [content]
            self.transport.post.side_effect = None
            self.transport.post.return_value = response
            with self.assertRaises(UserError) as raised:
                read_policy_knowledge(self.client)
            self.assertNotIn('private-test-key', str(raised.exception))
            self.assertTrue(response.close.called)
        self.transport.post.side_effect = requests.Timeout('private-test-key')
        with self.assertRaises(UserError) as raised:
            read_policy_knowledge(self.client)
        self.assertNotIn('private-test-key', str(raised.exception))

    def _enable_wcs(self):
        self.skill['manifest'] = [{'path': path, 'is_executable': False} for path in RESOURCE_PATHS + WCS_RESOURCE_PATHS]
        self.skill['metadata']['approved_contracts'] = {'wcs_creation': ['wcs_creation/4']}
        self.skill['metadata']['wiki_source'] = {'wiki_id': 'test-project-wiki', 'version': 2}
        self.wcs_header = {'approved': True, 'hook_code': 'wcs_creation', 'contracts': ['wcs_creation/4']}

    def test_wcs_reads_its_approved_contract_and_examples_not_putaway(self):
        self._enable_wcs()
        bundle, reference = read_policy_knowledge(self.client, hook_code='wcs_creation', contract='wcs_creation/4')
        self.assertEqual(bundle['hook_code'], 'wcs_creation')
        self.assertEqual(reference['contract'], 'wcs_creation/4')
        paths = [call['json']['path'] for _, call in self.requests if 'path' in call['json']]
        self.assertEqual(paths, list(WCS_RESOURCE_PATHS))
        self.assertNotIn('04-approved-putaway-examples.md', paths)
        self.assertEqual(read_policy_knowledge(self.client, reference, 'wcs_creation', 'wcs_creation/4')[1], reference)

    def test_wcs_wrong_hook_contract_header_and_missing_body_fail_closed(self):
        self._enable_wcs()
        for change in ({'hook_code': 'putaway_policy'}, {'contracts': ['wcs_creation/3']}, {'approved': False}):
            original = dict(self.wcs_header)
            self.wcs_header.update(change)
            with self.subTest(change=change), self.assertRaises(UserError):
                read_policy_knowledge(self.client, hook_code='wcs_creation', contract='wcs_creation/4')
            self.wcs_header = original
        self.skill['metadata']['approved_contracts'] = {'wcs_creation': ['wcs_creation/3']}
        with self.assertRaises(UserError):
            read_policy_knowledge(self.client, hook_code='wcs_creation', contract='wcs_creation/4')
        self._enable_wcs()
        self.skill['manifest'] = [{'path': RESOURCE_PATHS[0]}]
        with self.assertRaises(UserError):
            read_policy_knowledge(self.client, hook_code='wcs_creation', contract='wcs_creation/4')

    def test_old_local_only_wcs_reference_requires_reopen(self):
        with self.assertRaises(UserError):
            read_policy_knowledge(self.client, {'source': 'local_wcs_contract'}, 'wcs_creation', 'wcs_creation/4')
        self.transport.post.assert_not_called()

    def test_wcs_requires_observed_wiki_source_and_has_no_timeout_fallback(self):
        self._enable_wcs()
        for source in (None, {}, {'wiki_id': 'observed-wiki', 'version': None}):
            self.skill['metadata']['wiki_source'] = source
            with self.subTest(source=source), self.assertRaises(UserError):
                read_policy_knowledge(self.client, hook_code='wcs_creation', contract='wcs_creation/4')
        self._enable_wcs()
        self.transport.post.side_effect = requests.Timeout('private-test-key')
        with self.assertRaises(UserError) as raised:
            read_policy_knowledge(self.client, hook_code='wcs_creation', contract='wcs_creation/4')
        self.assertNotIn('private-test-key', str(raised.exception))
