import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon

from ..providers.knowledge import MAX_RESPONSE, NativeWiki
from ..guard import REQUIRED_GUIDANCE


@tagged('post_install', '-at_install')
class TestCloudKnowledge(BaseCommon):
    def setUp(self):
        super().setUp()
        self.catalog = [{'scope': scope, 'wiki_id': 'wiki-' + scope, 'wiki_version': '2',
                         'asset_version': 1, 'generation_ready': True} for scope in ['common', 'putaway']]
        self.requests, self.responses = [], []
        self.transport = Mock()
        self.transport.post.side_effect = self._post
        self.client = SimpleNamespace(env=self.env, api_url='https://cloud.example/codebuddy/default/v1',
                                      headers=lambda: {'Authorization': 'Bearer private-test-key'},
                                      _connection=lambda: SimpleNamespace(agent_name='personal'),
                                      _http_session=lambda: self.transport)
        self.body = 'Accurate approved Wiki body.'

    def _response(self, data, status=200):
        response = Mock()
        response.status_code = status
        response.iter_content.return_value = [json.dumps({'code': 0, 'data': data}).encode()]
        self.responses.append(response)
        return response

    def _post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        operation = url.rsplit('/', 1)[-1]
        data = {'catalog': copy.deepcopy(self.catalog)}
        if operation == 'context':
            data.update(source='tencent_wiki', hook_code='putaway_policy', contract='putaway_policy/2')
        elif operation == 'search':
            data['results'] = [{'scope': 'putaway', 'ref': 'domains/putaway/specification.md',
                                'title': 'Policy specification', 'snippet': 'Summary only'}]
        elif operation == 'read':
            data.update(content=self.body, reference={**kwargs['json']['page'], 'sha256': hashlib.sha256(self.body.encode()).hexdigest()})
        elif operation == 'verify':
            data['valid'] = True
        return self._response(data)

    def _wiki(self, pinned=None):
        return NativeWiki(self.client, 'putaway_policy', 'putaway_policy/2', pinned)

    def test_context_is_not_full_body_and_search_is_native(self):
        reference = self._wiki().context()
        self.assertEqual(reference['source'], 'tencent_wiki')
        self.assertEqual(reference['pages'], [])
        wiki = self._wiki(reference)
        hits = wiki.search('batch')
        body, page = wiki.read({'scope': hits[0]['scope'], 'ref': hits[0]['ref']})
        self.assertEqual(body, self.body)
        self.assertEqual(page['sha256'], hashlib.sha256(body.encode()).hexdigest())
        self.assertTrue(all('/odoo-wiki/v1/' in url for url, _ in self.requests))
        for _, call in self.requests:
            self.assertFalse(call['allow_redirects'])
            self.assertEqual(call['json']['agent_name'], 'personal')
            self.assertNotIn('user_id', call['json'])
            self.assertNotIn('wiki_id', call['json'])
        self.assertTrue(all(response.close.called for response in self.responses))

    def test_old_skill_and_other_hook_references_require_reopen_before_network(self):
        for pinned in [{'source': 'tencent_skill_bridge'},
                       {'source': 'tencent_wiki', 'hook_code': 'wcs_creation', 'contract': 'wcs_creation/4'}]:
            with self.assertRaises(UserError):
                self._wiki(pinned)
        self.transport.post.assert_not_called()

    def test_readiness_approval_and_version_drift_are_not_silently_replaced(self):
        pinned = self._wiki().context()
        for field, value in [('wiki_version', '3'), ('asset_version', 2), ('generation_ready', False)]:
            before = copy.deepcopy(self.catalog)
            self.catalog[1][field] = value
            with self.subTest(field=field), self.assertRaises(UserError):
                self._wiki(pinned).search('policy')
            self.catalog = before

    def test_body_digest_mismatch_is_rejected(self):
        response = self._response({'catalog': self.catalog, 'content': 'changed body',
                                   'reference': {'scope': 'putaway', 'ref': 'approved.md', 'sha256': 'wrong'}})
        self.transport.post.side_effect = None
        self.transport.post.return_value = response
        with self.assertRaises(UserError):
            self._wiki().read({'scope': 'putaway', 'ref': 'approved.md'})

    def test_submit_verification_requires_real_pages_and_sends_no_body(self):
        pinned = self._wiki().context()
        with self.assertRaises(UserError):
            self._wiki(pinned).verify()
        pinned['pages'] = [{'scope': scope, 'role': role, 'ref': role + '.md', 'sha256': 'a' * 64, 'bytes': 40}
                           for scope, role in [('common', 'guidance'), ('putaway', 'specification'), ('putaway', 'example')]]
        pinned['pages'].extend({'scope': 'common', 'role': 'guidance', 'ref': ref,
                                'sha256': 'a' * 64, 'bytes': 40} for ref in REQUIRED_GUIDANCE)
        self._wiki(pinned).verify()
        sent = self.requests[-1][1]['json']['references']
        self.assertNotIn('bytes', sent[0])
        self.assertNotIn('content', sent[0])

    def test_redirect_oversize_and_transport_errors_do_not_leak_vendor_data(self):
        for status, raw in [(302, b'private-test-key'), (403, b'private-test-key'), (200, b'x' * (MAX_RESPONSE + 1))]:
            response = self._response({}, status)
            response.iter_content.return_value = [raw]
            self.transport.post.side_effect = None
            self.transport.post.return_value = response
            with self.subTest(status=status), self.assertRaises(UserError) as raised:
                self._wiki().context()
            self.assertNotIn('private-test-key', str(raised.exception))
            self.assertTrue(response.close.called)
        self.transport.post.side_effect = requests.Timeout('private-test-key')
        with self.assertRaises(UserError) as raised:
            self._wiki().context()
        self.assertNotIn('private-test-key', str(raised.exception))

    def test_search_limits_are_checked_before_http(self):
        for query in ['', 'x' * 257, None]:
            with self.subTest(query=query), self.assertRaises(UserError):
                self._wiki().search(query)
        self.transport.post.assert_not_called()
