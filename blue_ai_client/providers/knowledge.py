"""Read approved project references through the proxy's session-scoped bridge.

The model cannot supply an endpoint, identity, skill ID, file path or command.
Search performs the proxy's current ACL check before each bundle is read.
Only references and digests are persisted locally, never a second example library.
"""

import hashlib
import json
import time
from urllib.parse import urlsplit, urlunsplit

import requests

from odoo.exceptions import UserError


SKILL_NAME = 'bluewms-policy-authoring'
RESOURCE_PATHS = (
    '01-project-and-governance.md',
    '03-policy-contract.md',
    '04-approved-putaway-examples.md',
)
WCS_RESOURCE_PATHS = ('01-project-and-governance.md', '06-wcs-creation-contract.md', '07-approved-wcs-examples.md')
SUPPORTED_CONTRACTS = {'putaway_policy': ('putaway_policy/1', 'putaway_policy/2'), 'wcs_creation': ('wcs_creation/4',)}

MAX_RESPONSE = 131072
MAX_BUNDLE = 32768


def read_policy_knowledge(client, pinned=None, hook_code="putaway_policy", contract=None):
    """Return a bounded approved Skill bundle and its reproducible references."""
    if hook_code not in SUPPORTED_CONTRACTS or (contract and contract not in SUPPORTED_CONTRACTS[hook_code]):
        raise UserError(client.env._('此业务合同尚未接入批准云端知识.'))
    contract = contract or SUPPORTED_CONTRACTS[hook_code][-1]
    resource_paths = WCS_RESOURCE_PATHS if hook_code == 'wcs_creation' else RESOURCE_PATHS
    if pinned and pinned.get('source') != 'tencent_skill_bridge':
        raise UserError(client.env._('知识引用方式已升级, 请从资产页面重新打开AI会话.'))
    deadline = time.monotonic() + 30
    parts = urlsplit(client.api_url)
    # This deployment exposes the bridge on the same configured HTTPS origin.
    base = urlunsplit((parts.scheme, parts.netloc, '/skill-bridge/v3/skill', '', ''))

    def fail():
        return UserError(client.env._('云端批准知识读取失败，请检查知识权限、版本及服务。当前草稿未修改。'))

    def post(operation, body):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise fail()
        response = None
        try:
            response = client._http_session().post(
                base + '/' + operation, headers=client.headers(), json=body,
                timeout=(min(5, remaining), min(10, remaining)), stream=True, allow_redirects=False,
            )
            if not 200 <= response.status_code < 300:
                raise fail()
            chunks, size = [], 0
            for chunk in response.iter_content(8192):
                size += len(chunk)
                if size > MAX_RESPONSE or time.monotonic() > deadline:
                    raise fail()
                chunks.append(chunk)
            envelope = json.loads(b''.join(chunks))
            if type(envelope) is not dict or envelope.get('code') != 0 or type(envelope.get('data')) is not dict:
                raise fail()
            return envelope['data']
        except (requests.RequestException, ValueError, RecursionError) as error:
            # Do not echo credential-bearing vendor errors or response bodies.
            raise fail() from error
        finally:
            if response is not None:
                response.close()

    found = post('search', {'query': SKILL_NAME})
    items = found.get('items')
    if type(items) is not list:
        raise fail()
    matches = [item for item in items if type(item) is dict and item.get('name') == SKILL_NAME]
    if len(matches) != 1 or not isinstance(matches[0].get('skill_id'), str):
        raise fail()
    skill_id = matches[0]['skill_id']
    version = pinned.get('version') if pinned else None
    if pinned and (pinned.get('skill_id') != skill_id or type(version) is not int):
        raise fail()
    body = {'skill_id': skill_id, 'include_content': True, 'include_manifest': True}
    if version:
        body['version'] = version
    skill = post('get', body)
    metadata = skill.get('metadata')
    if (skill.get('skill_id') != skill_id or skill.get('name') != SKILL_NAME
            or skill.get('status') != 'active' or type(metadata) is not dict
            or metadata.get('approved') is not True or metadata.get('purpose') != 'odoo_runtime_policy'
            or type(skill.get('version')) is not int or skill['version'] < 1
            or (version and skill['version'] != version)):
        raise fail()
    if hook_code == 'wcs_creation':
        approved = metadata.get('approved_contracts', {})
        allowed = approved.get(hook_code) if type(approved) is dict else None
        if type(allowed) is not list or contract not in allowed:
            raise UserError(client.env._('云端尚无当前WCS合同的批准知识. 请先完成既有Wiki/Skill发布, 当前草稿未修改.'))
        wiki_source = metadata.get('wiki_source')
        if (type(wiki_source) is not dict or type(wiki_source.get('wiki_id')) is not str or not wiki_source['wiki_id']
                or type(wiki_source.get('version')) is not int or wiki_source['version'] < 1):
            raise UserError(client.env._('云端WCS知识缺少有效Wiki来源ID或版本, 当前草稿未修改.'))
        if pinned and (pinned.get('hook_code') != hook_code or pinned.get('contract') != contract):
            raise fail()
    manifest = skill.get('manifest')
    if type(manifest) is not list:
        raise fail()
    paths = {entry.get('path') for entry in manifest if type(entry) is dict and not entry.get('is_executable')}
    if not set(resource_paths).issubset(paths) or type(skill.get('content')) is not str:
        raise fail()
    resources = []
    for path in resource_paths:
        data = post('files/read', {'skill_id': skill_id, 'version': skill['version'], 'path': path, 'encoding': 'utf-8'})
        if (data.get('path') != path or data.get('version') != skill['version']
                or data.get('encoding') != 'utf-8' or type(data.get('content')) is not str):
            raise fail()
        if hook_code == 'wcs_creation' and path != RESOURCE_PATHS[0]:
            marker = '<!-- bluewms-knowledge '
            first_line = data['content'].split('\n', 1)[0]
            try:
                header = json.loads(first_line[len(marker):-4]) if first_line.startswith(marker) and first_line.endswith(' -->') else {}
            except (ValueError, TypeError):
                raise fail()
            if (type(header) is not dict or type(header.get('contracts')) is not list
                    or header.get('hook_code') != hook_code or contract not in header['contracts'] or header.get('approved') is not True):
                raise fail()
        resources.append({'path': path, 'content': data['content'],
                          'sha256': hashlib.sha256(data['content'].encode()).hexdigest()})
    bundle = {'name': SKILL_NAME, 'skill_id': skill_id, 'version': skill['version'],
              'approved': True, 'content': skill['content'], 'resources': resources}
    if len(json.dumps(bundle, ensure_ascii=False).encode()) > MAX_BUNDLE:
        raise fail()
    references = {'name': SKILL_NAME, 'skill_id': skill_id, 'version': skill['version'],
                  'approved': True, 'source': 'tencent_skill_bridge',
                  'sha256': hashlib.sha256(skill['content'].encode()).hexdigest(),
                  'resources': [{k: v for k, v in item.items() if k != 'content'} for item in resources]}
    if hook_code == 'wcs_creation':
        references.update(hook_code=hook_code, contract=contract, wiki_source=wiki_source)
        bundle.update(hook_code=hook_code, contract=contract, wiki_source=wiki_source)
    if len(json.dumps(bundle, ensure_ascii=False).encode()) > MAX_BUNDLE:
        raise fail()
    if pinned and pinned != references:
        raise fail()
    return bundle, references
