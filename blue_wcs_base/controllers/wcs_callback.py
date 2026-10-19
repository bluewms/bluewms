import json

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import consteq


class WcsCallback(http.Controller):
    @http.route('/blue_wcs/v1/devices/<int:device_id>/events', type='http', auth='public', methods=['POST'], csrf=False)
    def device_event(self, device_id):
        # Deliberate narrow sudo: authenticate a specific configured device before
        # looking up any task, then restrict every lookup to that same device/company.
        device = request.env['wcs.equipment'].sudo().browse(device_id).exists()
        token = request.httprequest.headers.get('Authorization', '').removeprefix('Bearer ')
        if not device or not device.active or not (device.callback_token or device.category_id.callback_token) or not consteq(token, device.callback_token or device.category_id.callback_token):
            return request.make_json_response({'error': 'unauthorized'}, status=401)
        if len(request.httprequest.data) > 65536:
            return request.make_json_response({'error': 'too_large'}, status=413)
        try:
            data = json.loads(request.httprequest.data)
            if type(data) is not dict or set(data) - {'task_id', 'event_id', 'event', 'point', 'actual_destination'} or not all(type(value) is str and len(value) <= 256 for value in data.values()):
                raise ValueError('Invalid schema')
            task = request.env['wcs.request'].sudo().search([
                ('name', '=', data['task_id']), ('equipment_id', '=', device.id), ('company_id', '=', device.company_id.id)], limit=1)
            if not task:
                return request.make_json_response({'error': 'unknown_task'}, status=404)
            with request.env.cr.savepoint():
                task._receive_event(data['event_id'], data['event'], data.get('point', ''), data.get('actual_destination', ''))
        except (ValueError, KeyError, UserError, ValidationError):
            return request.make_json_response({'error': 'invalid_event'}, status=400)
        return request.make_json_response({'accepted': True})

    @http.route('/api/blue_wcs_hik/reporter/task', type='http', auth='public', methods=['POST'], csrf=False)
    def hik_event(self):
        import hashlib
        if len(request.httprequest.data) > 65536:
            return request.make_json_response({'error': 'too_large'}, status=413)
        try:
            data = json.loads(request.httprequest.data)
            task_code = data['robotTaskCode']
            if type(task_code) is not str or len(task_code) > 128:
                raise ValueError('Invalid task ID')
            task = request.env['wcs.request'].sudo().search([('name', '=', task_code)], limit=1)
            device = task.equipment_id
            token = request.httprequest.headers.get('Authorization', '').removeprefix('Bearer ')
            if not task or device.adapter_code != 'hik' or not device.active or not (device.callback_token or device.category_id.callback_token) or not consteq(token, device.callback_token or device.category_id.callback_token):
                return request.make_json_response({'error': 'unauthorized'}, status=401)
            values = data['extra']['values']
            event = values['method']
            event_id = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            with request.env.cr.savepoint():
                task._receive_event(event_id, event, str(values.get('pointCode', values.get('slotCode', ''))),
                                    str(values.get('slotCode', '')) if event == 'end' else '')
        except (ValueError, KeyError, TypeError, UserError, ValidationError):
            return request.make_json_response({'error': 'invalid_event'}, status=400)
        return request.make_json_response({'code': 'SUCCESS', 'message': 'success', 'data': {'robotTaskCode': task_code}})
