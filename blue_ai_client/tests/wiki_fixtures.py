"""Small protocol fixtures for business workflow tests; never installed as data."""
import hashlib

from odoo.exceptions import UserError

from ..guard import HOOK_TASKS, REQUIRED_GUIDANCE


class FakeNativeWiki:
    def __init__(self, client, hook_code, contract='', pinned=None):
        self.client, self.hook_code, self.contract, self.pinned = client, hook_code, contract or '', pinned
        self.scope = {'putaway_policy': 'putaway', 'wcs_creation': 'wcs', 'erp_mapping': 'erp',
                      'device_protocol': 'equipment', 'barcode_policy': 'barcode'}[hook_code]
        self.catalog = [{'scope': s, 'wiki_id': 'wiki-' + s, 'wiki_version': '2', 'asset_version': 1,
                         'source_commit': 'approved-source', 'generation_ready': s in ['common', 'putaway', 'wcs'],
                         'approved_contracts': [self.contract] if s != 'common' and self.contract else []}
                        for s in ['common', self.scope]]

    def context(self):
        return self.pinned or {'source': 'tencent_wiki', 'hook_code': self.hook_code,
                               'contract': self.contract, 'catalog': self.catalog, 'pages': []}

    def identity(self):
        return {'team_id': 'test-team', 'agent_id': 'test-agent', 'task_id': 'task-' + self.scope,
                'task_name': HOOK_TASKS[self.hook_code]}

    def search(self, query):
        return [{'scope': scope, 'ref': ref, 'title': role, 'snippet': 'Search summary only.'}
                for scope, ref, role in [('common', 'basics/overview.md', 'guidance'),
                                        *[('common', ref, 'guidance') for ref in REQUIRED_GUIDANCE],
                                        (self.scope, 'domains/' + self.scope + '/specification.md', 'specification'),
                                        (self.scope, 'domains/' + self.scope + '/examples/approved.md', 'example')]]

    def read(self, page):
        role = 'guidance' if page['scope'] == 'common' else 'example' if '/examples/' in page['ref'] else 'specification'
        body = 'Approved full ' + role + ' body.'
        book = next(b for b in self.catalog if b['scope'] == page['scope'])
        return body, {**book, 'ref': page['ref'], 'sha256': hashlib.sha256(body.encode()).hexdigest(),
                      'role': role, 'contracts': [self.contract] if page['scope'] != 'common' else []}

    def verify(self):
        roles = {(p['scope'], p['role']) for p in (self.pinned or {}).get('pages', [])}
        pages = {(p['scope'], p['ref']) for p in (self.pinned or {}).get('pages', [])}
        if not {('common', ref) for ref in REQUIRED_GUIDANCE}.issubset(pages):
            raise UserError('Read workflow and requirements clarification before submitting.')
        if not {('common', 'guidance'), (self.scope, 'specification'), (self.scope, 'example')}.issubset(roles):
            raise UserError('Read full guidance, specification and example before submitting.')
