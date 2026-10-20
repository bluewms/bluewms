import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('gateway', Path(__file__).parents[1] / 'native_wiki_gateway.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeGateway(module.NativeWikiGateway):
    def __init__(self):
        super().__init__({'team_id': 'team', 'wikis': {s: s for s in ['common', 'putaway', 'wcs', 'erp', 'equipment', 'barcode']}})
        self.allowed = True
        self.task_present = True
        self.valid_key = True
        self.user_id = 'owner'
        self.agent_id = 'agent'
        self.task_overrides = {}
        self.duplicate_task = False
        self.task_link_active = True
        self.assets = {}
        self.pages = {}
        self.versions = {}
        for scope, refs in {'common': ['basics/overview.md'], 'putaway': ['domains/putaway/specification.md', 'domains/putaway/examples/same-picking.md'], 'wcs': ['domains/wcs/specification.md'], 'erp': ['domains/erp/specification.md'], 'equipment': ['domains/equipment/specification.md']}.items():
            contracts = [] if scope in ['common', 'erp'] else ['putaway_policy/2'] if scope == 'putaway' else ['device_protocol/1'] if scope == 'equipment' else ['wcs_creation/4']
            self.pages[scope] = {ref: '---\ncontracts: ' + json.dumps(contracts) + '\n---\nAccurate reference.' for ref in refs}
            self.versions[scope] = '2'
            metadata = {'scope': scope, 'purpose': 'odoo_runtime_code_generation', 'generation_ready': scope != 'erp',
                        'approved': scope != 'erp', 'approved_contracts': contracts, 'wiki_version': '2',
                        'source_commit': 'source', 'approved_pages': [{'ref': ref, 'page_sha256': module.digest(body)} for ref, body in self.pages[scope].items()]}
            self.assets[scope] = {'asset_id': scope, 'team_id': 'team', 'status': 'candidate' if scope == 'erp' else 'approved', 'version': 1, 'metadata_json': json.dumps(metadata)}

    def _core(self, path, body, key, deadline):
        if path == 'auth/verify':
            return {'valid': self.valid_key, 'user': {'user_id': self.user_id} if self.valid_key else None}
        if path == 'agent/list':
            return {'items': [{'agent_id': self.agent_id, 'owner_user_id': self.user_id, 'team_id': 'team', 'name': 'personal', 'status': 'active'}]}
        if path == 'agent-fixed-asset/list-with-detail':
            return {'items': [{'asset_id': s, 'status': a['status']} for s, a in self.assets.items()]}
        if path == 'acl/check':
            return {'allowed': self.allowed}
        if path == 'asset/get':
            return self.assets[body['asset_id']]
        if path == 'task/list':
            hook = next(h for h, title in module.TASK_NAMES.items() if title == body['title'])
            task = {'task_id': 'shared-' + hook, 'team_id': 'team', 'title': body['title'],
                    'creator_user_id': 'team-admin', 'status': 'running', **self.task_overrides}
            tasks = [task] if self.task_present else []
            if self.duplicate_task:
                tasks.append({**task, 'task_id': 'duplicate'})
            if body.get('creator_user_id'):
                tasks = [t for t in tasks if t['creator_user_id'] == body['creator_user_id']]
            return {'items': tasks}
        if path == 'task-agent/list':
            return {'items': [{'agent_id': self.agent_id, 'status': 'active' if self.task_link_active else 'inactive'}]}
        raise AssertionError(path)

    def _native(self, operation, wiki_id, params, key, deadline):
        if operation == 'list':
            return {'tools': [{'name': n} for n in ['search', 'read_page', 'get_info']]}
        tool = params['tool_name']
        if tool == 'get_info':
            return {'status': 'ready', 'version': self.versions[wiki_id]}
        if tool == 'search':
            return {'results': [{'path': 'wiki/' + ref, 'title': ref} for ref in self.pages[wiki_id]]}
        if tool == 'read_page':
            return {'items': [{'content': self.pages[wiki_id][params['params']['refs'][0]]}]}
        raise AssertionError(tool)


class TestNativeGateway(unittest.TestCase):
    def setUp(self):
        self.gateway = FakeGateway()
        self.payload = {'hook_code': 'putaway_policy', 'contract': 'putaway_policy/2', 'agent_name': 'personal'}

    def request(self, operation, **values):
        return self.gateway.handle(operation, {**self.payload, **values}, 'business-key')

    def test_native_search_reads_current_scoped_pages(self):
        data = self.request('search', query='same picking')
        self.assertEqual({r['scope'] for r in data['results']}, {'common', 'putaway'})
        page = data['results'][0]
        read = self.request('read', page=page)
        self.assertEqual(module.digest(read['content']), read['reference']['sha256'])

    def test_submission_requires_guidance_specification_and_example(self):
        hits = self.request('search', query='policy')['results']
        refs = [self.request('read', page=h)['reference'] for h in hits]
        self.assertTrue(self.request('verify', references=refs)['valid'])
        with self.assertRaises(module.Rejected):
            self.request('verify', references=refs[1:])

    def test_acl_revocation_and_invalid_credential_fail_closed(self):
        self.gateway.allowed = False
        with self.assertRaises(module.Rejected):
            self.request('context')
        self.gateway.allowed = True
        self.gateway.valid_key = False
        with self.assertRaises(module.Rejected):
            self.request('context')

    def test_model_cannot_choose_identity_endpoint_or_other_domain(self):
        for extra in [{'user_id': 'someone'}, {'endpoint': 'http://other'}, {'knowledge_id': 'other'}, {'task_id': 'other'}]:
            with self.subTest(extra=extra), self.assertRaises(module.Rejected):
                self.request('context', **extra)
        with self.assertRaises(module.Rejected):
            self.request('read', page={'scope': 'wcs', 'ref': 'domains/wcs/specification.md'})
        with self.assertRaises(module.Rejected):
            self.request('read', page={'scope': 'putaway', 'ref': '../../secret'})

    def test_unapproved_book_and_contract_mismatch_rejected(self):
        self.gateway.assets['putaway']['status'] = 'candidate'
        with self.assertRaises(module.Rejected):
            self.request('context')
        with self.assertRaises(module.Rejected):
            self.request('context', contract='wcs_creation/4')

    def test_version_and_same_version_body_drift_rejected(self):
        self.gateway.versions['putaway'] = '3'
        with self.assertRaises(module.Rejected):
            self.request('context')
        self.gateway.versions['putaway'] = '2'
        self.gateway.pages['putaway']['domains/putaway/specification.md'] += 'changed'
        with self.assertRaises(module.Rejected):
            self.request('read', page={'scope': 'putaway', 'ref': 'domains/putaway/specification.md'})

    def test_forged_reference_cannot_verify(self):
        refs = [self.request('read', page=h)['reference'] for h in self.request('search', query='policy')['results']]
        refs[0]['source_commit'] = 'forged'
        with self.assertRaises(module.Rejected):
            self.request('verify', references=refs)

    def test_cross_team_resource_configuration_is_rejected(self):
        self.gateway.assets['putaway']['team_id'] = 'other-team'
        with self.assertRaises(module.Rejected):
            self.request('context')

    def test_planned_domain_is_read_only_without_contract(self):
        self.payload.update(hook_code='erp_mapping', contract='')
        result = self.request('context')
        self.assertFalse(result['catalog'][1]['generation_ready'])
        self.assertTrue(self.request('search', query='mapping')['results'])
        with self.assertRaises(module.Rejected):
            self.request('verify', references=[])
        with self.assertRaises(module.Rejected):
            self.request('context', contract='erp_mapping/1')

    def test_erp_contract_requires_explicit_approved_metadata(self):
        self.payload.update(hook_code='erp_mapping', contract='erp_mapping/1')
        with self.assertRaises(module.Rejected):
            self.request('context')
        asset = self.gateway.assets['erp']
        metadata = json.loads(asset['metadata_json'])
        metadata.update(approved=True, generation_ready=True, approved_contracts=['erp_mapping/1'])
        asset.update(status='approved', metadata_json=json.dumps(metadata))
        result = self.request('context')
        self.assertTrue(result['catalog'][1]['generation_ready'])
        self.assertEqual(result['catalog'][1]['approved_contracts'], ['erp_mapping/1'])

    def test_each_business_identity_uses_its_exact_task(self):
        for hook, task in module.TASK_NAMES.items():
            self.payload.update(hook_code=hook, contract='')
            self.assertEqual(self.request('identity')['task_name'], task)
        self.gateway.task_present = False
        with self.assertRaises(module.Rejected):
            self.request('identity')

    def test_all_users_share_business_tasks_and_keep_their_own_agents(self):
        shared = {}
        agents = set()
        for user in ['first', 'second', 'third']:
            self.gateway.user_id = user
            self.gateway.agent_id = 'agent-' + user
            for hook in module.TASK_NAMES:
                self.payload.update(hook_code=hook, contract='')
                identity = self.request('identity')
                self.assertEqual(identity['agent_id'], self.gateway.agent_id)
                self.assertEqual(identity['task_id'], shared.setdefault(hook, identity['task_id']))
                agents.add(identity['agent_id'])
        self.assertEqual(len(set(shared.values())), 5)
        self.assertEqual(len(agents), 3)

    def test_shared_task_rejects_duplicates_other_teams_and_stopped_tasks(self):
        self.gateway.duplicate_task = True
        with self.assertRaises(module.Rejected):
            self.request('identity')
        self.gateway.duplicate_task = False
        for overrides in [{'team_id': 'other'}, {'status': 'completed'}, {'title': '日常任务'}]:
            self.gateway.task_overrides = overrides
            with self.subTest(overrides=overrides), self.assertRaises(module.Rejected):
                self.request('identity')

    def test_shared_task_rejects_revoked_agent_link(self):
        self.gateway.task_link_active = False
        with self.assertRaises(module.Rejected):
            self.request('identity')

    def test_device_contract_requires_approved_device_wiki(self):
        self.payload.update(hook_code='device_protocol', contract='device_protocol/1')
        context = self.request('context')
        self.assertEqual(context['catalog'][1]['scope'], 'equipment')
        self.gateway.assets['equipment']['status'] = 'candidate'
        with self.assertRaises(module.Rejected):
            self.request('context')

    def test_query_and_reference_limits(self):
        for query in ['', 'x' * 257, None]:
            with self.subTest(query=query), self.assertRaises(module.Rejected):
                self.request('search', query=query)
        with self.assertRaises(module.Rejected):
            self.request('verify', references=[{}] * 13)
        for hook in [None, [], 'unknown']:
            with self.subTest(hook=hook), self.assertRaises(module.Rejected):
                self.request('context', hook_code=hook)


if __name__ == '__main__':
    unittest.main()
