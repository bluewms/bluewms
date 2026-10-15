from odoo import fields, models


class WcsEquipmentCategory(models.Model):
    _inherit = 'wcs.equipment.category'

    adapter_code = fields.Selection(selection_add=[('wes', 'WES VZF')], ondelete={'wes': 'set default'})
    wes_authorization = fields.Char('WES Authorization', groups='base.group_system', copy=False)
    wes_token_url = fields.Char('WES Token URL', groups='base.group_system')
    wes_app_id = fields.Char('WES App ID', groups='base.group_system', copy=False)
    wes_app_secret = fields.Char('WES App Secret', groups='base.group_system', copy=False)
