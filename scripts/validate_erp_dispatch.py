"""Durable sender integration with a mocked ERP, restricted to an isolated database.

Run through Odoo shell. Own cursors intentionally persist test fixtures and sender claims.
No real network requests are made. Reruns use unique test identities.
"""
import uuid
from unittest.mock import patch

from odoo import api, fields
from odoo.tests import new_test_user
from odoo.tools import mute_logger

from odoo.addons.blue_erp_interface.models.guard import ERP_TOKEN
from odoo.addons.blue_erp_interface.tests.common import done, make_interface, message

if not env.cr.dbname.endswith('_test'):
    raise RuntimeError('Use an isolated test database.')
registry = env.registry
suffix = uuid.uuid4().hex[:8]
with registry.cursor() as cr:
    setup = api.Environment(cr, env.uid, {})
    user = new_test_user(setup, login='erp_dispatch_' + suffix, groups='stock.group_stock_manager,base.group_system',
        company_id=setup.company.id, company_ids=[(6, 0, setup.company.ids)])
    work = api.Environment(cr, user.id, {})
    warehouse = work['stock.warehouse'].create({'name': 'ERP dispatch ' + suffix, 'code': suffix[:5]})
    product = work['product.product'].create({'name': 'Dispatch product', 'default_code': 'DISPATCH-' + suffix, 'is_storable': True})
    interface = make_interface(work, warehouse, product)
    interface._receive(message(product, external_id='D-' + suffix))
    document = interface.document_ids
    done(document.picking_ids, 10)
    event = document.event_ids
    event._prepare()
    first = event.delivery_ids
    second = work['blue.erp.delivery'].with_context(blue_erp_token=ERP_TOKEN).create({
        'event_id': event.id, 'company_id': work.company.id, 'sequence': 2,
        'operation': 'complete', 'path': '/complete', 'body': {'second': True}})
    ids = [first.id, second.id]
    event_id, user_id = event.id, user.id
    cr.commit()  # Own cursor: fixtures must be visible to the separate sender transactions.

calls = []

def simulated_send(connection, operation, body, headers, code, snapshot):
    with registry.cursor() as check_cr:
        check_cr.execute('SELECT id,state FROM blue_erp_delivery WHERE id IN %s ORDER BY sequence', [tuple(ids)])
        states = dict(check_cr.fetchall())
        active = ids[len(calls)]
        assert states[active] == 'sending', states
    calls.append(connection['idempotency_key'])
    if len(calls) == 1:
        # A concurrent/re-entrant worker cannot resend the claim or advance the next step.
        with registry.cursor() as other_cr:
            other = api.Environment(other_cr, user_id, {})
            other['blue.erp.event']._cron_dispatch()
            other_cr.commit()  # Own cursor: complete this independent worker invocation.
        assert len(calls) == 1
    return 'done', 'MOCK-ERP'

with registry.cursor() as cr:
    work = api.Environment(cr, user_id, {})
    with patch('odoo.addons.blue_erp_interface.tools.transport.send', side_effect=simulated_send):
        work['blue.erp.event']._cron_dispatch()
        work['blue.erp.event']._cron_dispatch()
    assert len(calls) == 2 and len(set(calls)) == 2, calls
    cr.commit()  # Own cursor: refresh the snapshot after separate sender commits.
    work['blue.erp.event'].browse(event_id).invalidate_recordset()
    assert work['blue.erp.event'].browse(event_id).state == 'done'
    cr.commit()  # Own cursor: persist completed integration evidence.

with registry.cursor() as cr:
    work = api.Environment(cr, user_id, {})
    interface = work['blue.erp.interface'].browse(interface.id)
    interface._receive(message(product.with_env(work), external_id='CRASH-' + suffix))
    document = interface.document_ids.filtered(lambda d: d.external_id == 'CRASH-' + suffix)
    done(document.picking_ids, 10)
    crash_event_id = document.event_ids.id
    cr.commit()  # Own cursor: new independent event for crash recovery testing.

with registry.cursor() as cr:
    work = api.Environment(cr, user_id, {})
    with patch('odoo.addons.blue_erp_interface.tools.transport.send', side_effect=RuntimeError('Simulated process loss')):
        try:
            work['blue.erp.event']._cron_dispatch()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Expected process-loss simulation')

with registry.cursor() as cr:
    work = api.Environment(cr, user_id, {})
    event = work['blue.erp.event'].browse(crash_event_id)
    assert event.delivery_ids.state == 'sending'
    with patch('odoo.addons.blue_erp_interface.tools.transport.send') as send:
        work['blue.erp.event']._cron_dispatch()
        send.assert_not_called()
    event.delivery_ids.with_context(blue_erp_token=ERP_TOKEN).write({
        'sent_at': fields.Datetime.subtract(fields.Datetime.now(), minutes=11)})
    cr.commit()  # Own cursor: simulate an aged durable sending claim.

with registry.cursor() as cr:
    work = api.Environment(cr, user_id, {})
    with patch('odoo.addons.blue_erp_interface.tools.transport.send') as send:
        work['blue.erp.event']._cron_dispatch()
        send.assert_not_called()
    event = work['blue.erp.event'].browse(crash_event_id)
    assert event.delivery_ids.state == 'unknown' and event.state == 'unknown'
    cr.commit()  # Own cursor: persist unknown, never silently reset it to pending.

# Two receivers start from the same old database snapshot. The gate row forces
# the native HTTP retry mechanism to refresh the second transaction.
import threading
from odoo.http.retrying import retrying

barrier = threading.Barrier(2)
received, errors = [], []

def receive_concurrently():
    try:
        with registry.cursor() as cr:
            worker = api.Environment(cr, user_id, {})
            target = worker['blue.erp.interface'].browse(interface.id)
            target.read(['kind'])
            barrier.wait(timeout=15)
            with mute_logger('odoo.sql_db'):
                received.append(retrying(lambda: target._receive(message(product.with_env(worker),
                    external_id='CONCURRENT-' + suffix)), worker, close_on_commit=False))
    except Exception as error:
        errors.append(type(error).__name__)

threads = [threading.Thread(target=receive_concurrently) for unused in range(2)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join(timeout=30)
assert not any(thread.is_alive() for thread in threads), 'Receiver did not finish'
assert not errors and len(received) == 2 and received[0] == received[1], (errors, received)
with registry.cursor() as cr:
    check = api.Environment(cr, user_id, {})
    assert check['blue.erp.document'].search_count([('interface_id', '=', interface.id),
        ('external_id', '=', 'CONCURRENT-' + suffix)]) == 1

print('ERP_DISPATCH_VALIDATION: ordered=2, duplicate_sends=0, durable_claim=True, crash_requires_reconciliation=True, concurrent_receivers_idempotent=True')
