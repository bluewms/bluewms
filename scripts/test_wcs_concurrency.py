"""Run with Odoo shell on a disposable *_test database only.
Creates named synthetic fixtures, retains them for inspection, archives the test user.
"""
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from psycopg2.errors import SerializationFailure
from odoo import api
from odoo.tests import new_test_user
from odoo.tools import file_open

if not env.cr.dbname.endswith('_test'):
    raise RuntimeError('Use an isolated *_test database, never the development database.')
registry = env.registry
suffix = uuid.uuid4().hex[:8]
with registry.cursor() as cr:
    fixture = api.Environment(cr, env.uid, {})
    warehouse = fixture['stock.warehouse'].search([('company_id', '=', fixture.company.id)], limit=1)
    operation = warehouse.int_type_id
    operation.write({'blue_wcs_enabled': True, 'blue_wcs_ready_mode': 'reserved', 'blue_wcs_profile_id': False})
    source = warehouse.lot_stock_id
    destination = fixture['stock.location'].create({'name': 'WCS concurrent destination ' + suffix,
        'location_id': source.id, 'usage': 'internal', 'company_id': fixture.company.id})
    product = fixture['product.product'].create({'name': 'WCS concurrency ' + suffix, 'is_storable': True})
    package = fixture['stock.package'].create({'name': 'WCS concurrency carrier ' + suffix})
    fixture['stock.quant']._update_available_quantity(product, source, 10, package_id=package)
    picking = fixture['stock.picking'].create({'picking_type_id': operation.id, 'location_id': source.id, 'location_dest_id': destination.id})
    fixture['stock.move'].create({'picking_id': picking.id, 'product_id': product.id, 'uom_id': product.uom_id.id,
        'product_uom_qty': 10, 'location_id': source.id, 'location_dest_id': destination.id})
    picking.action_confirm()
    picking.action_assign()
    picking.move_line_ids.result_package_id = package
    category = fixture['wcs.equipment.category'].create({'name': 'Concurrency simulation ' + suffix, 'company_id': fixture.company.id})
    devices = fixture['wcs.equipment'].create([{'name': 'WCS concurrency device ' + suffix, 'company_id': fixture.company.id, 'category_id': category.id},
                                              {'name': 'WCS concurrency second ' + suffix, 'company_id': fixture.company.id}])
    intermediate = fixture['stock.location'].create({'name': 'WCS concurrency handoff ' + suffix,
        'location_id': source.id, 'usage': 'internal', 'company_id': fixture.company.id, 'agv_map_point': 'X'})
    source.agv_map_point = 'A'
    destination.agv_map_point = 'B'
    profile = fixture['blue.config.profile'].create({'name': 'Concurrency relay ' + suffix, 'template_id': fixture.ref('blue_wcs_extension.template_relay_v3').id})
    with file_open('blue_wcs_extension/tests/data/legacy_wcs_regression_cases.json') as source_file:
        case = json.load(source_file)['template_relay_v3']
    profile.action_submit_draft(case['code_text'], case['test_cases'], 'Isolated legacy concurrency regression fixture')
    profile.action_validate()
    profile.action_publish()
    operation.write({'wcs_type': 'out', 'task_type': 'TRANSFER', 'wcs_secondary_task_type': 'TRANSFER',
        'equipment_category_id': category.id, 'blue_wcs_profile_id': profile.id, 'equipment_id': devices[0].id, 'wcs_secondary_equipment_id': devices[1].id,
        'wcs_request_mode': 'relay', 'wcs_intermediate_location_id': intermediate.id,
        'is_create_wcs_by_container': True, 'is_wcs_required_for_validate': True})
    user = new_test_user(fixture, login='wcs_concurrent_' + suffix, groups='stock.group_stock_user')
    picking_id, user_id = picking.id, user.id
    cr.commit()  # Own cursor: fixtures visible to independent concurrency transactions.
barrier = threading.Barrier(2)

def attempt(index):
    retries = 0
    for number in range(3):
        try:
            with registry.cursor() as cr:
                current = api.Environment(cr, user_id, {})
                picking = current['stock.picking'].browse(picking_id)
                state = picking.state  # Establish an independent repeatable-read snapshot.
                if number == 0:
                    barrier.wait(timeout=15)
                picking.action_create_wcs_request_from_button()
                cr.commit()  # Own cursor: independent business transaction.
                return retries
        except SerializationFailure:
            retries += 1
    raise RuntimeError('Concurrency retry exhausted')

with ThreadPoolExecutor(max_workers=2) as pool:
    retries = list(pool.map(attempt, [0, 1]))
with registry.cursor() as cr:
    current = api.Environment(cr, env.uid, {})
    picking = current['stock.picking'].browse(picking_id)
    result = {'picking_id': picking_id, 'plans': len(picking.wcs_plan_ids), 'tasks': len(picking.wcs_request_ids),
              'quantity': sum(picking.wcs_plan_ids.line_ids.mapped('quantity')), 'retries': retries}
    assert result['plans'] == 1 and result['tasks'] == 2 and result['quantity'] == 10, result
    current['res.users'].browse(user_id).active = False
    cr.commit()  # Own cursor: archive the dedicated synthetic test identity.
print('WCS_CONCURRENCY_RESULT=' + json.dumps(result))
