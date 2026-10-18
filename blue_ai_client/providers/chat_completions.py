import hashlib
import json
import re
import uuid
from urllib.parse import urlsplit, urlunsplit

import requests

from odoo.exceptions import UserError

from odoo.addons.muk_ai.providers.base import PROVIDER_STATE_KEY, ProviderBase
from odoo.addons.muk_ai.providers.region import CUSTOM

from ..guard import HOOK_TASKS, TASK_NAME, TEAM_NAME
from .knowledge import NativeWiki


def normalize_url(value):
    """Accept a base URL or the complete Chat Completions endpoint."""
    parts = urlsplit((value or '').strip())
    host = parts.hostname
    if (not host or parts.username or parts.password or parts.query or parts.fragment
            or parts.scheme not in ('https', 'http')):
        raise ValueError('Invalid service URL')
    if parts.scheme == 'http' and host not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('HTTPS is required outside loopback development')
    path = parts.path.rstrip('/')
    if path.endswith('/chat/completions'):
        path = path[:-len('/chat/completions')]
    # CodeBuddy base URLs omit /v1; OpenAI-compatible bases normally include it.
    if re.search(r'/codebuddy/[^/]+$', path):
        path += '/v1'
    return urlunsplit((parts.scheme, parts.netloc, path, '', ''))


class BlueCloudProvider(ProviderBase):
    """Chat Completions wire adapter with deterministic proxy initialization."""

    name = 'blue_cloud'
    label = '宝蓝云端'
    default_model = 'glm-5.3-Flash'
    default_url = 'https://odooapi.royalblue56.com/codebuddy/default/v1'
    regions = (CUSTOM,)
    modalities = frozenset({'chat'})
    supports_vision = True

    @property
    def api_url(self):
        try:
            return normalize_url(super().api_url)
        except ValueError as error:
            raise UserError(self.env._('云端服务地址无效，请使用 HTTPS 地址。')) from error

    def _connection(self):
        return self.env['blue.ai.connection']._for_current_user()

    @property
    def _api_key(self):
        # Resolve exactly the current user's binding before reading its secret.
        return self._connection().sudo().api_key or ''

    def headers(self):
        sid = self.env.context.get('blue_ai_session_uuid') or str(uuid.uuid4())
        scope = self.identity_scope()
        sid = f'{sid}-{scope}'
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'session-id': sid,
            'x-conversation-id': sid,
        }

    def identity_scope(self):
        connection = self._connection()
        values = [str(self.env.uid), self.api_key, connection.agent_name or '',
                  self.env.context.get('blue_ai_task_name') or TASK_NAME,
                  str(self.env.company.id), self.env.context.get('blue_ai_contract') or '', 'native-wiki-v1']
        return hashlib.sha256('\0'.join(values).encode()).hexdigest()[:32]

    def _post(self, path, body, timeout, stream=False):
        """Do not follow credential-bearing redirects or echo upstream bodies."""
        if not self.provider.active:
            raise UserError(self.env._('请先在 MuK AI 设置中启用宝蓝云端服务。'))
        try:
            response = self._http_session().post(
                f'{self.api_url}{path}', headers={**self.headers(), **getattr(self, '_business_headers', {})}, json=body,
                timeout=(min(timeout, 15), timeout), stream=stream,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise UserError(self.env._('云端连接失败，请检查网络和服务地址。')) from error
        if not 200 <= response.status_code < 300:
            status = response.status_code
            response.close()
            raise UserError(self.env._('云端请求失败（HTTP %s）。请检查用户 Key 和代理配置。', status))
        return response

    def _raise(self, error):
        # Vendor responses can echo credentials and prompt data. Keep them private.
        raise UserError(self.env._('云端回复无效或连接中断，请检查服务日志。'))

    def request(self, inputs, tools_schema=None, text_schema=None, on_delta=None,
                model=None, enable_web_search=False, enable_code_interpreter=False,
                cache_key=None, reasoning_effort=None):
        connection = self._connection()
        if not connection.agent_name:
            raise UserError(self.env._('请在用户连接设置中填写云端 Agent 名称。'))
        # All HTTP calls of this request, including initialization, share an ID.
        self.provider = self.provider.with_context(
            blue_ai_session_uuid=self.env.context.get('blue_ai_session_uuid') or str(uuid.uuid4())
        )
        task_name = self.env.context.get('blue_ai_task_name') or TASK_NAME
        self._business_headers = {}
        hook = next((code for code, name in HOOK_TASKS.items() if name == task_name), None)
        if hook:
            identity = NativeWiki(self, hook, self.env.context.get('blue_ai_contract') or '').identity()
            if identity.get('task_name') != task_name or any(
                    not isinstance(identity.get(key), str) or not identity[key]
                    for key in ('team_id', 'agent_id', 'task_id')):
                raise UserError(self.env._('业务 Task 身份解析失败,不使用日常任务兜底.'))
            self._business_headers = {'x-team-id': identity['team_id'], 'x-agent-id': identity['agent_id'],
                                      'x-task-id': identity['task_id']}
            session = self.env['muk_ai.session'].search([
                ('blue_session_uuid', '=', self.env.context.get('blue_ai_session_uuid')),
                ('user_id', '=', self.env.uid), ('blue_hook_code', '=', hook),
            ], limit=1)
            if session:
                session._blue_pin_cloud_identity(identity)
        maximum = self.env.context.get('blue_ai_test_max_tokens') or self.provider.max_tokens or 16384
        body = {
            'model': self.model_for(model), 'messages': self._inputs_to_messages(inputs),
            'stream': True, 'stream_options': {'include_usage': True}, 'max_tokens': maximum,
        }
        tools = [
            {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': parameters}}
            for name, description, parameters in self._unique_tools(tools_schema)
        ]
        if tools:
            body['tools'] = tools
        if text_schema:
            body['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': text_schema.get('name', 'response'), 'schema': text_schema['schema'], 'strict': True,
            }}
        if reasoning_effort:
            body['reasoning_effort'] = reasoning_effort
        if enable_web_search or enable_code_interpreter:
            raise UserError(self.env._('此连接不提供模型内置搜索或代码执行，请使用已授权的业务工具。'))
        for _attempt in range(6):
            result, form = self._stream_chat(body, on_delta)
            if form is None:
                return result
            answer = self._answer_initialization(form, connection.agent_name)
            body['messages'].extend([
                {'role': 'assistant', 'content': None, 'tool_calls': [form]},
                {'role': 'tool', 'tool_call_id': form['id'], 'content': json.dumps(answer, ensure_ascii=False)},
            ])
        raise UserError(self.env._('云端身份初始化未完成，请检查团队、Agent 和任务配置。'))

    @classmethod
    def _inputs_to_messages(cls, inputs):
        messages = []
        for item in inputs or []:
            kind = item.get('type')
            role = item.get('role')
            if kind == 'function_call':
                if not messages or messages[-1]['role'] != 'assistant':
                    messages.append({'role': 'assistant', 'content': None})
                messages[-1].setdefault('tool_calls', []).append({
                    'id': item['call_id'], 'type': 'function', 'function': {
                        'name': item['name'], 'arguments': item.get('arguments') or '{}',
                    },
                })
            elif kind == 'function_call_output':
                output = item.get('output', '')
                messages.append({'role': 'tool', 'tool_call_id': item['call_id'],
                                 'content': output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)})
            elif role in ('system', 'developer', 'user', 'assistant'):
                content = cls._content_parts(item.get('content'))
                if all(part.get('type') == 'text' for part in content):
                    content = ''.join(part['text'] for part in content)
                message = {'role': role, 'content': content or (None if role == 'assistant' else '')}
                state = (item.get(PROVIDER_STATE_KEY) or {}).get(cls.name) or {}
                if role == 'assistant' and state.get('reasoning_content'):
                    message['reasoning_content'] = state['reasoning_content']
                messages.append(message)
        return messages

    @staticmethod
    def _text_part(text):
        return {'type': 'text', 'text': text}

    @classmethod
    def _attachment_part(cls, block):
        if block.get('strategy') == 'image':
            return {'type': 'image_url', 'image_url': {
                'url': f"data:{block.get('mimetype') or 'image/png'};base64,{block.get('data_b64') or ''}",
            }}
        return cls._text_part(cls._attachment_text(block))

    def _stream_chat(self, body, on_delta):
        text, reasoning, calls = [], [], {}
        usage, finished, form_stream = {}, False, False
        for event in self._post_stream('/chat/completions', body):
            if not isinstance(event, dict):
                self._raise('invalid event')
            if event.get('error'):
                self._raise('upstream error')
            form_stream = form_stream or str(event.get('id', '')).startswith('session-init-')
            if event.get('usage'):
                usage = event['usage']
            for choice in event.get('choices') or []:
                if choice.get('index', 0) != 0:
                    continue
                delta = choice.get('delta') or {}
                if delta.get('content'):
                    text.append(delta['content'])
                    if not form_stream:
                        self._call_on_delta(on_delta, 'text', {'delta': delta['content']})
                if delta.get('reasoning_content'):
                    reasoning.append(delta['reasoning_content'])
                    if not form_stream:
                        self._call_on_delta(on_delta, 'reasoning', {'delta': delta['reasoning_content']})
                for tool in delta.get('tool_calls') or []:
                    index = tool.get('index', 0)
                    entry = calls.setdefault(index, {'id': '', 'name': '', 'arguments': ''})
                    function = tool.get('function') or {}
                    if tool.get('id'):
                        entry['id'] = tool['id']
                    if function.get('name'):
                        entry['name'] += function['name']
                        if not form_stream:
                            self._call_on_delta(on_delta, 'tool_start', {'call_id': entry['id'], 'name': entry['name']})
                    if function.get('arguments'):
                        entry['arguments'] += function['arguments']
                        if not form_stream:
                            self._call_on_delta(on_delta, 'tool_args', {'call_id': entry['id'], 'delta': function['arguments']})
                if choice.get('finish_reason'):
                    finished = choice['finish_reason']
        if not finished:
            self._raise('unfinished stream')
        if form_stream:
            if len(calls) != 1 or text:
                self._raise('invalid initialization response')
            entry = next(iter(calls.values()))
            if entry['name'] != 'ask_followup_question' or not entry['id'].startswith('call_session_init_'):
                self._raise('unknown initialization tool')
            return None, {'id': entry['id'], 'type': 'function', 'function': {
                'name': entry['name'], 'arguments': entry['arguments'],
            }}
        if finished == 'content_filter':
            raise UserError(self.env._('云端模型拒绝了此次请求。'))
        if any(not entry['id'] or not entry['name'] for entry in calls.values()):
            self._raise('invalid tool call')
        if finished == 'length' and self.env.context.get('blue_ai_contract'):
            raise UserError(self.env._('代码生成回复达到输出上限,本轮未执行截断的工具调用.请提高模型 Max Tokens 后重试;已有草稿保留.'))
        tool_calls = [] if finished == 'length' else [
            self._tool_call(entry['id'], entry['name'], entry['arguments']) for entry in calls.values()
        ]
        carry = []
        if text or calls or reasoning:
            assistant = self._text_carry(''.join(text))
            if reasoning:
                assistant[PROVIDER_STATE_KEY] = {self.name: {'reasoning_content': ''.join(reasoning)}}
            carry.append(assistant)
        carry.extend(self._call_item(call) for call in tool_calls)
        result = self._result(
            ''.join(text), tool_calls, carry,
            self._usage(usage.get('prompt_tokens'), usage.get('completion_tokens'),
                        (usage.get('prompt_tokens_details') or {}).get('cached_tokens')),
            on_delta, finished == 'length', body.get('max_tokens'),
        )
        result['blue_finish_reason'] = finished
        return result, None

    def _answer_initialization(self, form, agent_name):
        try:
            args = json.loads(form['function']['arguments'])
            questions = args['questions']
            if isinstance(questions, str):
                questions = json.loads(questions)
            if not isinstance(questions, list) or not 1 <= len(questions) <= 3:
                raise ValueError('invalid questions')
            targets = {'asset_confirm': '是，关联团队资产', 'team': TEAM_NAME,
                       'agent': agent_name, 'task': self.env.context.get('blue_ai_task_name') or TASK_NAME}
            answers, answered = {}, []
            for question in questions:
                qid = question['id']
                if qid not in targets or question.get('multiSelect'):
                    raise ValueError('unknown question')
                options = question['options']
                if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
                    raise ValueError('invalid options')
                matches = [option for option in options
                           if option == targets[qid] or re.sub(r' \([^()]+\)$', '', option) == targets[qid]]
                if len(matches) != 1:
                    raise UserError(self.env._('云端初始化选项中找不到唯一匹配的 %s。请核对名称和用户权限。', targets[qid]))
                answers[qid] = matches[0]
                answered.append({**question, 'answer': matches[0]})
            return {'status': 'success', 'success': True, 'result': {
                'type': 'multi_question_result', 'questions': answered, 'answers': answers,
            }}
        except (ValueError, KeyError, TypeError) as error:
            raise UserError(self.env._('云端初始化表单格式不兼容，请检查代理版本。')) from error

    def test_connection(self):
        self.provider = self.provider.with_context(blue_ai_test_max_tokens=512)
        payload = self.request([{'role': 'user', 'content': '仅回复：连接正常。'}])
        if not payload['text'] or payload['tool_calls'] or payload['blue_finish_reason'] != 'stop':
            raise UserError(self.env._('云端测试未收到有效文本回复。'))
        return True
