import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon

from ..providers.knowledge import MAX_RESPONSE, RESOURCE_PATHS, SKILL_NAME, read_policy_knowledge


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
        return self._response({'path': kwargs['json']['path'], 'version': 7,
                               'encoding': 'utf-8', 'content': 'Approved cloud body'})

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
