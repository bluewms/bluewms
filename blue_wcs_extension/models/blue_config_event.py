from odoo import fields, models


class BlueConfigEvent(models.Model):
    _inherit = 'blue.config.event'

    event_type = fields.Selection(selection_add=[('migration', '升级草稿')], ondelete={'migration': 'cascade'})
