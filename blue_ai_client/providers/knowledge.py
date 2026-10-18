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
MAX_RESPONSE = 131072
MAX_BUNDLE = 32768


def read_policy_knowledge(client, pinned=None):
    """Return a bounded approved Skill bundle and its reproducible references."""
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
    manifest = skill.get('manifest')
    if type(manifest) is not list:
        raise fail()
    paths = {entry.get('path') for entry in manifest if type(entry) is dict and not entry.get('is_executable')}
    if not set(RESOURCE_PATHS).issubset(paths) or type(skill.get('content')) is not str:
        raise fail()
    resources = []
    for path in RESOURCE_PATHS:
        data = post('files/read', {'skill_id': skill_id, 'version': skill['version'], 'path': path, 'encoding': 'utf-8'})
        if (data.get('path') != path or data.get('version') != skill['version']
                or data.get('encoding') != 'utf-8' or type(data.get('content')) is not str):
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
    if pinned and pinned != references:
        raise fail()
    return bundle, references
