"""Run with run(env) in an isolated *_test Odoo shell, never on a customer DB."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from psycopg2.errors import SerializationFailure

from odoo import api


def run(env):
    if not env.cr.dbname.endswith('_test'):
        raise RuntimeError('This validation is restricted to isolated *_test databases.')
    marker = uuid4().hex[:8]
    warehouse = env['stock.warehouse'].create({'name': 'Barcode concurrency ' + marker, 'code': marker[:5]})
    product = env['product.product'].create({'name': 'Concurrency item ' + marker,
        'barcode': 'CONC-' + marker, 'is_storable': True})
    picking = env['stock.picking'].create({'picking_type_id': warehouse.in_type_id.id,
        'location_id': warehouse.in_type_id.default_location_src_id.id, 'location_dest_id': warehouse.lot_stock_id.id})
    env['stock.move'].create({'picking_id': picking.id, 'product_id': product.id,
        'product_uom_qty': 10, 'uom_id': product.uom_id.id, 'location_id': picking.location_id.id,
        'location_dest_id': picking.location_dest_id.id})
    picking.action_confirm()
    client, event = uuid4().hex, uuid4().hex
    view = env['blue.barcode.service'].open_session('picking', picking.id, client)
    registry, uid, context = env.registry, env.uid, dict(env.context)
    session_id, picking_id, code = view['id'], picking.id, product.barcode
    # This script owns committed isolated fixtures so independent cursors can see them.
    env.cr.commit()
    barrier = Barrier(2)

    def submit():
        barrier.wait(timeout=10)
        for attempt in range(4):
            try:
                with registry.cursor() as cr:
                    worker = api.Environment(cr, uid, context)
                    response = worker['blue.barcode.session'].browse(session_id).action_event(
                        client, event, 0, {'raw': code})
                    cr.commit()  # This worker owns its isolated cursor.
                    return response['replayed']
            except SerializationFailure:
                if attempt == 3:
                    raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(results) == [False, True], results
    with registry.cursor() as cr:
        verify = api.Environment(cr, uid, context)
        session = verify['blue.barcode.session'].browse(session_id)
        assert len(session.event_ids) == 1
        assert verify['stock.picking'].browse(picking_id).move_line_ids.quantity == 1
    return {'concurrent_requests': 2, 'business_events': 1, 'quantity': 1, 'passed': True}
