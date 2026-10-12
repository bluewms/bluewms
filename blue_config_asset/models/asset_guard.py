from odoo.exceptions import AccessError

# An in-process capability, never serialized or accepted from RPC.
ASSET_TOKEN = object()


def check_internal(records):
    if records.env.context.get('blue_asset_token') is not ASSET_TOKEN:
        raise AccessError(records.env._('Use the validated policy workflow to create this record.'))
