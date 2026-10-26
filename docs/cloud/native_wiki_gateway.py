"""Authenticated read-only forwarding to Tencent's native Wiki tools.

Run behind the existing HTTPS origin. Tenant, endpoints and logical Wiki IDs
are operator configuration; service credentials never enter Odoo or model prompts.
No indexing, example store, Skill operation or business write is implemented.
"""
import argparse
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOOKS = {
    'putaway_policy': ('putaway', ['putaway_policy/1', 'putaway_policy/2']),
    'wcs_creation': ('wcs', ['wcs_creation/4']),
    'erp_mapping': ('erp', ['erp_mapping/1']),
    'device_protocol': ('equipment', ['device_protocol/1']),
    'barcode_policy': ('barcode', ['barcode_policy/1']),
}
TASK_NAMES = {'putaway_policy': '上架策略', 'wcs_creation': 'WCS生成策略', 'erp_mapping': 'ERP接口',
              'device_protocol': '设备连接接口', 'barcode_policy': '条码扫描策略'}
MAX_BODY = 16384
MAX_RESPONSE = 524288
MAX_PAGE = 131072


class Rejected(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def digest(body):
    return hashlib.sha256(body.encode()).hexdigest()


def page_role(ref):
    if ref in ('basics/overview.md', 'basics/ai-generation-workflow.md'):
        return 'guidance'
    if ref.endswith(('/specification.md', '/configuration-guide.md')):
        return 'specification'
    if '/examples/' in ref and not ref.endswith('/README.md'):
        return 'example'
    return 'reference'


class NativeWikiGateway:
    def __init__(self, config):
        self.config = config

    def _post(self, endpoint, path, body, key, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Rejected('知识服务超时.', 504)
        headers = {'Content-Type': 'application/json', 'x-tdai-service-id': self.config['service_id'],
                   'x-tdai-user-key': key,
                   'Authorization': 'Bearer ' + Path(self.config['service_token_file']).read_text().strip()}
        request = urllib.request.Request(endpoint.rstrip('/') + path,
                                         json.dumps(body, ensure_ascii=False).encode(), headers)
        # Fixed loopback services must never redirect credential-bearing calls.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=min(8, remaining)) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise Rejected('知识响应过大.', 413)
                envelope = json.loads(raw)
                if envelope.get('code') != 0:
                    raise Rejected('知识服务拒绝当前请求.', 403)
                return envelope['data']
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
            raise Rejected('知识服务连接或身份校验失败.', 502) from error

    def _core(self, path, body, key, deadline):
        return self._post(self.config['core_url'], '/v3/meta/' + path, body, key, deadline)

    def _native(self, operation, wiki_id, params, key, deadline):
        return self._post(self.config['knowledge_url'], '/v3/tools/' + operation,
                          {'knowledge_id': wiki_id, **params}, key, deadline)

    def _identity(self, key, agent_name, deadline):
        if not key or len(key) > 512 or not isinstance(agent_name, str) or not 1 <= len(agent_name) <= 128:
            raise Rejected('缺少有效业务用户身份.', 401)
        auth = self._core('auth/verify', {'user_key': key}, key, deadline)
        user = auth.get('user')
        if auth.get('valid') is not True or not user:
            raise Rejected('业务用户身份无效.', 401)
        agents = self._core('agent/list', {'team_id': self.config['team_id'], 'name': agent_name,
                                         'limit': 100}, key, deadline)
        matches = [a for a in agents['items'] if a['name'] == agent_name
                   and a['owner_user_id'] == user['user_id'] and a['status'] == 'active'
                   and a['team_id'] == self.config['team_id']]
        if len(matches) != 1:
            raise Rejected('当前用户没有唯一匹配的项目 Agent.', 403)
        agent_id = matches[0]['agent_id']
        bindings = self._core('agent-fixed-asset/list-with-detail', {
            'agent_id': agent_id, 'asset_types': ['llm_wiki'],
            'apply_visibility_filter': True, 'touch_usage': False, 'limit': 100,
        }, key, deadline)
        if len(bindings['items']) < bindings.get('total', len(bindings['items'])):
            raise Rejected('知识绑定清单不完整.')
        return agent_id, user['user_id'], {r['asset_id']: r for r in bindings['items']}

    def _book(self, scope, bindings, agent_id, contract, key, deadline):
        wiki_id = self.config['wikis'][scope]
        asset = bindings.get(wiki_id)
        if not asset or asset.get('status') not in ('approved', 'candidate'):
            raise Rejected('当前 Agent 无可用知识绑定.', 403)
        acl = self._core('acl/check', {'user_key': key, 'agent_id': agent_id,
                                     'asset_id': wiki_id, 'action': 'read'}, key, deadline)
        if acl.get('allowed') is not True:
            raise Rejected('当前用户无权读取此知识库.', 403)
        asset = self._core('asset/get', {'asset_id': wiki_id}, key, deadline)
        if asset.get('team_id') != self.config['team_id']:
            raise Rejected('知识资产不属于当前项目团队.', 403)
        metadata = json.loads(asset.get('metadata_json') or '{}')
        if metadata.get('purpose') != 'odoo_runtime_code_generation' or metadata.get('scope') != scope:
            raise Rejected('知识库用途或领域不匹配.')
        ready = asset['status'] == 'approved' and metadata.get('approved') is True and metadata.get('generation_ready') is True
        if contract and (not ready or (scope != 'common' and contract not in metadata.get('approved_contracts', []))):
            raise Rejected('当前合同没有批准的知识正文.')
        tools = self._native('list', wiki_id, {}, key, deadline)
        if not {'get_info', 'search', 'read_page'}.issubset({t['name'] for t in tools['tools']}):
            raise Rejected('平台缺少必要的标准 Wiki 工具.')
        info = self._native('call', wiki_id, {'tool_name': 'get_info', 'params': {}}, key, deadline)
        if info['status'] != 'ready' or str(info['version']) != metadata.get('wiki_version'):
            raise Rejected('知识索引或批准版本已变化,请重新审阅发布.')
        files = metadata.get('approved_pages')
        if not isinstance(files, list) or not files:
            raise Rejected('知识库缺少审阅页清单.')
        summary = {'scope': scope, 'wiki_id': wiki_id, 'wiki_version': str(info['version']),
                   'asset_version': asset['version'], 'source_commit': metadata.get('source_commit'),
                   'generation_ready': ready, 'approved_contracts': metadata.get('approved_contracts', [])}
        return {'summary': summary, 'files': {f['ref']: f for f in files}}

    def _read(self, book, ref, contract, key, deadline):
        ref = ref.removeprefix('wiki/')
        entry = book['files'].get(ref)
        if not entry:
            raise Rejected('页面不在当前审阅清单中.', 403)
        summary = book['summary']
        result = self._native('call', summary['wiki_id'], {'tool_name': 'read_page', 'params': {'refs': [ref]}}, key, deadline)
        items = result.get('items')
        if not items or items[0].get('not_found') or not isinstance(items[0].get('content'), str):
            raise Rejected('知识页面不存在.')
        body = items[0]['content']
        if len(body.encode()) > MAX_PAGE or digest(body) != entry['page_sha256']:
            raise Rejected('知识正文过大或与批准摘要不一致.')
        header = re.search(r'^contracts: (.+)$', body[:4096], re.M)
        contracts = json.loads(header[1]) if header else []
        if contract and summary['scope'] != 'common' and contract not in contracts:
            raise Rejected('该页面不适用于当前合同.')
        info = self._native('call', summary['wiki_id'], {'tool_name': 'get_info', 'params': {}}, key, deadline)
        if info['status'] != 'ready' or str(info['version']) != summary['wiki_version']:
            raise Rejected('读页期间知识版本发生变化.')
        reference = {**summary, 'ref': ref, 'sha256': digest(body), 'contracts': contracts, 'role': page_role(ref)}
        return {'reference': reference, 'content': body}

    def handle(self, operation, payload, key):
        if operation not in ('identity', 'context', 'search', 'read', 'verify') or type(payload) is not dict:
            raise Rejected('不支持的知识操作.', 400)
        if set(payload) - {'agent_name', 'hook_code', 'contract', 'query', 'page', 'references'}:
            raise Rejected('不允许自选身份,地址或知识库.', 400)
        hook = payload.get('hook_code')
        if not isinstance(hook, str) or hook not in HOOKS:
            raise Rejected('未知业务入口.', 400)
        scope, contracts = HOOKS[hook]
        contract = payload.get('contract') or ''
        if not isinstance(contract, str) or (contract and contract not in contracts):
            raise Rejected('此业务合同尚未开放.')
        deadline = time.monotonic() + 25
        agent_id, _, bindings = self._identity(key, payload.get('agent_name'), deadline)
        if operation == 'identity':
            tasks = self._core('task/list', {'team_id': self.config['team_id'], 'status': 'running',
                                             'title': TASK_NAMES[hook], 'limit': 100}, key, deadline)
            matches = [t for t in tasks['items'] if t['title'] == TASK_NAMES[hook]
                       and t['status'] == 'running'
                       and t.get('team_id') == self.config['team_id']]
            if len(matches) != 1:
                raise Rejected('项目团队缺少唯一对应的共享业务 Task,请核对既有云端任务.')
            links = self._core('task-agent/list', {'task_id': matches[0]['task_id'], 'limit': 100}, key, deadline)
            if not any(link['agent_id'] == agent_id and link.get('status') == 'active' for link in links['items']):
                raise Rejected('业务 Task 尚未关联当前 Agent.', 403)
            return {'team_id': self.config['team_id'], 'agent_id': agent_id,
                    'task_id': matches[0]['task_id'], 'task_name': TASK_NAMES[hook]}
        books = {s: self._book(s, bindings, agent_id, contract, key, deadline) for s in ['common', scope]}
        catalog = [book['summary'] for book in books.values()]
        if operation == 'context':
            return {'source': 'tencent_wiki', 'hook_code': hook, 'contract': contract, 'catalog': catalog}
        if operation == 'search':
            query = payload.get('query')
            if not isinstance(query, str) or not 1 <= len(query.strip()) <= 256:
                raise Rejected('搜索词长度应为 1-256 字符.', 400)
            hits = []
            for s, book in books.items():
                result = self._native('call', book['summary']['wiki_id'], {
                    'tool_name': 'search', 'params': {'query': query, 'limit': 8}}, key, deadline)
                for hit in result.get('results', []):
                    ref = hit['path'].removeprefix('wiki/')
                    if ref in book['files']:
                        hits.append({'scope': s, 'ref': ref, 'title': hit['title'],
                                     'snippet': hit.get('snippet', '')[:512]})
            return {'catalog': catalog, 'results': hits}
        if operation == 'read':
            page = payload.get('page')
            if type(page) is not dict or page.get('scope') not in books or not isinstance(page.get('ref'), str):
                raise Rejected('页面不属于当前业务范围.', 403)
            return {'catalog': catalog, **self._read(books[page['scope']], page['ref'], contract, key, deadline)}
        references = payload.get('references')
        if not contract or not isinstance(references, list) or not 1 <= len(references) <= 12:
            raise Rejected('生成必须具备当前合同的真实知识引用.')
        seen, roles = set(), set()
        for old in references:
            if type(old) is not dict or old.get('scope') not in books:
                raise Rejected('知识引用越过业务范围.', 403)
            pair = (old['scope'], old.get('ref'))
            if pair in seen:
                raise Rejected('知识引用重复.')
            seen.add(pair)
            read = self._read(books[old['scope']], old['ref'], contract, key, deadline)
            if read['reference'] != old:
                raise Rejected('引用版本,批准状态或正文已变化,请重新打开会话.')
            roles.add((old['scope'], old['role']))
        if not {('common', 'guidance'), (scope, 'specification'), (scope, 'example')}.issubset(roles):
            raise Rejected('请先完整读取通用规则,本领域规范和至少一个匹配案例.')
        return {'valid': True, 'catalog': catalog}


def make_handler(gateway):
    slots = threading.BoundedSemaphore(16)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, data):
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self._send(200 if self.path == '/health' else 404, {'healthy': True} if self.path == '/health' else {})

        def do_POST(self):
            if not slots.acquire(blocking=False):
                self._send(503, {'code': 503, 'message': '知识服务繁忙.'})
                return
            try:
                self.connection.settimeout(30)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                    raise Rejected('请求体过大或格式不支持.', 413)
                if self.headers.get_content_type() != 'application/json':
                    raise Rejected('必须使用 JSON 请求.', 415)
                prefix = '/odoo-wiki/v1/'
                if not self.path.startswith(prefix):
                    raise Rejected('未知知识接口.', 404)
                authorization = self.headers.get('Authorization', '')
                key = authorization[7:] if authorization.startswith('Bearer ') else ''
                data = gateway.handle(self.path[len(prefix):], json.loads(self.rfile.read(length)), key)
                self._send(200, {'code': 0, 'data': data})
            except Rejected as error:
                self._send(error.status, {'code': error.status, 'message': str(error)})
            except Exception:
                # Never echo upstream bodies, bearer credentials or identities.
                self._send(502, {'code': 502, 'message': '知识请求失败,请检查服务与发布配置.'})
            finally:
                slots.release()
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--port', type=int, default=8430)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    for name in ('core_url', 'knowledge_url'):
        if not re.fullmatch(r'http://127\.0\.0\.1:\d+', config[name]):
            raise RuntimeError('Upstream services must be fixed loopback endpoints.')
    ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(NativeWikiGateway(config))).serve_forever()
