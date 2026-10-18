"""Public, secret-free authoring specification for the local WCS contract."""


def creation_schema():
    schema = {
        'contract': 'wcs_creation/3', 'hook_code': 'wcs_creation',
        'execution': 'local bounded interpreter; cloud generates drafts only; no publish or device tool',
        'input': {'type': 'object', 'required': ['request', 'candidates'], 'additionalProperties': False,
                  'request_phases': {
                      'configure': {'phase': 'configure', 'picking_id': 'integer', 'state': 'string',
                                    'company_id': 'integer', 'operation': 'incoming|outgoing|internal',
                                    'wcs_type': 'in|out (manual)', 'all_confirmed': 'boolean'},
                      'tasks': {'phase': 'tasks', 'settings': 'configure result', 'picking_id': 'integer',
                                'state': 'string', 'company_id': 'integer', 'operation': 'string',
                                'wcs_type': 'in|out (manual)', 'confirmed': 'boolean', 'all_confirmed': 'boolean',
                                'default_condition_met': 'boolean', 'ready': 'boolean',
                                'source_id': 'integer', 'destination_id': 'integer',
                                'source_parent_id': 'integer', 'destination_parent_id': 'integer',
                                'equipment_id': 'integer (manual primary)', 'task_type': 'string (manual primary)',
                                'secondary_equipment_id': 'integer|false (manual)', 'secondary_task_type': 'string',
                                'intermediate_location_id': 'integer|false', 'mode': 'settings.mode',
                                'allowed_location_ids': 'integer[]', 'allowed_equipment_ids': 'integer[] (explicit selections only)',
                                'allowed_goods_destinations': 'integer[]',
                                'locations': 'object keyed by string ID: {name:string,parent_id:integer|false,point:string}',
                                'equipment': 'object keyed by string ID: {name:string,category_id:integer|false,task_type:string}',
                                'quantities': 'object keyed by move line ID string: positive uncovered quantity in line UoM'}},
                  'candidates': 'configure: []; tasks: 1-2 full task objects built from chosen mode'},
        'configure_output': {'type': 'object', 'additionalProperties': False,
                             'required': ['condition', 'mode', 'quantity_basis', 'group_by_container'],
                             'properties': {'condition': {'enum': ['ready', 'all_confirmed']},
                                            'mode': {'enum': ['single', 'relay', 'double_in', 'double_out']},
                                            'quantity_basis': {'enum': ['confirmed', 'reserved']},
                                            'group_by_container': {'type': 'boolean'}}},
        'tasks_output': {'type': 'array', 'maxItems': 4, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['equipment_id', 'location_res_id', 'location_dest_id', 'role', 'task_type',
                         'dependency_step', 'dependency_event', 'dependency_point', 'reason'],
            'properties': {'equipment_id': {'type': 'integer'}, 'location_res_id': {'type': 'integer'},
                           'location_dest_id': {'type': 'integer'}, 'role': {'enum': ['goods', 'empty_supply', 'empty_return']},
                           'task_type': {'type': 'string', 'maxLength': 512}, 'dependency_step': {'type': 'integer', 'minimum': 0},
                           'dependency_event': {'enum': ['end', 'take', 'point', 'point_or_take']},
                           'dependency_point': {'type': 'string', 'maxLength': 512}, 'reason': {'type': 'string', 'maxLength': 512}}}},
        'syntax': {'allowed': ['single variable assignment', 'JSON literals', 'existing dictionary string-key subscripts',
                               'if/elif/else', 'conditional expression', 'for candidate in candidates', 'result.append(task)',
                               'and/or/not', 'comparisons including in/not in', 'bounded numeric + - * /'],
                   'forbidden': ['imports', 'functions', 'ORM', 'network', 'filesystem', 'attributes except result.append',
                                 'get/sort/len/dict/str and all other calls', 'list indexing', 'comprehensions',
                                 'nested loops', 'while', 'try', 'dictionary mutation', 'dictionary expansion'],
                   'limits': {'code_characters': 32768, 'AST_nodes': 2000, 'steps': 30000,
                              'input_bytes_convention': 'JSON text <=262144 characters', 'text_characters': 512}},
        'invariants': ['inbound quantity_basis=confirmed', 'all selected stock lines assigned, storable and lots complete',
                       'outbound valid stock and reservation', 'no frozen or cross-company locations', 'whole carrier completeness',
                       'noncancelled plans cover quantities; busy carrier waits; completed carrier cannot move again on same picking',
                       'first goods starts at actual source and manual primary equipment; final approved destination',
                       'goods relay continuous with end dependency; explicit earlier dependency steps only',
                       'equipment restricted to primary/secondary; task_type equals manual authorization',
                       'no AI control of WCS/automatic creation/automatic validation/required-task switches',
                       'no package: simulation or explicitly capable JSON gateway only; HIK/WES require carrier'],
        'trials': {'schema': '{name:string,input:{request:object,candidates:array},expected_result:object|array}',
                   'count': '2..20; include configure and tasks phases'},
    }

    integer = {'type': 'integer'}
    boolean = {'type': 'boolean'}
    text = {'type': 'string'}
    optional_id = {'oneOf': [integer, {'const': False}]}
    configure = {key: text for key in ('phase', 'state', 'operation', 'wcs_type')}
    configure.update(phase={'const': 'configure'}, picking_id=integer, company_id=integer, all_confirmed=boolean)
    tasks = dict(configure, phase={'const': 'tasks'}, settings=schema['configure_output'])
    tasks.update({key: integer for key in ('source_id', 'destination_id', 'source_parent_id', 'destination_parent_id', 'equipment_id')})
    tasks.update({key: optional_id for key in ('secondary_equipment_id', 'intermediate_location_id')})
    tasks.update({key: boolean for key in ('confirmed', 'default_condition_met', 'ready')})
    tasks.update({key: text for key in ('task_type', 'secondary_task_type', 'mode')})
    tasks.update({key: {'type': 'array', 'items': integer} for key in ('allowed_location_ids', 'allowed_equipment_ids', 'allowed_goods_destinations')})
    tasks.update(locations={'type': 'object', 'additionalProperties': {
        'type': 'object', 'required': ['name', 'parent_id', 'point'], 'additionalProperties': False,
        'properties': {'name': text, 'parent_id': optional_id, 'point': text}}},
        equipment={'type': 'object', 'additionalProperties': {
            'type': 'object', 'required': ['name', 'category_id', 'task_type'], 'additionalProperties': False,
            'properties': {'name': text, 'category_id': optional_id, 'task_type': text}}},
        quantities={'type': 'object', 'additionalProperties': {'type': 'number', 'minimum': 0}})
    # Complete production input schemas. Small synthetic local trials may omit unused keys.
    schema['input']['properties'] = {
        'request': {'oneOf': [dict(type='object', properties=props, required=list(props), additionalProperties=False)
                              for props in (configure, tasks)]},
        'candidates': dict(schema['tasks_output']),
    }
    schema['input']['properties']['candidates']['description'] = 'Empty in configure; generated task defaults in tasks.'
    return schema
