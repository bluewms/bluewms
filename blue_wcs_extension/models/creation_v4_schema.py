"""Secret-free authoring schema; independent of example and database record identities."""
from .creation_v4 import REFS


def creation_schema_v4():
    integer = {'type': 'integer'}
    number = {'type': 'number'}
    boolean = {'type': 'boolean'}
    text = {'type': 'string', 'maxLength': 512}
    optional_id = {'oneOf': [integer, {'const': False}]}
    optional_number = {'oneOf': [number, {'const': False}]}

    def obj(properties):
        return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}

    def mapping(values):
        return {'type': 'object', 'additionalProperties': values}

    decision = obj({'line_id': integer, 'action': {'enum': ['create', 'wait', 'exclude']},
        'quantity_basis': {'enum': ['confirmed', 'reserved']}, 'quantity': {'type': 'number', 'minimum': 0},
        'group_key': text, 'source_ref': {'enum': list(REFS)}, 'destination_ref': {'enum': list(REFS)}, 'reason': text})
    task = obj({'equipment_id': integer, 'location_res_id': integer, 'location_dest_id': integer,
        'source_ref': {'enum': list(REFS)}, 'destination_ref': {'enum': list(REFS)},
        'role': {'enum': ['goods', 'empty_supply', 'empty_return']}, 'task_type': text,
        'movement': {'enum': ['primary', 'repeat', 'relay', 'empty']},
        'dependency_step': {'type': 'integer', 'minimum': 0},
        'dependency_event': {'enum': ['end', 'take', 'point', 'point_or_take']}, 'dependency_point': text, 'reason': text})
    line_props = {key: integer for key in ('line_id', 'product_id', 'uom_id', 'source_id', 'destination_id')}
    line_props.update({key: optional_id for key in ('carrier_id', 'lot_id', 'owner_id', 'package_type_id')})
    line_props.update({key: text for key in ('line_key', 'carrier_key', 'route_key', 'product_code', 'stock_state')})
    line_props.update({key: number for key in ('quantity', 'covered_quantity', 'available_quantity', 'stock_quantity', 'reserved_quantity', 'carrier_weight', 'carrier_volume')})
    line_props.update({key: boolean for key in ('picked', 'company_valid', 'storable', 'lot_ready', 'source_blocked', 'destination_blocked',
                                              'carrier_all_picked', 'carrier_same_uom', 'carrier_weight_complete', 'carrier_volume_complete')})
    line_props.update(carrier_quantity=optional_number, package_max_weight=optional_number)
    line = obj(line_props)
    common = {'phase': {'const': 'lines'}, 'picking_id': integer, 'state': text, 'company_id': integer,
              'operation': {'enum': ['incoming', 'outgoing', 'internal']}, 'wcs_type': {'enum': ['in', 'out']},
              'all_confirmed': boolean, 'picking_source_id': integer, 'picking_destination_id': integer}
    task_request = dict(common, phase={'const': 'tasks'}, positions=obj({ref: optional_id for ref in REFS}), base_task=task,
        primary_equipment_id=integer, secondary_equipment_id=optional_id, secondary_task_type=text,
        equipment=mapping(obj({'name': text, 'task_type': text, 'adapter': text, 'supports_loose_goods': boolean, 'supports_location_scope': boolean, 'supports_repeated_goods': boolean})),
        position_details=mapping(obj({'id': integer, 'name': text, 'point': text, 'contains_inventory_source': boolean, 'contains_inventory_destination': boolean})),
        lines=mapping(line), decisions=mapping(decision))
    return {'contract': 'wcs_creation/4', 'hook_code': 'wcs_creation',
        'execution': 'local published code; cloud draft/validate only; no publish/device control',
        'input': {'oneOf': [obj({'request': obj(common), 'candidates': {'type': 'array', 'items': line, 'maxItems': 200}}),
                            obj({'request': obj(task_request), 'candidates': {'type': 'array', 'items': task, 'maxItems': 4}})]},
        'lines_output': {'type': 'array', 'items': decision, 'maxItems': 200},
        'tasks_output': {'type': 'array', 'items': task, 'maxItems': 4},
        'field_semantics': {
            'candidates_lines': 'all positive current picking lines, before AI or picked/stock business filters; quantities use line UoM',
            'available_quantity': 'line quantity minus noncancelled plan coverage, counted once per plan rather than per task',
            'stock_quantity/reserved_quantity': 'matching company/source/product/lot/package/owner, in product base UoM; 0 for incoming external source',
            'carrier_all_picked': 'all positive lines of this physical outer carrier on this picking; distinct from request.all_confirmed',
            'carrier_quantity': 'sum only if same UoM; otherwise false; not a universal fullness signal',
            'carrier_weight/volume': 'sum product weight/volume times quantities converted to product base UoM, before filtering; complete=false if any missing',
            'package_max_weight': 'native package type maximum shipping weight, false if not configured; not a minimum or automatic full flag',
            'group_key': 'line_key, carrier_key or route_key are usable defaults; each group requires compatible physical carrier and mappings',
            'quantity_basis': 'incoming always confirmed; nonincoming reserved needs no picked flag, confirmed additionally requires picked',
            'position_refs': 'line/picking source/destination, manual handoff, or line endpoint parents; inventory locations never rewritten',
            'repeat': 'same goods data/equipment/task type/endpoints, distinct program identity, waits for previous goods end, quantities covered once',
            'exclude': 'WCS not required for this line, with fixed release and line fingerprint for inventory-validation coverage; not a stock exclusion',
            'wait': 'no WCS created; reconsider at next scan, blocks uncovered WCS inventory validation if other tasks exist',
        },
        'syntax': {'allowed': ['single variable assignment', 'JSON literals', 'existing dict string-key access', 'if/elif/else',
                               'conditional expression', 'for candidate in candidates', 'result.append(object)', 'and/or/not',
                               'comparisons including in/not in', 'bounded numeric + - * /'],
                   'forbidden': ['imports', 'ORM', 'eval/exec', 'network', 'filesystem', 'general calls including get/len/dict',
                                 'list indexing', 'nested loops', 'while', 'comprehensions', 'dictionary mutation/expansion', 'object attributes'],
                   'limits': {'code_characters': 32768, 'AST_nodes': 2000, 'steps': 30000, 'input_JSON_characters': 262144}},
        'invariants': ['explicit decision exactly once for every input line', 'quantity within uncovered amount, wait/exclude quantity=0',
                       'manual equipment/task types and all manual switches immutable to policy', 'actual stock, reservation, company, freezing and whole-carrier contents checked after filtering',
                       'first goods uses primary equipment and decision mapping; final physical scope contains inventory destination',
                       'additional goods explicitly repeat(same data) or relay(connected endpoints), dependency on previous goods end',
                       'separate task names/steps; one plan goods coverage; stock validated once after all steps complete',
                       'unknown/failed tasks keep quantity coverage; concurrent/repeated planning cannot recreate the same quantities'],
        'capabilities': {'loose_goods': 'simulation or manually enabled JSON only; HIK requires carrier',
                         'area_mapping': 'simulation, HIK ZONE or explicitly enabled JSON',
                         'repeat_goods': 'simulation or manually confirmed real equipment support; no claim of real-device acceptance',
                         'actual_bin_callback': 'accept declared area or single already-planned exact bin; other actual bins require reconciliation, never auto-write inventory'},
        'trials': {'shape': '{name,input,expected_result}', 'count': '2..20 per asset; cover lines and tasks phases',
                   'notes': 'production schema is complete; small interpreter trials may omit unused input keys'},
    }
