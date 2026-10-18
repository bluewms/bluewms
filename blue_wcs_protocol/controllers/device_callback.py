import json

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import consteq

from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN

from ..tools.protocol import ProtocolError, bounded


class DeviceCallback(http.Controller):
    @http.route('/api/blue_wcs_tusk/feedbackTask', type='http', auth='public', methods=['POST'], csrf=False)
    def tusk_callback(self):
        return self._receive(legacy=True)

    @http.route('/blue_wcs/v1/categories/<int:category_id>/callback', type='http', auth='public', methods=['POST'], csrf=False)
    def category_callback(self, category_id):
        return self._receive(category_id=category_id)

    def _receive(self, category_id=None, legacy=False):
        # The user explicitly requires the old unauthenticated TUSK webhook.
        # Sudo is limited to an exact existing random task ID, then pinned category/company.
        if len(request.httprequest.data) > 65536:
            return request.make_json_response({'error': 'too_large'}, status=413)
        task = None
        try:
            message = json.loads(request.httprequest.data)
            bounded(message)
            if type(message) is not dict:
                raise ValueError('Expected an object')
            category = request.env['wcs.equipment.category'].sudo().browse(category_id).exists() if category_id else None
            key = 'taskId' if legacy else (category.protocol_task_key if category else '')
            name = message.get(key)
            if type(name) is not str or not 1 <= len(name) <= 128:
                raise ValueError('Missing bounded task identifier')
            tasks = request.env['wcs.request'].sudo().search([
                ('name', '=', name), ('protocol_release_id', '!=', False)], limit=2)
            if len(tasks) != 1:
                return request.make_json_response({'error': 'unknown_task'}, status=404)
            task = tasks.with_company(tasks.company_id)
            pinned = task.protocol_category_id
            if (not pinned or pinned.company_id != task.company_id or pinned.adapter_code != 'protocol'
                    or (legacy and not pinned.protocol_tusk_compat) or (category_id and pinned.id != category_id)):
                return request.make_json_response({'error': 'wrong_category'}, status=403)
            if pinned.protocol_callback_mode == 'bearer':
                token = request.httprequest.headers.get('Authorization', '').removeprefix('Bearer ')
                if not pinned.callback_token or not consteq(token, pinned.callback_token):
                    return request.make_json_response({'error': 'unauthorized'}, status=401)
            with request.env.cr.savepoint():
                response = task._protocol_receive(message)
            return request.make_json_response(response)
        except (ValueError, KeyError, TypeError, RecursionError, ProtocolError, UserError, ValidationError):
            if task and task.state in ('sending', 'accepted', 'running', 'unknown'):
                # Keep failure outside the rolled-back event transaction; never complete on bad mappings.
                task._lock()
                task.with_context(blue_wcs_token=WCS_TOKEN).write({
                    'state': 'unknown', 'last_result': '设备完成回调或位置映射未通过校验,请核对后重放有效回报.'})
            return request.make_json_response({'error': 'invalid_callback', 'message': '回调未通过校验,任务未确认完成.'}, status=409)
