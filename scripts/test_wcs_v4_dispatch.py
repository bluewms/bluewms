"""Run in Odoo shell after test_wcs_v4_concurrency.py, on *_test only."""
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
        raise RuntimeError('Run test_wcs_v4_concurrency.py first.')
    tasks = plan.request_ids.sorted('step')
    assert tasks[1].goods_mode == 'repeat'
    assert tasks[0]._prepared_payload()['items'] == tasks[1]._prepared_payload()['items']
    assert tasks[0].location_res_id == tasks[1].location_res_id
    assert tasks[0].location_dest_id == tasks[1].location_dest_id
    assert tasks.equipment_id.adapter_code == 'simulation'
    first_id, second_id = tasks.ids
    cr.commit()  # Own cursor: close the read snapshot before the scheduler transactions.
env['wcs.request']._cron_dispatch()
with registry.cursor() as cr:
    current = api.Environment(cr, env.uid, {})
    first = current['wcs.request'].browse(first_id)
    second = current['wcs.request'].browse(second_id)
    assert first.state == 'accepted' and second.state == 'waiting', (first.state, second.state)
    first._receive_event('dispatcher-take-only', 'take', point=first.source_point)
    first._receive_event('dispatcher-point-only', 'point', point=first.destination_point)
    assert second.state == 'waiting'
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
    planned_quantity = sum(second.plan_id.line_ids.mapped('quantity'))
    rows = second.plan_id.line_ids
    actual_quantity = sum(current['stock.quant'].search([('product_id', 'in', rows.product_id.ids), ('location_id', '=', rows.move_line_id.location_dest_id.id)]).mapped('quantity'))
    assert planned_quantity == actual_quantity == 10
    result = {'planned_quantity': planned_quantity, 'actual_quantity': actual_quantity, 'first': current['wcs.request'].browse(first_id).state, 'second': second.state, 'stock_picking': picking.state}
    cr.commit()  # Own cursor: final synthetic stock completion.
print('WCS_V4_REPEAT_DISPATCH_RESULT=' + json.dumps(result))
