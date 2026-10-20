"""Exercise real transaction retries in an isolated database; no external calls."""
import threading
import uuid

from odoo import Command, api
from odoo.exceptions import UserError, ValidationError
from odoo.http.retrying import retrying
from odoo.tests import new_test_user
from odoo.tools import mute_logger

if not env.cr.dbname.endswith('_test'):
    raise RuntimeError('Use an isolated test database.')
registry = env.registry
suffix = uuid.uuid4().hex[:8]
with registry.cursor() as cr:
    setup = api.Environment(cr, env.uid, {})
    user = new_test_user(setup, login='count_retry_' + suffix, groups='stock.group_stock_manager,base.group_system',
        company_id=setup.company.id, company_ids=[Command.set(setup.company.ids)])
    work = api.Environment(cr, user.id, {})
    warehouse = work['stock.warehouse'].create({'name': 'Count concurrency ' + suffix, 'code': suffix[:5]})
    product = work['product.product'].create({'name': 'Count concurrency product', 'is_storable': True})
    work['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, 10)
    plans = work['stock.inventory'].create([{'location_ids': [Command.set(warehouse.lot_stock_id.ids)],
        'product_selection': 'one', 'product_ids': [Command.set(product.ids)]} for unused in range(2)])
    ids, user_id, product_id, location_id = plans.ids, user.id, product.id, warehouse.lot_stock_id.id
    cr.commit()  # Own cursor: fixtures must be visible to the two receiving transactions.


def race(plan_ids, method):
    barrier, results = threading.Barrier(2), []
    def act(plan_id):
        try:
            with registry.cursor() as cr:
                worker = api.Environment(cr, user_id, {})
                plan = worker['stock.inventory'].browse(plan_id)
                plan.read(['state'])
                barrier.wait(timeout=15)
                with mute_logger('odoo.sql_db'):
                    retrying({'action_start': plan.action_start, 'action_state_to_done': plan.action_state_to_done}[method], worker, close_on_commit=False)
                results.append(('success', plan_id))
        except (UserError, ValidationError) as error:
            results.append((type(error).__name__, plan_id))
        except Exception as error:
            results.append(('unexpected:' + type(error).__name__, plan_id))
    threads = [threading.Thread(target=act, args=(plan_id,)) for plan_id in plan_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads), 'Concurrent operation did not finish'
    assert len(results) == 2 and len([r for r in results if r[0] == 'success']) == 1, results
    assert not any(r[0].startswith('unexpected:') for r in results), results
    return next(plan_id for state, plan_id in results if state == 'success')

winner = race(ids, 'action_start')
with registry.cursor() as cr:
    work = api.Environment(cr, user_id, {})
    plan = work['stock.inventory'].browse(winner)
    assert work['stock.inventory'].browse(ids).filtered(lambda p: p.state == 'in_progress') == plan
    plan.line_ids.product_qty = 7
    cr.commit()  # Own cursor: persist the counted quantity before concurrent validations.

assert race([winner, winner], 'action_state_to_done') == winner
with registry.cursor() as cr:
    work = api.Environment(cr, user_id, {})
    plan = work['stock.inventory'].browse(winner)
    quants = work['stock.quant'].search([('product_id', '=', product_id), ('location_id', '=', location_id)])
    assert sum(quants.mapped('quantity')) == 7
    assert plan.state == 'done' and plan.line_ids.applied
    assert len(plan.stock_move_ids) == 1 and plan.stock_move_ids.quantity == 3

print('INVENTORY_CONCURRENCY_VALIDATION: overlapping_scopes_admitted=1, successful_completions=1, quantity=7, ledger_lines=1')
