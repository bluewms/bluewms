"""Run in Odoo shell after test_wcs_concurrency.py, on *_test only."""
import json
from odoo import api

if not env.cr.dbname.endswith('_test'):
    raise RuntimeError('Disposable test databases only.')
registry = env.registry
# Start from the retained synthetic concurrency plan.
with registry.cursor() as cr:
    current = api.Environment(cr, env.uid, {})
    plan = current['wcs.plan'].search([('name', 'like', 'WCS concurrency carrier')], order='id desc', limit=1)
    if not plan:
        raise RuntimeError('Run test_wcs_concurrency.py first.')
    tasks = plan.request_ids.sorted('step')
    first_id, second_id = tasks.ids
    cr.commit()  # Own cursor: close the read snapshot before the scheduler transactions.
env['wcs.request']._cron_dispatch()
with registry.cursor() as cr:
    current = api.Environment(cr, env.uid, {})
    first = current['wcs.request'].browse(first_id)
    second = current['wcs.request'].browse(second_id)
    assert first.state == 'accepted' and second.state == 'waiting', (first.state, second.state)
    first._receive_event('dispatcher-first-done', 'end', actual_destination=first.destination_point)
    cr.commit()  # Own cursor: durable event and dependent release before next dispatch.
env['wcs.request']._cron_dispatch()
with registry.cursor() as cr:
    current = api.Environment(cr, env.uid, {})
    second = current['wcs.request'].browse(second_id)
    assert second.state == 'accepted'
    second._receive_event('dispatcher-second-done', 'end', actual_destination=second.destination_point)
    picking = second.picking_id
    picking.button_validate()
    assert picking.state == 'done'
    result = {'first': current['wcs.request'].browse(first_id).state, 'second': second.state, 'stock_picking': picking.state}
    cr.commit()  # Own cursor: final synthetic stock completion.
print('WCS_DISPATCH_RESULT=' + json.dumps(result))
