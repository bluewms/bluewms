"""Bounded task proposals from original WCS operation defaults and stock locations."""
import json

from odoo.addons.blue_extension_contract.tools.policy import Interpreter, PolicyError, validate_code


TASK_KEYS = {'equipment_id', 'location_res_id', 'location_dest_id', 'role', 'task_type',
             'dependency_step', 'dependency_event', 'dependency_point', 'reason'}


class CreationInterpreter(Interpreter):
    def append_result(self, result, value):
        if type(value) is not dict or set(value) != TASK_KEYS:
            raise PolicyError('Each task needs equipment, source/destination, role, template, dependency and reason.')
        if any(type(value[key]) is not int for key in ('equipment_id', 'location_res_id', 'location_dest_id', 'dependency_step')):
            raise PolicyError('Task identifiers and dependency step must be integers.')
        if any(type(value[key]) is not str or len(value[key]) > 512 for key in ('role', 'task_type', 'dependency_event', 'dependency_point', 'reason')):
            raise PolicyError('Task text must be bounded strings.')
        result.append(dict(value))


def run_creation(code, payload):
    tree = validate_code(code)
    try:
        encoded = json.dumps(payload, allow_nan=False)
        if len(encoded) > 262144:
            raise PolicyError('Creation input exceeds 256KB.')
        payload = json.loads(encoded)
    except (ValueError, TypeError, RecursionError) as error:
        raise PolicyError('Creation input must be finite JSON.') from error
    if type(payload) is not dict or set(payload) != {'request', 'candidates'} or type(payload['request']) is not dict or type(payload['candidates']) is not list or len(payload['candidates']) > 4:
        raise PolicyError('Creation input needs request and at most four default task candidates.')
    interpreter = CreationInterpreter(payload)
    try:
        interpreter.statements(tree.body)
    except RecursionError as error:
        raise PolicyError('Creation code nesting is too deep.') from error
    result = interpreter.variables.get('result')
    if type(result) is not list or len(result) > 4:
        raise PolicyError('Create at most four tasks per physical movement unit.')
    request = payload['request']
    allowed_locations = request.get('allowed_location_ids', [])
    allowed_equipment = request.get('allowed_equipment_ids', [])
    for index, task in enumerate(result, start=1):
        # Check even a result assigned as a literal instead of appended.
        interpreter.append_result([], task)
        if task['equipment_id'] not in allowed_equipment or task['location_res_id'] not in allowed_locations or task['location_dest_id'] not in allowed_locations:
            raise PolicyError('Task uses a device or location outside this operation scope.')
        if task['location_res_id'] == task['location_dest_id'] or not task['task_type']:
            raise PolicyError('A task needs different endpoints and a device template.')
        if task['role'] not in ('goods', 'empty_supply', 'empty_return') or task['dependency_event'] not in ('end', 'take', 'point', 'point_or_take'):
            raise PolicyError('Unsupported task role or dependency event.')
        if not 0 <= task['dependency_step'] < index:
            raise PolicyError('Dependencies must refer to an earlier task, never self or future steps.')
        if task['dependency_step'] and task['dependency_event'] != 'end' and not task['dependency_point']:
            raise PolicyError('Early release requires an explicit point.')
        if task['dependency_step'] and task['role'] == 'goods' and result[task['dependency_step'] - 1]['role'] == 'goods' and task['dependency_event'] != 'end':
            raise PolicyError('Same-goods relay requires predecessor completion.')
    goods = [(index, task) for index, task in enumerate(result, start=1) if task['role'] == 'goods']
    if result and not goods:
        raise PolicyError('A goods operation requires a goods task.')
    for previous, following in zip(goods, goods[1:]):
        if following[1]['dependency_step'] != previous[0] or following[1]['location_res_id'] != previous[1]['location_dest_id']:
            raise PolicyError('Goods tasks must form a contiguous relay, not independent duplicate movements.')
    if goods and request.get('source_id') and goods[0][1]['location_res_id'] != request['source_id']:
        raise PolicyError('First goods task must start at the actual stock source.')
    if goods and request.get('destination_id') and goods[-1][1]['location_dest_id'] not in request.get('allowed_goods_destinations', [request['destination_id']]):
        raise PolicyError('Final goods task must preserve the approved stock destination scope.')
    return result


SETTINGS_KEYS = {'condition', 'mode', 'quantity_basis', 'group_by_container'}
BASIC_SETTINGS = {'condition': 'ready', 'mode': 'single', 'quantity_basis': 'reserved', 'group_by_container': False}


def run_creation_v3(code, payload):
    """Resolve policy settings before grouping, then validate bounded task proposals."""
    tree = validate_code(code)
    try:
        encoded = json.dumps(payload, allow_nan=False)
        if len(encoded) > 262144:
            raise PolicyError('Creation input exceeds 256KB.')
        payload = json.loads(encoded)
    except (ValueError, TypeError, RecursionError) as error:
        raise PolicyError('Creation input must be finite JSON.') from error
    if (type(payload) is not dict or set(payload) != {'request', 'candidates'}
            or type(payload['request']) is not dict or type(payload['candidates']) is not list
            or len(payload['candidates']) > 4):
        raise PolicyError('Creation input needs request and at most four candidates.')
    request = payload['request']
    if request.get('phase') not in ('configure', 'tasks'):
        raise PolicyError('Creation phase must be configure or tasks.')
    if request['phase'] == 'configure':
        interpreter = CreationInterpreter(payload)
        try:
            interpreter.statements(tree.body)
        except RecursionError as error:
            raise PolicyError('Creation code nesting is too deep.') from error
        settings = interpreter.variables.get('result')
        if type(settings) is not dict or set(settings) != SETTINGS_KEYS:
            raise PolicyError('Configure result requires condition, mode, quantity_basis, group_by_container.')
        if (settings['condition'] not in ('ready', 'all_confirmed')
                or settings['mode'] not in ('single', 'relay', 'double_in', 'double_out')
                or settings['quantity_basis'] not in ('confirmed', 'reserved')
                or type(settings['group_by_container']) is not bool):
            raise PolicyError('Invalid creation settings.')
        if request.get('operation') == 'incoming' and settings['quantity_basis'] != 'confirmed':
            raise PolicyError('Inbound WCS requires actual confirmed quantities.')
        return settings
    result = run_creation(code, payload)
    if result and (type(request.get('ready')) is not bool or type(request.get('all_confirmed')) is not bool
                   or type(request.get('settings')) is not dict or set(request['settings']) != SETTINGS_KEYS
                   or type(request.get('equipment')) is not dict or type(request.get('equipment_id')) is not int):
        raise PolicyError('Task phase requires readiness, settings and manual equipment authorizations.')
    if result and (not request.get('ready') or (request['settings']['condition'] == 'all_confirmed' and not request['all_confirmed'])):
        raise PolicyError('Tasks cannot bypass readiness or configured confirmation conditions.')
    for task in result:
        expected = request['equipment'].get(str(task['equipment_id']), {}).get('task_type')
        if not expected or task['task_type'] != expected:
            raise PolicyError('Use the task type explicitly authorized for this equipment.')
    goods = [task for task in result if task['role'] == 'goods']
    if goods and goods[0]['equipment_id'] != request['equipment_id']:
        raise PolicyError('First goods task must use the manually selected primary equipment.')
    return result
