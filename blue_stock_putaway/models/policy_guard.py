from odoo.exceptions import AccessError

POLICY_TOKEN = object()


def check_internal(records):
    if records.env.context.get('blue_putaway_token') is not POLICY_TOKEN:
        raise AccessError(records.env._('Policy execution fields cannot be supplied directly.'))
