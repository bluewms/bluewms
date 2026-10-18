import json

from odoo.tools import file_open

from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN


def fixture(name='tusk-subposition'):
    with file_open('blue_wcs_protocol/tests/data/protocol_regression_cases.json') as source:
        return json.load(source)[name]


def make_category(env, root, name='tusk-subposition', **settings):
    category = env['wcs.equipment.category'].create({
        'name': 'Protocol regression ' + name, 'company_id': env.company.id, 'adapter_code': 'protocol',
        'ip_post': 'http://127.0.0.1:9', 'submit_path': '/rpc/createTask', 'protocol_tusk_compat': True,
        'protocol_allow_destination': name == 'tusk-destination', 'protocol_destination_root_id': root.id,
        **settings})
    example = fixture(name)
    category.protocol_profile_id.write({'draft_code': example['code'], 'draft_tests': json.dumps(example['cases'])})
    category.action_protocol_validate()
    category.action_protocol_publish()
    return category


def make_task(env, category, warehouse, destination, product, quantity=10):
    picking = env['stock.picking'].create({'picking_type_id': warehouse.in_type_id.id,
        'location_id': env.ref('stock.stock_location_suppliers').id, 'location_dest_id': destination.id})
    package = env['stock.package'].create({'name': 'Protocol carrier %s' % picking.id})
    move = env['stock.move'].create({'picking_id': picking.id, 'product_id': product.id,
        'uom_id': product.uom_id.id, 'product_uom_qty': quantity,
        'location_id': picking.location_id.id, 'location_dest_id': destination.id})
    picking.action_confirm()
    picking.action_assign()
    line = move.move_line_ids[:1]
    values = {'quantity': quantity, 'picked': True, 'result_package_id': package.id}
    if line:
        line.write(values)
    else:
        line = env['stock.move.line'].create({**values, 'move_id': move.id, 'picking_id': picking.id,
            'product_id': product.id, 'uom_id': product.uom_id.id,
            'location_id': picking.location_id.id, 'location_dest_id': destination.id})
    device = env['wcs.equipment'].create({'name': 'Protocol device %s' % picking.id,
        'company_id': env.company.id, 'category_id': category.id})
    token = dict(blue_wcs_token=WCS_TOKEN)
    plan = env['wcs.plan'].with_context(**token).create({'name': 'Protocol plan %s' % picking.id,
        'company_id': env.company.id, 'picking_id': picking.id, 'carrier_id': package.id,
        'unit_key': package.name, 'revision': 1, 'snapshot': '{}'})
    env['wcs.plan.line'].with_context(**token).create({'plan_id': plan.id, 'move_line_id': line.id,
        'product_id': product.id, 'uom_id': product.uom_id.id, 'quantity': quantity, 'package_id': package.id})
    task = env['wcs.request'].with_context(**token).create({'company_id': env.company.id,
        'plan_id': plan.id, 'equipment_id': device.id, 'step': 1, 'role': 'goods',
        'source_point': 'A', 'destination_point': 'B', 'location_res_id': picking.location_id.id,
        'location_dest_id': destination.id, 'task_type': 'TRANSFER', 'carrier_code': package.name})
    return task, line, package
