from odoo import api, fields, models

from .guard import protect


class BlueBarcodeEvent(models.Model):
    _name = 'blue.barcode.event'
    _description = '已确认的条码事件'
    _order = 'id desc'

    session_id = fields.Many2one('blue.barcode.session', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='session_id.company_id', store=True)
    user_id = fields.Many2one(related='session_id.user_id', store=True)
    event_key = fields.Char(required=True)
    payload_hash = fields.Char(required=True)
    result = fields.Json(required=True)

    _unique_event = models.Constraint('UNIQUE(session_id,event_key)', '此扫描事件已经处理.')

    @api.model_create_multi
    def create(self, vals_list):
        protect(self)
        return super().create(vals_list)

    def write(self, vals):
        protect(self)
        return super().write(vals)

    def unlink(self):
        protect(self)
        return super().unlink()
