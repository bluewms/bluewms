import copy
import json

from odoo.tools import file_open


def fixture():
    with file_open('blue_erp_interface/tests/data/mapping.json') as source:
        return json.load(source)


def make_interface(env, warehouse, product, kind='incoming', publish=True, **values):
    connection = env['blue.erp.connection'].create({'name': 'ERP test connection', 'company_id': env.company.id,
        'base_url': 'https://erp.invalid', 'app_key': 'test-only-key', 'app_secret': 'test-only-secret',
        'service_user_id': env.user.id})
    settings = {'name': 'ERP test ' + kind, 'connection_id': connection.id, 'company_id': env.company.id,
                'kind': kind, 'inbound_token': 'erp-test-inbound'}
    if kind == 'inventory':
        settings['inventory_location_ids'] = [(6, 0, warehouse.lot_stock_id.ids)]
    else:
        operation = {'incoming': warehouse.in_type_id, 'outgoing': warehouse.out_type_id, 'internal': warehouse.int_type_id}[kind]
        settings.update(picking_type_id=operation.id, location_src_id=operation.default_location_src_id.id,
                        location_dest_id=operation.default_location_dest_id.id)
    interface = env['blue.erp.interface'].create({**settings, **values})
    for code in (['count_gain', 'count_loss'] if kind == 'inventory' else ['complete']):
        env['blue.erp.operation'].create({'name': code, 'code': code, 'path': '/' + code, 'interface_id': interface.id})
    example = fixture()
    cases = copy.deepcopy(example['inventory_cases'] if kind == 'inventory' else example['cases'])
    cases = json.loads(json.dumps(cases).replace('ERP-PRODUCT', product.default_code).replace('Units', product.uom_id.with_context(lang=None).name))
    for case in cases:
        case['input']['request']['kind'] = kind
    interface.profile_id.write({'draft_code': example['code'], 'draft_tests': json.dumps(cases)})
    if publish:
        interface.action_validate()
        interface.action_publish()
    return interface


def message(product, external_id='ERP-1', quantity=10, **line_values):
    return {'id': external_id, 'number': 'PO-' + external_id, 'lines': [
        {'id': '10', 'product': product.default_code, 'qty': quantity, 'unit': product.uom_id.with_context(lang=None).name, **line_values}]}


def done(picking, quantity):
    move = picking.move_ids[:1]
    line = move.move_line_ids[:1]
    values = {'quantity': quantity, 'picked': True}
    if line:
        line.write(values)
    else:
        picking.env['stock.move.line'].create({**values, 'move_id': move.id, 'picking_id': picking.id,
            'product_id': move.product_id.id, 'uom_id': move.uom_id.id,
            'location_id': move.location_id.id, 'location_dest_id': move.location_dest_id.id})
    return picking.button_validate()
