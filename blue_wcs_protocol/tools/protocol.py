"""Bounded JSON transformations; never evaluate Python or expose live objects."""
import ast
import copy
import json
import math
import operator


CONTRACT = 'device_protocol/1'
MAX_BYTES = 262144
MAX_ITEMS = 200
MAX_TEXT = 8192
MAX_STEPS = 30000
NODES = (
    ast.Module, ast.Assign, ast.Name, ast.Load, ast.Store, ast.Constant, ast.List,
    ast.Dict, ast.Subscript, ast.Slice, ast.For, ast.If, ast.Expr, ast.Call,
    ast.Attribute, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.BinOp, ast.IfExp,
    ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd, ast.Eq, ast.NotEq, ast.Lt,
    ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Add, ast.Sub, ast.Mult, ast.Div,
)


class ProtocolError(ValueError):
    pass


def bounded(value, depth=0, budget=None):
    if budget is None:
        budget = [MAX_BYTES, 32768]
    budget[0] -= 2
    budget[1] -= 1
    if budget[0] < 0 or budget[1] < 0:
        raise ProtocolError('JSON data exceeds the protocol resource budget.')
    if depth > 16:
        raise ProtocolError('JSON nesting exceeds 16 levels.')
    if type(value) is str:
        if len(value) > MAX_TEXT:
            raise ProtocolError('Text exceeds the supported length.')
        budget[0] -= len(value.encode())
    elif type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > 1e12:
            raise ProtocolError('Numbers must be finite and bounded.')
    elif type(value) in (list, dict):
        if len(value) > MAX_ITEMS:
            raise ProtocolError('Collections support at most 200 entries.')
        if type(value) is dict and any(type(key) is not str or len(key) > 256 for key in value):
            raise ProtocolError('JSON object keys must be bounded strings.')
        if type(value) is dict:
            budget[0] -= sum(len(key.encode()) + 3 for key in value)
        for item in (value.values() if type(value) is dict else value):
            bounded(item, depth + 1, budget)
    elif type(value) not in (bool, type(None)):
        raise ProtocolError('Only JSON values are supported.')
    if budget[0] < 0:
        raise ProtocolError('JSON data exceeds the protocol resource budget.')
    return value


def validate_protocol(code):
    if type(code) is not str or not code.strip() or len(code) > 32768:
        raise ProtocolError('Provide 1 to 32768 characters of protocol code.')
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError) as error:
        raise ProtocolError('Invalid protocol syntax.') from error
    nodes = list(ast.walk(tree))
    if len(nodes) > 2000:
        raise ProtocolError('Protocol code is too complex.')
    for node in nodes:
        if not isinstance(node, NODES):
            raise ProtocolError('Unsupported syntax: %s.' % type(node).__name__)
        if isinstance(node, ast.Name) and (node.id.startswith('_') or len(node.id) > 64):
            raise ProtocolError('Invalid variable name.')
        if isinstance(node, ast.Constant):
            bounded(node.value)
        if isinstance(node, ast.Assign):
            if (len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name)
                    or node.targets[0].id in ('request', 'candidates', 'candidate')):
                raise ProtocolError('Assign only to local variables; inputs are read-only.')
        if isinstance(node, ast.For):
            if (not isinstance(node.target, ast.Name) or node.target.id != 'candidate'
                    or not isinstance(node.iter, ast.Name) or node.iter.id != 'candidates' or node.orelse
                    or any(isinstance(child, ast.For) for statement in node.body for child in ast.walk(statement))):
                raise ProtocolError('Use only a single-level for candidate in candidates loop.')
        if isinstance(node, ast.Attribute) and node.attr not in ('get', 'append'):
            raise ProtocolError('Only JSON get and local-list append are available.')
        if isinstance(node, ast.Call):
            if node.keywords or len(node.args) > 2:
                raise ProtocolError('Unsupported call arguments.')
            if isinstance(node.func, ast.Name):
                if node.func.id not in ('str', 'float', 'int', 'len') or len(node.args) != 1:
                    raise ProtocolError('Only bounded scalar conversion and len are available.')
            elif not isinstance(node.func, ast.Attribute) or node.func.attr not in ('get', 'append'):
                raise ProtocolError('Unsupported call.')
        if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Call):
            raise ProtocolError('Standalone expressions are not supported.')
    return tree


class ProtocolInterpreter:
    def __init__(self, payload):
        self.values = payload
        self.steps = 0

    def expression(self, node):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise ProtocolError('Protocol execution budget exceeded.')
        if isinstance(node, ast.Constant):
            value = node.value
        elif isinstance(node, ast.Name):
            if node.id not in self.values:
                raise ProtocolError('Unknown protocol variable: %s.' % node.id)
            value = self.values[node.id]
        elif isinstance(node, ast.List):
            value = [self.expression(item) for item in node.elts]
        elif isinstance(node, ast.Dict):
            value = {}
            for key, item in zip(node.keys, node.values):
                if key is None:
                    raise ProtocolError('Dictionary expansion is not supported.')
                key = self.expression(key)
                if type(key) is not str or key in value:
                    raise ProtocolError('Object keys must be unique strings.')
                value[key] = self.expression(item)
        elif isinstance(node, ast.Subscript):
            data = self.expression(node.value)
            if isinstance(node.slice, ast.Slice):
                if type(data) not in (str, list):
                    raise ProtocolError('Slice only JSON text or arrays.')
                parts = [self.expression(part) if part is not None else None
                         for part in (node.slice.lower, node.slice.upper, node.slice.step)]
                if any(part is not None and type(part) is not int for part in parts) or parts[2] == 0:
                    raise ProtocolError('Slices require integer bounds.')
                value = data[slice(*parts)]
            else:
                key = self.expression(node.slice)
                if type(data) is dict and type(key) is str and key in data:
                    value = data[key]
                elif type(data) in (list, str) and type(key) is int and -len(data) <= key < len(data):
                    value = data[key]
                else:
                    raise ProtocolError('Unknown JSON field or array index.')
        elif isinstance(node, ast.Call):
            args = [self.expression(item) for item in node.args]
            if isinstance(node.func, ast.Name):
                original = args[0]
                if node.func.id == 'len':
                    if type(original) not in (str, list, dict):
                        raise ProtocolError('len requires JSON text or a collection.')
                    value = len(original)
                else:
                    if type(original) not in (str, int, float, bool):
                        raise ProtocolError('Convert only scalar values.')
                    try:
                        value = {'str': str, 'int': int, 'float': float}[node.func.id](original)
                    except (ValueError, OverflowError) as error:
                        raise ProtocolError('Invalid scalar conversion.') from error
            else:
                data = self.expression(node.func.value)
                if node.func.attr == 'get':
                    if type(data) is not dict or not 1 <= len(args) <= 2 or type(args[0]) is not str:
                        raise ProtocolError('get requires a JSON object and text key.')
                    value = data.get(*args)
                else:
                    if (not isinstance(node.func.value, ast.Name) or node.func.value.id in ('request', 'candidates', 'candidate')
                            or type(data) is not list or len(args) != 1 or len(data) >= MAX_ITEMS):
                        raise ProtocolError('Append only to a bounded local list.')
                    data.append(copy.deepcopy(args[0]))
                    bounded(data)
                    value = None
        elif isinstance(node, ast.IfExp):
            value = self.expression(node.body if self.expression(node.test) else node.orelse)
        elif isinstance(node, ast.BoolOp):
            for part in node.values:
                value = self.expression(part)
                if (isinstance(node.op, ast.And) and not value) or (isinstance(node.op, ast.Or) and value):
                    break
        elif isinstance(node, ast.UnaryOp):
            original = self.expression(node.operand)
            if isinstance(node.op, ast.Not):
                value = not original
            elif type(original) in (int, float):
                value = -original if isinstance(node.op, ast.USub) else original
            else:
                raise ProtocolError('Unary arithmetic requires numbers.')
        elif isinstance(node, ast.BinOp):
            left, right = self.expression(node.left), self.expression(node.right)
            if isinstance(node.op, ast.Add) and type(left) is type(right) and type(left) in (str, list):
                value = left + right
            elif type(left) in (int, float) and type(right) in (int, float):
                if isinstance(node.op, ast.Div) and right == 0:
                    raise ProtocolError('Division by zero.')
                value = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                         ast.Div: operator.truediv}[type(node.op)](left, right)
            else:
                raise ProtocolError('Unsupported arithmetic values.')
        elif isinstance(node, ast.Compare):
            left = self.expression(node.left)
            value = True
            for operation, item in zip(node.ops, node.comparators):
                right = self.expression(item)
                try:
                    value = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                             ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
                             ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}[type(operation)](left, right)
                except TypeError as error:
                    raise ProtocolError('Incompatible comparison values.') from error
                if not value:
                    break
                left = right
        else:
            raise ProtocolError('Unsupported expression.')
        return bounded(value)

    def statements(self, statements):
        for node in statements:
            self.steps += 1
            if self.steps > MAX_STEPS:
                raise ProtocolError('Protocol execution budget exceeded.')
            if isinstance(node, ast.Assign):
                self.values[node.targets[0].id] = copy.deepcopy(self.expression(node.value))
            elif isinstance(node, ast.If):
                self.statements(node.body if self.expression(node.test) else node.orelse)
            elif isinstance(node, ast.For):
                for candidate in self.values['candidates']:
                    self.values['candidate'] = candidate
                    self.statements(node.body)
            elif isinstance(node, ast.Expr):
                self.expression(node.value)
            else:
                raise ProtocolError('Unsupported statement.')


def run_protocol(code, payload):
    tree = validate_protocol(code)
    try:
        bounded(payload)
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(raw.encode()) > MAX_BYTES:
            raise ProtocolError('Protocol input exceeds 256 KiB.')
        payload = json.loads(raw)
        if (type(payload) is not dict or set(payload) != {'request', 'candidates'}
                or type(payload['request']) is not dict or type(payload['candidates']) is not list):
            raise ProtocolError('Input requires request and candidates.')
        request = payload['request']
        if set(request) != {'phase', 'task', 'message', 'http_status', 'parameters'} or request['phase'] not in ('request', 'response', 'callback'):
            raise ProtocolError('Choose request, response or callback with the complete input schema.')
        if (type(request['task']) is not dict or type(request['message']) is not dict
                or type(request['parameters']) is not dict or type(request['http_status']) is not int):
            raise ProtocolError('Task and message must be objects; HTTP status must be an integer.')
        engine = ProtocolInterpreter(payload)
        engine.statements(tree.body)
        result = engine.values.get('result')
        if type(result) is not dict:
            raise ProtocolError('Produce a result JSON object.')
        phase = request['phase']
        if phase == 'request':
            if set(result) != {'body'} or type(result['body']) is not dict:
                raise ProtocolError('Request result requires only a JSON body object; connection settings are manual.')
        elif phase == 'response':
            if set(result) != {'state', 'reason'} or result['state'] not in ('accepted', 'rejected', 'unknown'):
                raise ProtocolError('Response result needs state and reason.')
            if type(result['reason']) is not str or len(result['reason']) > 512:
                raise ProtocolError('Response reason must be bounded text.')
        else:
            if set(result) != {'task_id', 'event', 'point', 'subposition', 'destination_code', 'response'}:
                raise ProtocolError('Callback result requires task_id, event, point, subposition, destination_code and response.')
            if any(type(result[key]) is not str or len(result[key]) > 256 for key in ('task_id', 'event', 'point', 'subposition', 'destination_code')):
                raise ProtocolError('Callback event fields must be bounded text.')
            if result['task_id'] != request['task'].get('task_id') or result['event'] != 'end' or type(result['response']) is not dict:
                raise ProtocolError('Only completion of this exact task is supported.')
        bounded(result)
        if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_BYTES:
            raise ProtocolError('Protocol output exceeds 256 KiB.')
        return result
    except (TypeError, ValueError, RecursionError, OverflowError) as error:
        if isinstance(error, ProtocolError):
            raise
        raise ProtocolError('Invalid protocol JSON or expression.') from error


def protocol_schema():
    return {
        'contract': CONTRACT, 'hook_code': 'device_protocol', 'schema_version': 1,
        'phases': ['request', 'response', 'callback'],
        'input': {'request': {'phase': 'request|response|callback',
            'task': {'task_id': 'text', 'source': 'text', 'destination': 'text', 'template': 'text',
                     'carrier': 'text', 'device_code': 'text', 'role': 'goods|empty_supply|empty_return',
                     'operation': 'incoming|outgoing|internal'},
            'message': 'JSON response or one callback object; empty for request', 'http_status': 'integer',
            'parameters': 'administrator-approved non-secret vendor parameters'},
            'candidates': 'up to 200 goods objects: product_code, quantity, uom, lot'},
        'output': {'request': {'body': 'JSON object'},
            'response': {'state': 'accepted|rejected|unknown', 'reason': 'text <=512'},
            'callback': {'task_id': 'same task_id', 'event': 'end', 'point': 'reported point',
                'subposition': 'package subposition, or empty', 'destination_code': 'exact approved location code, or empty',
                'response': 'bounded vendor acknowledgement object'}},
        'syntax': 'JSON literals, local assignments, if/else, for candidate in candidates, .get, local .append, slices, str/int/float/len; no imports, eval, ORM, attributes or networking',
        'manual_settings': ['adapter_code', 'company', 'technician', 'IP', 'submit_path', 'credentials',
                            'callback_mode', 'allowed_destination_root', 'allowed_writebacks'],
        'limits': {'code_characters': 32768, 'input_bytes': MAX_BYTES, 'items': MAX_ITEMS, 'steps': MAX_STEPS},
    }
