"""Pure data barcode_policy/1; no Python evaluation, ORM or frontend access."""
import ast
import copy
import json

from odoo.addons.blue_extension_contract.tools.json_policy import (
    MAX_BYTES, ProtocolError, ProtocolInterpreter, bounded, validate_protocol,
)

CONTRACT = 'barcode_policy/1'
PARSED_KEYS = {'kind', 'code', 'quantity', 'lot', 'location', 'package', 'uom', 'reason'}


def between(raw, separator, start, end):
    """Return text between 1-based delimiter occurrences, keeping empty fields."""
    if (type(raw) is not str or len(raw) > 8192 or type(separator) is not str
            or not 1 <= len(separator) <= 16 or type(start) is not int or type(end) is not int
            or not 1 <= start < end <= 64):
        raise ProtocolError('between requires bounded text and delimiter occurrences 1 <= start < end <= 64.')
    positions, offset = [], 0
    for occurrence in range(end):
        position = raw.find(separator, offset)
        if position < 0:
            raise ProtocolError('Required barcode delimiter is missing.')
        positions.append(position)
        offset = position + len(separator)
    return raw[positions[start - 1] + len(separator):positions[end - 1]]


def validate_code(code):
    return validate_protocol(code, extra_calls={'between': 4})


class BarcodeInterpreter(ProtocolInterpreter):
    def expression(self, node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'between':
            self.steps += 1
            return bounded(between(*(self.expression(arg) for arg in node.args)))
        return super().expression(node)


def run_barcode(code, payload):
    tree = validate_code(code)
    try:
        bounded(payload)
        if (len(json.dumps(payload, allow_nan=False).encode()) > MAX_BYTES
                or type(payload) is not dict or set(payload) != {'request', 'candidates'}
                or type(payload['request']) is not dict or type(payload['candidates']) is not list):
            raise ProtocolError('Input requires bounded request and candidates.')
        request = payload['request']
        if (set(request) != {'phase', 'raw', 'context', 'parsed'} or request['phase'] not in ('parse', 'decide')
                or type(request['raw']) is not str or not 1 <= len(request['raw']) <= 8192
                or type(request['context']) is not dict or type(request['parsed']) is not dict):
            raise ProtocolError('Invalid barcode request schema.')
        candidate_keys = [row.get('key') if type(row) is dict else None for row in payload['candidates']]
        if any(type(key) is not str or not key or len(key) > 128 for key in candidate_keys) or len(set(candidate_keys)) != len(candidate_keys):
            raise ProtocolError('Candidates require unique bounded row keys.')
        engine = BarcodeInterpreter(copy.deepcopy(payload))
        engine.statements(tree.body)
        result = engine.values.get('result')
        bounded(result)
        if type(result) is not dict:
            raise ProtocolError('Produce a barcode result object.')
        if request['phase'] == 'parse':
            if (set(result) != PARSED_KEYS or result['kind'] not in ('product', 'location', 'lot', 'package')
                    or type(result['quantity']) not in (int, float) or not 0 < result['quantity'] <= 1e9):
                raise ProtocolError('Parse requires kind, code, positive quantity, lot, location, package, uom and reason.')
            for key in PARSED_KEYS - {'quantity'}:
                if type(result[key]) is not str or len(result[key]) > 512:
                    raise ProtocolError('Parsed fields must be text of at most 512 characters.')
            if not result['code']:
                raise ProtocolError('Parsed code cannot be empty.')
        else:
            if (set(result) not in ({'action', 'keys', 'reason'}, {'action', 'keys', 'reason', 'after'})
                    or result['action'] not in ('count', 'prompt', 'select')
                    or type(result['keys']) is not list or type(result['reason']) is not str
                    or len(result['reason']) > 512):
                raise ProtocolError('Decide requires count/prompt/select, keys and reason.')
            approved = [row['key'] for row in payload['candidates']]
            if any(type(key) is not str or key not in approved for key in result['keys']) or len(set(result['keys'])) != len(result['keys']):
                raise ProtocolError('Select only unique approved candidate keys.')
            if ((result['action'] == 'count' and len(result['keys']) != 1)
                    or (result['action'] in ('prompt', 'select') and result['keys'])):
                raise ProtocolError('Count selects exactly one row; prompt selects none.')
            if result.get('after', '') not in ('', 'next_group', 'wcs', 'validate', 'pack'):
                raise ProtocolError('Unsupported registered follow-up action.')
        return result
    except (TypeError, KeyError, ValueError, OverflowError, RecursionError) as error:
        if isinstance(error, ProtocolError):
            raise
        raise ProtocolError('Barcode transformation failed validation.') from error


def schema():
    return {'contract': CONTRACT, 'hook_code': 'barcode_policy', 'schema_version': 1,
        'phases': ['parse', 'decide'], 'input': {'request': {
            'phase': 'parse|decide', 'raw': 'complete barcode, 1-8192 characters',
            'context': 'fixed company/document/session context',
            'parsed': 'empty on parse, validated parsed fields on decide'},
            'candidates': 'empty on parse; at most 200 authorized row objects with unique key on decide'},
        'output': {'parse': {key: 'positive increment' if key == 'quantity' else 'text' for key in sorted(PARSED_KEYS)},
            'decide': {'action': 'count|prompt|select', 'keys': 'exactly one approved key for count; otherwise empty',
                'reason': 'text', 'after': 'optional: empty|next_group|wcs|validate|pack; fixed service rechecks authorization'}},
        'helpers': {'between(raw, separator, start, end)': 'between 1-based delimiter occurrences; empty segments preserved'},
        'execution': 'Pure JSON only. No ORM, imports, eval, network, arbitrary JS or frontend commands. Fixed services execute approved actions.'}
