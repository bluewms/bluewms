from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for device in env['wcs.equipment'].search([('adapter_code', '=', 'wes'), ('category_id', '!=', False)]):
        credentials = {key: device[key] for key in (
            'wes_authorization', 'wes_token_url', 'wes_app_id', 'wes_app_secret'
        ) if device[key] and not device.category_id[key]}
        if credentials:
            device.category_id.write(credentials)
