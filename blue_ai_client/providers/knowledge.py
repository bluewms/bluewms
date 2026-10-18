"""Read native Tencent Wiki tools using the current business user's identity."""
import hashlib
import json
import time
from urllib.parse import urlsplit, urlunsplit

import requests

from odoo.exceptions import UserError


MAX_RESPONSE = 262144
MAX_PAGES = 12
MAX_TOTAL = 196608


class NativeWiki:
    def __init__(self, client, hook_code, contract='', pinned=None):
        self.client = client
        self.hook_code = hook_code
        self.contract = contract or ''
        self.pinned = pinned
        if pinned and (pinned.get('source') != 'tencent_wiki'
                       or pinned.get('hook_code') != hook_code or pinned.get('contract') != self.contract):
            raise UserError(client.env._('知识引用方式已升级,请从业务页面重新打开 AI 会话.'))

    def _post(self, operation, **values):
        parts = urlsplit(self.client.api_url)
        endpoint = urlunsplit((parts.scheme, parts.netloc, '/odoo-wiki/v1/' + operation, '', ''))
        body = {'hook_code': self.hook_code, 'contract': self.contract,
                'agent_name': self.client._connection().agent_name, **values}
        response = None
        deadline = time.monotonic() + 30
        try:
            response = self.client._http_session().post(
                endpoint, headers=self.client.headers(), json=body, timeout=(5, 28),
                stream=True, allow_redirects=False,
            )
            if not 200 <= response.status_code < 300:
                if operation == 'identity':
                    raise UserError(self.client.env._('无法确认当前业务 Task,请检查云端用户,Agent 和同名任务关联;不使用日常任务兜底.'))
                raise UserError(self.client.env._('Wiki 读取被拒绝,请检查用户权限,合同和知识批准版本;草稿未修改.'))
            chunks, size = [], 0
            for chunk in response.iter_content(8192):
                size += len(chunk)
                if size > MAX_RESPONSE or time.monotonic() > deadline:
                    raise UserError(self.client.env._('Wiki 响应过大或超时,请缩小检索范围.'))
                chunks.append(chunk)
            result = json.loads(b''.join(chunks))
            if type(result) is not dict or result.get('code') != 0 or type(result.get('data')) is not dict:
                raise ValueError('Invalid Wiki response')
            data = result['data']
            if operation == 'identity':
                return data
            catalog = data.get('catalog')
            if not isinstance(catalog, list) or len(catalog) != 2:
                raise ValueError('Invalid Wiki catalog')
            if self.pinned and catalog != self.pinned.get('catalog'):
                raise UserError(self.client.env._('云端知识版本或批准状态已改变,请重新打开 AI 会话.'))
            return data
        except (requests.RequestException, ValueError, KeyError, RecursionError) as error:
            raise UserError(self.client.env._('原生 Wiki 连接或正文校验失败,请检查知识服务.')) from error
        finally:
            if response is not None:
                response.close()

    def identity(self):
        return self._post('identity')

    def context(self):
        data = self._post('context')
        if (data.get('source') != 'tencent_wiki' or data.get('hook_code') != self.hook_code
                or data.get('contract') != self.contract):
            raise UserError(self.client.env._('知识范围与当前入口不一致.'))
        return self.pinned or {**data, 'pages': []}

    def search(self, query):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 256:
            raise UserError(self.client.env._('请输入 1-256 字符的知识检索词.'))
        data = self._post('search', query=query)
        if not isinstance(data.get('results'), list) or len(data['results']) > 16:
            raise UserError(self.client.env._('Wiki 搜索结果格式无效.'))
        return data['results']

    def read(self, page):
        data = self._post('read', page=page)
        body, reference = data.get('content'), data.get('reference')
        if (not isinstance(body, str) or type(reference) is not dict
                or reference.get('scope') != page['scope'] or reference.get('ref') != page['ref']
                or reference.get('sha256') != hashlib.sha256(body.encode()).hexdigest()):
            raise UserError(self.client.env._('Wiki 完整正文或来源摘要校验失败.'))
        return body, reference

    def verify(self):
        pages = (self.pinned or {}).get('pages')
        if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES:
            raise UserError(self.client.env._('请先搜索并完整读取通用规则,本领域规范及匹配案例.'))
        domains = [book['scope'] for book in self.pinned['catalog'] if book['scope'] != 'common']
        roles = {(page.get('scope'), page.get('role')) for page in pages}
        if len(domains) != 1 or not {('common', 'guidance'), (domains[0], 'specification'),
                                    (domains[0], 'example')}.issubset(roles):
            raise UserError(self.client.env._('请完整读取通用生成规则,本领域规范及至少一个匹配案例,再提交草稿.'))
        references = [{k: v for k, v in page.items() if k != 'bytes'} for page in pages]
        if self._post('verify', references=references).get('valid') is not True:
            raise UserError(self.client.env._('知识来源复核失败,草稿未修改.'))
