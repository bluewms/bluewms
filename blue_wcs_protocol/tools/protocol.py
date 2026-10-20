"""Device contract over the shared bounded JSON interpreter."""
import json

from odoo.addons.blue_extension_contract.tools.json_policy import (
    MAX_BYTES, MAX_ITEMS, MAX_STEPS, ProtocolError, ProtocolInterpreter, bounded,
    validate_headers, validate_protocol,
)

CONTRACT = 'device_protocol/1'


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
        task = request['task']
        task_keys = {'task_id', 'source', 'destination', 'template', 'carrier', 'device_code', 'role', 'operation'}
        if set(task) != task_keys or any(type(value) is not str or len(value) > 256 for value in task.values()):
            raise ProtocolError('Task fields must match the installed contract exactly.')
        if (not task['task_id'] or task['role'] not in ('goods', 'empty_supply', 'empty_return')
                or task['operation'] not in ('incoming', 'outgoing', 'internal')):
            raise ProtocolError('Invalid task identity, role or operation.')
        for item in payload['candidates']:
            if (type(item) is not dict or set(item) != {'product_code', 'quantity', 'uom', 'lot'}
                    or any(type(item[key]) is not str or len(item[key]) > 256 for key in ('product_code', 'uom', 'lot'))
                    or type(item['quantity']) not in (int, float) or item['quantity'] < 0):
                raise ProtocolError('Goods fields must match the installed contract exactly.')
        engine = ProtocolInterpreter(payload)
        engine.statements(tree.body)
        result = engine.values.get('result')
        if type(result) is not dict:
            raise ProtocolError('Produce a result JSON object.')
        phase = request['phase']
        if phase == 'request':
            if set(result) not in ({'body'}, {'body', 'headers'}) or type(result['body']) is not dict:
                raise ProtocolError('Request result requires body and optional credential-reference headers.')
            validate_headers(result.get('headers', {}))
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
        'contract': CONTRACT, 'hook_code': 'device_protocol', 'schema_version': 2,
        'phases': ['request', 'response', 'callback'],
        'input': {'request': {'phase': 'request|response|callback',
            'task': {'task_id': 'text', 'source': 'text', 'destination': 'text', 'template': 'text',
                     'carrier': 'text', 'device_code': 'text', 'role': 'goods|empty_supply|empty_return',
                     'operation': 'incoming|outgoing|internal'},
            'message': 'JSON response or one callback object; empty for request', 'http_status': 'integer',
            'parameters': 'non-secret legacy parameters; new vendor constants belong in code'},
            'candidates': 'up to 200 goods objects: product_code, quantity, uom, lot'},
        'output': {'request': {'body': 'JSON object',
                'headers?': 'optional text map; $app_key / $app_secret are resolved locally, omitted when blank; default Bearer uses the category Token'},
            'response': {'state': 'accepted|rejected|unknown', 'reason': 'text <=512'},
            'callback': {'task_id': 'same task_id', 'event': 'end', 'point': 'reported point',
                'subposition': 'package subposition, or empty', 'destination_code': 'exact same-company, current-warehouse internal location barcode or AGV code, or empty',
                'response': 'bounded vendor acknowledgement object'}},
        'syntax': 'JSON literals, local assignments, if/else, for candidate in candidates, .get, local .append, slices, str/int/float/len; no imports, eval, ORM, attributes or networking',
        'manual_settings': ['company', 'technician', 'IP', 'submit_path', 'credentials'],
        'callback_lookup': 'one exact existing task ID in the JSON values; pinned code maps task_id and completion',
        'writebacks': 'published code chooses subposition and/or destination_code; fixed service validates final step, warehouse, company, stock and capacity',
        'limits': {'code_characters': 32768, 'input_bytes': MAX_BYTES, 'items': MAX_ITEMS, 'steps': MAX_STEPS},
    }
