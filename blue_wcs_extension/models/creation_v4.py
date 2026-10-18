"""Versioned line decisions and bounded device-program orchestration, with no Python eval."""
import json
import math

from odoo.addons.blue_extension_contract.tools.policy import Interpreter, PolicyError, validate_code


REFS = ('line_source', 'line_destination', 'picking_source', 'picking_destination', 'handoff', 'source_parent', 'destination_parent')
DECISION_KEYS = {'line_id', 'action', 'quantity_basis', 'quantity', 'group_key', 'source_ref', 'destination_ref', 'reason'}
TASK_KEYS_V4 = {'equipment_id', 'location_res_id', 'location_dest_id', 'source_ref', 'destination_ref',
                'role', 'task_type', 'movement', 'dependency_step', 'dependency_event', 'dependency_point', 'reason'}
BASIC_V4_CODE = '''if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        result.append({"line_id": candidate["line_id"], "action": "create", "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": candidate["available_quantity"], "group_key": candidate["line_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": "基础逐行直达"})
else:
    result = [request["base_task"]]
'''


class OrchestrationInterpreter(Interpreter):
    def append_result(self, result, value):
        if type(value) is not dict:
            raise PolicyError('Append a JSON decision or task object.')
        result.append(dict(value))


def run_creation_v4(code, payload):
    tree = validate_code(code)
    try:
        encoded = json.dumps(payload, allow_nan=False)
        if len(encoded) > 262144:
            raise PolicyError('WCS input exceeds 256KB.')
        payload = json.loads(encoded)
    except (ValueError, TypeError, RecursionError) as error:
        raise PolicyError('WCS input must be finite JSON.') from error
    if (type(payload) is not dict or set(payload) != {'request', 'candidates'}
            or type(payload['request']) is not dict or type(payload['candidates']) is not list
            or len(payload['candidates']) > 200):
        raise PolicyError('WCS input requires request and at most 200 candidates.')
    request = payload['request']
    if request.get('phase') not in ('lines', 'tasks'):
        raise PolicyError('WCS /4 phase must be lines or tasks.')
    interpreter = OrchestrationInterpreter(payload)
    try:
        interpreter.statements(tree.body)
    except RecursionError as error:
        raise PolicyError('WCS nesting is too deep.') from error
    result = interpreter.variables.get('result')
    if type(result) is not list or len(result) > (200 if request['phase'] == 'lines' else 4):
        raise PolicyError('Return a bounded list: 200 line decisions or four device tasks.')
    if request['phase'] == 'lines':
        if any(type(item) is not dict or type(item.get('line_id')) is not int
               or type(item.get('available_quantity')) not in (int, float)
               or not math.isfinite(item['available_quantity']) or item['available_quantity'] < 0 for item in payload['candidates']):
            raise PolicyError('Line candidates need an integer identity and finite uncovered quantity.')
        candidates = {item['line_id']: item for item in payload['candidates']}
        if len(candidates) != len(payload['candidates']):
            raise PolicyError('Input line identities must be unique.')
        seen = set()
        for decision in result:
            if type(decision) is not dict or set(decision) != DECISION_KEYS:
                raise PolicyError('Each line needs identity, action, quantity basis/amount, group, endpoint references and reason.')
            line_id = decision['line_id']
            if type(line_id) is not int or line_id not in candidates or line_id in seen:
                raise PolicyError('Decide each input line exactly once.')
            seen.add(line_id)
            if (decision['action'] not in ('create', 'wait', 'exclude') or decision['quantity_basis'] not in ('confirmed', 'reserved')
                    or decision['source_ref'] not in REFS or decision['destination_ref'] not in REFS):
                raise PolicyError('Invalid line decision values.')
            if any(type(decision[key]) is not str or not decision[key] or len(decision[key]) > 512 for key in ('reason', 'group_key')):
                raise PolicyError('Decisions require bounded nonempty group and reason.')
            quantity = decision['quantity']
            if type(quantity) not in (int, float) or not math.isfinite(quantity) or quantity < 0 or quantity > candidates[line_id]['available_quantity']:
                raise PolicyError('Decision quantity must be within the uncovered line amount.')
            if decision['action'] != 'create' and quantity != 0:
                raise PolicyError('Wait/exclude decisions must have zero WCS quantity.')
            if request.get('operation') == 'incoming' and decision['action'] == 'create' and decision['quantity_basis'] != 'confirmed':
                raise PolicyError('Inbound creation requires actual confirmed quantity.')
        if seen != set(candidates):
            raise PolicyError('Return an explicit decision for every input line, including waits and exclusions.')
        return result
    positions = request.get('positions', {})
    devices = request.get('equipment', {})
    if type(positions) is not dict or type(devices) is not dict or (result and type(request.get('base_task')) is not dict) or any(type(item) is not dict for item in devices.values()):
        raise PolicyError('Task input requires position mappings, a base task and manual equipment objects.')
    goods = []
    for index, task in enumerate(result, 1):
        if type(task) is not dict or set(task) != TASK_KEYS_V4:
            raise PolicyError('Invalid /4 task fields.')
        if any(type(task[key]) is not int for key in ('equipment_id', 'location_res_id', 'location_dest_id', 'dependency_step')):
            raise PolicyError('Task and dependency identifiers must be integers.')
        if any(type(value) is not str or len(value) > 512 for key, value in task.items() if key not in ('equipment_id', 'location_res_id', 'location_dest_id', 'dependency_step')):
            raise PolicyError('Task text must be bounded strings.')
        authorized = devices.get(str(task['equipment_id']), {})
        if not authorized or task['task_type'] != authorized.get('task_type'):
            raise PolicyError('Equipment and task types must match explicit human authorizations.')
        for side, id_key in (('source_ref', 'location_res_id'), ('destination_ref', 'location_dest_id')):
            if task[side] not in positions or type(positions[task[side]]) is not int or positions[task[side]] != task[id_key]:
                raise PolicyError('Task endpoint must match its declared position source.')
        if task['location_res_id'] == task['location_dest_id'] or not task['reason']:
            raise PolicyError('Tasks need different endpoints and an explanation.')
        if task['role'] not in ('goods', 'empty_supply', 'empty_return') or task['movement'] not in ('primary', 'repeat', 'relay', 'empty'):
            raise PolicyError('Invalid task role or movement semantics.')
        if not 0 <= task['dependency_step'] < index or task['dependency_event'] not in ('end', 'take', 'point', 'point_or_take'):
            raise PolicyError('Dependencies must reference an earlier step with an explicit event.')
        if task['dependency_step'] and task['dependency_event'] != 'end' and not task['dependency_point']:
            raise PolicyError('Early release requires a specific point.')
        if task['role'] != 'goods':
            if task['movement'] != 'empty':
                raise PolicyError('Empty carrier steps require empty movement semantics.')
            continue
        if not goods:
            base = request['base_task']
            if task['movement'] != 'primary' or any(task[key] != base[key] for key in ('equipment_id', 'location_res_id', 'location_dest_id', 'source_ref', 'destination_ref')):
                raise PolicyError('First goods task must preserve the selected line decision and manual primary equipment.')
        else:
            previous_index, previous = goods[-1]
            if task['dependency_step'] != previous_index or task['dependency_event'] != 'end':
                raise PolicyError('Additional goods programs require completion of the previous goods program.')
            if task['movement'] == 'repeat':
                if any(task[key] != previous[key] for key in ('equipment_id', 'location_res_id', 'location_dest_id', 'source_ref', 'destination_ref', 'task_type')):
                    raise PolicyError('Repeat means identical goods data, equipment and physical endpoints.')
            elif task['movement'] == 'relay':
                if task['location_res_id'] != previous['location_dest_id']:
                    raise PolicyError('Relay endpoints must connect.')
            else:
                raise PolicyError('Additional goods steps must explicitly be repeat or relay.')
        goods.append((index, task))
    if result and not goods:
        raise PolicyError('A movement plan must include a goods program.')
    return result
