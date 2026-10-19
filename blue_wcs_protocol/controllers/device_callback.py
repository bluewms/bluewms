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
            if category_id and (not category or category.adapter_code != 'protocol'):
                return request.make_json_response({'error': 'wrong_category'}, status=403)
            # Locate only exact existing opaque task IDs, independent of vendor JSON keys.
            # The pinned parser must then confirm that same ID and completion meaning.
            values, pending = set(), [message]
            while pending:
                value = pending.pop()
                if type(value) is dict:
                    pending.extend(value.values())
                elif type(value) is list:
                    pending.extend(value)
                elif type(value) is str and 1 <= len(value) <= 128:
                    values.add(value)
                    if len(values) > 200:
                        raise ValueError('Too many callback values')
            domain = [('name', 'in', sorted(values)), ('protocol_release_id', '!=', False)]
            if category_id:
                domain.append(('protocol_category_id', '=', category_id))
            tasks = request.env['wcs.request'].sudo().search(domain, limit=2)
            if len(tasks) != 1:
                return request.make_json_response({'error': 'unknown_or_ambiguous_task'}, status=404)
            candidate = tasks.with_company(tasks.company_id)
            pinned = candidate.protocol_category_id
            if (not pinned or pinned.company_id != candidate.company_id or pinned.adapter_code != 'protocol'
                    or (category_id and pinned.id != category_id)):
                return request.make_json_response({'error': 'wrong_category'}, status=403)
            if pinned.callback_token:
                token = request.httprequest.headers.get('Authorization', '').removeprefix('Bearer ')
                if not consteq(token, pinned.callback_token):
                    return request.make_json_response({'error': 'unauthorized'}, status=401)
            # Do not alter an existing task when callback credentials failed.
            task = candidate
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
