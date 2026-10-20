"""ERP pure-data contract. Every database and HTTP effect stays in fixed services."""
import copy
import json
import re

from odoo.addons.blue_extension_contract.tools.json_policy import (
    MAX_BYTES, MAX_STEPS, ProtocolError, ProtocolInterpreter, bounded, validate_headers,
    validate_protocol,
)

CONTRACT = 'erp_mapping/1'
PHASES = ('receive', 'complete', 'inventory', 'response')


def text(value, label, optional=False):
    if type(value) is not str or len(value) > 256 or (not optional and not value.strip()):
        raise ProtocolError('Invalid %s.' % label)


def run_mapping(code, payload):
    tree = validate_protocol(code)
    try:
        bounded(payload)
        if len(json.dumps(payload, allow_nan=False).encode()) > MAX_BYTES:
            raise ProtocolError('ERP input exceeds 256 KiB.')
        if (type(payload) is not dict or set(payload) != {'request', 'candidates'}
                or type(payload['request']) is not dict or type(payload['candidates']) is not list):
            raise ProtocolError('Input requires request and candidates.')
        request = payload['request']
        if (set(request) != {'phase', 'kind', 'event_key', 'external_id', 'number', 'message', 'http_status', 'operation'}
                or request['phase'] not in PHASES
                or request['kind'] not in ('incoming', 'outgoing', 'internal', 'inventory')
                or type(request['message']) is not dict or type(request['http_status']) is not int):
            raise ProtocolError('Invalid ERP request schema.')
        for key in ('event_key', 'external_id', 'number', 'operation'):
            text(request[key], key, optional=True)
        for item in payload['candidates']:
            if type(item) is not dict:
                raise ProtocolError('Candidates must be JSON objects.')
        engine = ProtocolInterpreter(copy.deepcopy(payload))
        engine.statements(tree.body)
        result = engine.values.get('result')
        if type(result) is not dict:
            raise ProtocolError('Produce a result object.')
        if request['phase'] == 'receive':
            if set(result) != {'documents'} or type(result['documents']) is not list or not 1 <= len(result['documents']) <= 20:
                raise ProtocolError('Receive requires 1-20 documents.')
            document_ids = set()
            for document in result['documents']:
                if (type(document) is not dict or set(document) != {'external_id', 'number', 'partner_code', 'lines'}
                        or type(document['lines']) is not list or not 1 <= len(document['lines']) <= 200):
                    raise ProtocolError('Invalid document schema.')
                for key in ('external_id', 'number', 'partner_code'):
                    text(document[key], key, optional=key == 'partner_code')
                if document['external_id'] in document_ids:
                    raise ProtocolError('Repeated external document ID.')
                document_ids.add(document['external_id'])
                line_ids = set()
                for line in document['lines']:
                    if type(line) is not dict or set(line) != {'external_line_id', 'product_code', 'quantity', 'uom', 'lot', 'source_code', 'destination_code', 'group'}:
                        raise ProtocolError('Invalid ERP line schema.')
                    for key in set(line) - {'quantity'}:
                        text(line[key], key, optional=key in ('lot', 'source_code', 'destination_code', 'group'))
                    if type(line['quantity']) not in (int, float) or line['quantity'] <= 0:
                        raise ProtocolError('Demand quantity must be positive.')
                    if line['external_line_id'] in line_ids:
                        raise ProtocolError('Repeated external line ID.')
                    line_ids.add(line['external_line_id'])
        elif request['phase'] in ('complete', 'inventory'):
            if set(result) != {'actions'} or type(result['actions']) is not list or not 1 <= len(result['actions']) <= 10:
                raise ProtocolError('Return 1-10 ordered ERP actions.')
            for action in result['actions']:
                if (type(action) is not dict or set(action) not in ({'operation', 'body'}, {'operation', 'body', 'headers'})
                        or type(action['body']) is not dict):
                    raise ProtocolError('Actions require operation, body and optional headers.')
                if type(action['operation']) is not str or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', action['operation']):
                    raise ProtocolError('Use a configured operation code.')
                validate_headers(action.get('headers', {}))
                if any(name.lower() == 'idempotency-key' for name in action.get('headers', {})):
                    raise ProtocolError('The fixed service owns Idempotency-Key.')
                # Authentication is referenced locally and never passed through AI input.
                for value in action.get('headers', {}).values():
                    if ('$' in value and '$app_key' not in value and '$app_secret' not in value):
                        raise ProtocolError('Unknown credential reference.')
        else:
            if (set(result) != {'state', 'external_number'} or result['state'] not in ('accepted', 'rejected', 'unknown')):
                raise ProtocolError('Response requires state and external_number.')
            text(result['external_number'], 'external_number', optional=True)
        bounded(result)
        if len(json.dumps(result, allow_nan=False).encode()) > MAX_BYTES:
            raise ProtocolError('ERP output exceeds 256 KiB.')
        return result
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError) as error:
        if isinstance(error, ProtocolError):
            raise
        raise ProtocolError('ERP transformation failed validation.') from error


def mapping_schema():
    return {
        'contract': CONTRACT, 'hook_code': 'erp_mapping', 'schema_version': 1,
        'phases': list(PHASES),
        'input': {'request': {'phase': '|'.join(PHASES), 'kind': 'incoming|outgoing|internal|inventory',
            'event_key': 'stable WMS completion/count event ID; empty on receive',
            'external_id': 'ERP document ID or empty', 'number': 'external document number or count event number',
            'message': 'raw ERP object on receive/response, empty otherwise', 'http_status': 'integer; 0 outside response',
            'operation': 'configured operation code on response, empty otherwise'},
            'candidates': {'receive': 'raw rows from the configured top-level ERP array; single-level for candidate in candidates',
                'complete': 'actual completed rows: external_line_id, product_code, quantity, cumulative_quantity, acknowledged_quantity, planned_quantity, uom, lot, source_code, destination_code, package',
                'inventory': 'difference rows: product_code, uom, lot, location_code, package, owner_code, book_quantity, counted_quantity, difference_quantity',
                'response': 'same frozen rows as the outgoing event'}},
        'receive_candidates': 'Fixed adapter exposes message.lines as candidates; vendor arrays may be configured using inbound_lines_key (one top-level key).',
        'output': {
            'receive': {'documents': [{'external_id': 'stable text', 'number': 'text', 'partner_code': 'existing ref or empty',
                'lines': [{'external_line_id': 'stable text', 'product_code': 'existing unique default_code', 'quantity': 'positive number',
                           'uom': 'exact product stock unit name with lang=None (canonical, not translated)', 'lot': 'existing lot name or empty', 'source_code': 'allowed location barcode or empty',
                           'destination_code': 'allowed location barcode or empty', 'group': 'local picking group or empty'}]}]},
            'complete|inventory': {'actions': [{'operation': 'manually configured code', 'body': 'JSON object',
                'headers?': 'optional map; $app_key / $app_secret placeholders, no literal credentials'}]},
            'response': {'state': 'accepted|rejected|unknown', 'external_number': 'ERP returned number or empty'}},
        'syntax': 'bounded JSON assignments, if/else, for candidate in candidates, .get, .append, str/int/float/len; no ORM/import/network',
        'fixed_rules': ['company and warehouse scope', 'existing product and stock unit only', 'same external ID + same normalized content returns existing document',
            'changed external content is rejected for manual review', 'stock validation creates durable events without HTTP',
            'each partial picking reports only its actual quantity', 'unknown HTTP outcomes require reconciliation', 'ordered steps, completed steps never resent'],
        'limits': {'code_characters': 32768, 'input_bytes': MAX_BYTES, 'documents': 20, 'lines': 200, 'actions': 10, 'steps': MAX_STEPS},
    }
