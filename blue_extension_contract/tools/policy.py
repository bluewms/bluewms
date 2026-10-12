"""Interpret a bounded Python subset without compiling or evaluating Python code.

Only JSON data enters this interpreter. There are no Python object attributes,
ORM records, builtins, imports, functions, network or filesystem capabilities.
"""

import ast
import json
import math
import operator


MAX_CANDIDATES = 200
MAX_CODE = 32768
MAX_STEPS = 30000
CONTRACT = 'putaway_policy/1'


class PolicyError(ValueError):
    pass


ALLOWED_NODES = (
    ast.Module, ast.Assign, ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.List, ast.Dict, ast.Subscript, ast.For, ast.If, ast.Expr,
    ast.Call, ast.Attribute, ast.Compare, ast.BoolOp, ast.UnaryOp,
    ast.BinOp, ast.IfExp, ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Add, ast.Sub, ast.Mult, ast.Div,
)


def validate_code(code):
    if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE:
        raise PolicyError('Code must contain 1 to 32768 characters.')
    try:
        tree = ast.parse(code)
    except (SyntaxError, RecursionError, ValueError) as error:
        raise PolicyError('Invalid syntax.') from error
    nodes = list(ast.walk(tree))
    if len(nodes) > 2000:
        raise PolicyError('Code is too complex.')
    for node in nodes:
        if not isinstance(node, ALLOWED_NODES):
            raise PolicyError('Unsupported syntax: %s.' % type(node).__name__)
        if isinstance(node, ast.Name) and (node.id.startswith('_') or len(node.id) > 64):
            raise PolicyError('Invalid variable name.')
        if isinstance(node, ast.Constant):
            value = node.value
            if type(value) not in (str, int, float, bool, type(None)):
                raise PolicyError('Only JSON constants are allowed.')
            if isinstance(value, str) and len(value) > 512:
                raise PolicyError('Text constants are limited to 512 characters.')
            if type(value) in (int, float) and (not math.isfinite(value) or abs(value) > 1e9):
                raise PolicyError('Number is out of range.')
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise PolicyError('Assign only to a single variable.')
            if node.targets[0].id in ('request', 'candidates', 'candidate'):
                raise PolicyError('Input variables are read-only.')
        if isinstance(node, ast.For):
            if (not isinstance(node.target, ast.Name) or node.target.id != 'candidate'
                    or not isinstance(node.iter, ast.Name) or node.iter.id != 'candidates' or node.orelse):
                raise PolicyError('Use only: for candidate in candidates.')
            if any(isinstance(child, ast.For) for statement in node.body for child in ast.walk(statement)):
                raise PolicyError('Nested loops are not supported.')
        if isinstance(node, ast.Call):
            if (not isinstance(node.func, ast.Attribute) or node.func.attr != 'append'
                    or not isinstance(node.func.value, ast.Name) or node.func.value.id != 'result'
                    or len(node.args) != 1 or node.keywords):
                raise PolicyError('Only result.append({...}) is allowed.')
        if isinstance(node, ast.Attribute) and (node.attr != 'append' or not isinstance(node.value, ast.Name) or node.value.id != 'result'):
            raise PolicyError('Object attributes are not supported.')
        if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Call):
            raise PolicyError('Only append calls are allowed as expression statements.')
    return tree


class Interpreter:
    def __init__(self, payload):
        self.variables = {'request': payload['request'], 'candidates': payload['candidates']}
        self.steps = 0

    def _tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise PolicyError('Policy execution budget exceeded.')

    def _number(self, value):
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e12:
            raise PolicyError('Arithmetic requires finite bounded numbers.')
        return value

    def expression(self, node):
        self._tick()
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in self.variables:
                raise PolicyError('Unknown variable: %s.' % node.id)
            return self.variables[node.id]
        if isinstance(node, ast.List):
            return [self.expression(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            result = {}
            for key, value in zip(node.keys, node.values):
                if key is None:
                    raise PolicyError('Dictionary expansion is not allowed.')
                key = self.expression(key)
                if type(key) is not str or key in result:
                    raise PolicyError('Dictionary keys must be unique strings.')
                result[key] = self.expression(value)
            return result
        if isinstance(node, ast.Subscript):
            data, key = self.expression(node.value), self.expression(node.slice)
            if type(data) is not dict or type(key) is not str or key not in data:
                raise PolicyError('Only existing JSON dictionary keys can be read.')
            return data[key]
        if isinstance(node, ast.IfExp):
            return self.expression(node.body if self.expression(node.test) else node.orelse)
        if isinstance(node, ast.UnaryOp):
            value = self.expression(node.operand)
            if isinstance(node.op, ast.Not):
                return not value
            return -self._number(value) if isinstance(node.op, ast.USub) else self._number(value)
        if isinstance(node, ast.BinOp):
            left, right = self._number(self.expression(node.left)), self._number(self.expression(node.right))
            function = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}[type(node.op)]
            if isinstance(node.op, ast.Div) and right == 0:
                raise PolicyError('Division by zero.')
            return self._number(function(left, right))
        if isinstance(node, ast.BoolOp):
            for item in node.values:
                value = self.expression(item)
                if isinstance(node.op, ast.And) and not value:
                    return value
                if isinstance(node.op, ast.Or) and value:
                    return value
            return value
        if isinstance(node, ast.Compare):
            left = self.expression(node.left)
            functions = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                         ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
                         ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
            for operation, right_node in zip(node.ops, node.comparators):
                right = self.expression(right_node)
                try:
                    valid = functions[type(operation)](left, right)
                except TypeError as error:
                    raise PolicyError('Incompatible comparison values.') from error
                if not valid:
                    return False
                left = right
            return True
        raise PolicyError('Unsupported expression.')

    def statements(self, statements):
        for node in statements:
            self._tick()
            if isinstance(node, ast.Assign):
                self.variables[node.targets[0].id] = self.expression(node.value)
            elif isinstance(node, ast.If):
                self.statements(node.body if self.expression(node.test) else node.orelse)
            elif isinstance(node, ast.For):
                for candidate in self.variables['candidates']:
                    self.variables['candidate'] = candidate
                    self.statements(node.body)
            elif isinstance(node, ast.Expr):
                result = self.variables.get('result')
                if type(result) is not list or len(result) >= MAX_CANDIDATES:
                    raise PolicyError('Result must be a list of at most 200 entries.')
                value = self.expression(node.value.args[0])
                # Do not allow aliased input lists or recursively aliased result trees.
                if type(value) is not dict or set(value) != {'location_id', 'score', 'reason'}:
                    raise PolicyError('Each result needs location_id, score and reason.')
                if type(value['location_id']) is not int or type(value['score']) not in (int, float) or type(value['reason']) is not str:
                    raise PolicyError('Invalid result value types.')
                result.append(dict(value))
            else:
                raise PolicyError('Unsupported statement.')


def run_policy(code, payload):
    tree = validate_code(code)
    try:
        encoded = json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise PolicyError('Input must be finite JSON data.') from error
    if len(encoded) > 262144:
        raise PolicyError('Input exceeds 256KB.')
    payload = json.loads(encoded)
    if type(payload) is not dict or set(payload) != {'request', 'candidates'} or type(payload['request']) is not dict or type(payload['candidates']) is not list:
        raise PolicyError('Input needs request and candidates.')
    candidates = payload['candidates']
    if len(candidates) > MAX_CANDIDATES or any(type(item) is not dict or type(item.get('location_id')) is not int for item in candidates):
        raise PolicyError('Input supports at most 200 candidate locations.')
    allowed_ids = [item['location_id'] for item in candidates]
    if len(set(allowed_ids)) != len(allowed_ids):
        raise PolicyError('Duplicate candidate location.')
    interpreter = Interpreter(payload)
    try:
        interpreter.statements(tree.body)
    except RecursionError as error:
        raise PolicyError('Policy nesting is too deep.') from error
    result = interpreter.variables.get('result')
    if type(result) is not list or len(result) > MAX_CANDIDATES:
        raise PolicyError('Code must produce a result list.')
    seen = set()
    for item in result:
        if type(item) is not dict or set(item) != {'location_id', 'score', 'reason'}:
            raise PolicyError('Invalid result schema.')
        location_id, score, reason = item['location_id'], item['score'], item['reason']
        if type(location_id) is not int or location_id not in allowed_ids or location_id in seen:
            raise PolicyError('Result must use unique approved candidate IDs.')
        if type(score) not in (int, float) or not math.isfinite(score) or abs(score) > 100000:
            raise PolicyError('Score must be a bounded finite number.')
        if type(reason) is not str or len(reason) > 512:
            raise PolicyError('Reason must be text of at most 512 characters.')
        seen.add(location_id)
    return sorted(result, key=lambda item: (item['score'], item['location_id']))
