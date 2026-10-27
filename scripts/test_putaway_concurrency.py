"""Run via Odoo shell against bluewms20_stock_test only.

Uses independent owned cursors and real HTTP retrying, with two stock users.
Leaves named fixtures in the isolated test DB for inspection; users are archived.
"""
import json
import logging
import threading
import time

from odoo import Command, SUPERUSER_ID, api
from odoo.exceptions import UserError
from odoo.http.retrying import retrying
from odoo.tools import file_open

from odoo.addons.blue_stock_putaway.models.policy_guard import POLICY_TOKEN

assert env.cr.dbname == 'bluewms20_stock_test', 'Never run this fixture on a business database.'
registry = env.registry
with registry.cursor() as cr:
    setup = api.Environment(cr, SUPERUSER_ID, {})
    company = setup.company
    warehouse = setup['stock.warehouse'].create({'name': 'Pallet concurrent last-slot test ' + str(time.time_ns()), 'code': 'PC' + str(int(time.time()) % 1000).zfill(3), 'company_id': company.id})
    root = setup['stock.location'].create({'name': 'Concurrency pallet area', 'usage': 'view', 'location_rank': 'area', 'location_id': warehouse.lot_stock_id.id, 'company_id': company.id})
    package_type = setup['stock.package.type'].create({'name': 'Concurrency pallet type', 'package_use': 'reusable'})
    category = setup['stock.storage.category'].create({'name': 'Concurrency ten pallet capacity', 'max_weight': 10000, 'company_id': company.id,
        'allow_new_product': 'mixed', 'capacity_ids': [Command.create({'package_type_id': package_type.id, 'quantity': 10})]})
    location = setup['stock.location'].create({'name': 'Concurrency only bin', 'usage': 'internal', 'location_id': root.id,
        'company_id': company.id, 'storage_category_id': category.id})
    native_rule = setup['stock.putaway.rule'].create({'location_in_id': root.id, 'location_out_id': root.id, 'sublocation': 'closest_location',
        'storage_category_id': category.id, 'company_id': company.id})
    product = setup['product.product'].create({'name': 'Concurrency fixture SKU', 'is_storable': True, 'tracking': 'lot'})
    lot = setup['stock.lot'].create({'name': 'CONCURRENT-BATCH', 'product_id': product.id, 'company_id': company.id})
    for __ in range(9):
        package = setup['stock.package'].create({'package_type_id': package_type.id})
        setup['stock.quant']._update_available_quantity(product, location, 1, lot_id=lot, package_id=package)
    profile = setup['blue.config.profile'].create({'name': 'Concurrency supplementary batch policy', 'company_id': company.id,
        'template_id': setup.ref('blue_stock_putaway.blue_scene_template_same_batch_name').id})
    native_rule.blue_profile_id = profile
    with file_open('blue_stock_putaway/tests/data/putaway_regression_cases.json') as source_file:
        case = json.load(source_file)['blue_scene_template_same_batch_name']
    profile.action_submit_draft(case['code_text'], case['test_cases'], 'Isolated current-contract concurrency fixture')
    profile.action_validate()
    profile.action_publish()
    picking_ids = []
    for __ in range(2):
        internal = setup(context=dict(setup.context, blue_putaway_token=POLICY_TOKEN))
        picking = internal['stock.picking'].create({'picking_type_id': warehouse.in_type_id.id,
            'location_id': setup.ref('stock.stock_location_suppliers').id, 'location_dest_id': root.id})
        move = internal['stock.move'].create({'product_id': product.id, 'uom_id': product.uom_id.id, 'product_uom_qty': 1,
            'picking_id': picking.id, 'location_id': picking.location_id.id, 'location_dest_id': root.id})
        move._action_confirm(merge=False)
        package = setup['stock.package'].create({'package_type_id': package_type.id})
        move.move_line_ids.write({'lot_id': lot.id, 'result_package_id': package.id, 'location_dest_id': root.id})
        picking_ids.append(picking.id)
    users = setup['res.users'].with_context(no_reset_password=True).create([
        {'name': 'Concurrency fixture worker ' + str(index), 'login': 'blue_pallet_concurrency_' + str(warehouse.id) + '_' + str(index),
         'company_id': company.id, 'company_ids': [Command.set(company.ids)],
         'group_ids': [Command.link(setup.ref('stock.group_stock_user').id)]}
        for index in range(2)])
    fixture = {'warehouse_id': warehouse.id, 'location_id': location.id, 'company_id': company.id, 'picking_ids': picking_ids, 'user_ids': users.ids}
    # Commit only our named synthetic fixture, in a cursor opened by this script.
    cr.commit()

ready = threading.Event()
allocated = threading.Event()
release_first = threading.Event()
results = {}
logging.getLogger('odoo.sql_db').setLevel(logging.CRITICAL)


def first_worker():
    try:
        with registry.cursor() as cr:
            worker = api.Environment(cr, fixture['user_ids'][0], {'allowed_company_ids': [fixture['company_id']]})
            if not ready.wait(10):
                raise AssertionError('Second transaction did not establish its snapshot.')
            worker['stock.picking'].browse(picking_ids[0]).action_blue_apply_putaway()
            allocated.set()
            if not release_first.wait(10):
                raise AssertionError('Lock observation timed out.')
            cr.commit()  # This script owns this independent cursor.
            results['first'] = 'allocated'
    except Exception as error:
        results['first_error'] = repr(error)
        allocated.set()


def second_worker():
    try:
        with registry.cursor() as cr:
            worker = api.Environment(cr, fixture['user_ids'][1], {'allowed_company_ids': [fixture['company_id']]})
            cr.execute('SELECT blue_putaway_revision, pg_backend_pid() FROM stock_warehouse WHERE id = %s', [fixture['warehouse_id']])
            __, results['second_pid'] = cr.fetchone()
            ready.set()
            if not allocated.wait(10):
                raise AssertionError('First transaction did not allocate.')
            results['attempts'] = 0

            def allocate():
                results['attempts'] += 1
                return worker['stock.picking'].browse(picking_ids[1]).action_blue_apply_putaway()

            try:
                retrying(allocate, worker, close_on_commit=False)
            except UserError:
                results['second'] = 'no remaining capacity'
            else:
                results['second'] = 'unexpected allocation'
    except Exception as error:
        results['second_error'] = repr(error)


two = threading.Thread(target=second_worker)
one = threading.Thread(target=first_worker)
two.start()
one.start()
assert allocated.wait(10), 'First worker timed out.'
lock_observed = False
end = time.monotonic() + 5
with registry.cursor() as cr:
    while time.monotonic() < end and not results.get('first_error'):
        cr.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s', [results.get('second_pid', 0)])
        row = cr.fetchone()
        if row and row[0] == 'Lock':
            lock_observed = True
            break
        time.sleep(0.05)
release_first.set()
one.join(15)
two.join(15)
assert not one.is_alive() and not two.is_alive(), 'Concurrent workers did not finish.'
with registry.cursor() as cr:
    check = api.Environment(cr, SUPERUSER_ID, {})
    first = check['stock.picking'].browse(picking_ids[0])
    second = check['stock.picking'].browse(picking_ids[1])
    assert first.move_line_ids.location_dest_id.id == fixture['location_id']
    assert not second.blue_putaway_release_id
    check['res.users'].browse(fixture['user_ids']).active = False
    cr.commit()  # Archive only the synthetic users created in our own cursor.
assert lock_observed, results
assert results.get('first') == 'allocated' and results.get('second') == 'no remaining capacity', results
assert results['attempts'] >= 2, results
print(json.dumps({'last_slot_winner_count': 1, 'blocked_second_allocation': True, 'row_lock_observed': lock_observed,
                  'native_retry_attempts': results['attempts'], 'worker_permissions': 'stock.group_stock_user', 'fixture': fixture}))
