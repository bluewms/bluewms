from urllib.parse import urlsplit

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Restore category organization without losing any per-device credentials.
    for device in env['wcs.equipment'].search([('category_id', '=', False)]):
        parsed = urlsplit(device.endpoint or '')
        category = env['wcs.equipment.category'].create({
            'name': device.name + ' / 设备类别', 'company_id': device.company_id.id,
            'adapter_code': device.adapter_code, 'ip_post': (parsed.scheme + '://' + parsed.netloc) if parsed.netloc else False,
            'submit_path': parsed.path or '/rcs/rtas/api/robot/controller/task/submit',
            'app_key': device.api_key, 'app_secret': device.api_secret, 'callback_token': device.callback_token})
        device.category_id = category
