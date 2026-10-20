import json

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.tools import consteq

from ..tools.contract import ProtocolError, bounded


class ErpReceive(http.Controller):
    @http.route('/blue_erp/v1/interfaces/<int:interface_id>/documents', type='http', auth='public', methods=['POST'], csrf=False)
    def receive_documents(self, interface_id):
        # Sudo only authenticates an exact configured interface. Business work uses its
        # manually authorized service user and a single company, without a sudo fallback.
        interface = request.env['blue.erp.interface'].sudo().browse(interface_id).exists()
        token = request.httprequest.headers.get('Authorization', '').removeprefix('Bearer ')
        if (not interface or not interface.active or not interface.connection_id.active
                or not interface.inbound_token or not consteq(token, interface.inbound_token)):
            return request.make_json_response({'error': 'unauthorized'}, status=401)
        if len(request.httprequest.data) > 262144:
            return request.make_json_response({'error': 'too_large'}, status=413)
        user = interface.connection_id.service_user_id
        if not user.active or interface.company_id not in user.company_ids or not user.has_group('stock.group_stock_user'):
            return request.make_json_response({'error': 'invalid_service_user'}, status=403)
        try:
            message = json.loads(request.httprequest.data)
            bounded(message)
            executor = interface.with_user(user).with_context(allowed_company_ids=[interface.company_id.id]).with_company(interface.company_id)
            with request.env.cr.savepoint():
                documents = executor._receive(message)
            return request.make_json_response({'accepted': True, 'documents': documents})
        except (ValueError, KeyError, TypeError, RecursionError, ProtocolError, UserError, ValidationError, AccessError):
            return request.make_json_response({'error': 'invalid_document', 'message': '报文、版本或业务校验失败,本批未建单.'}, status=409)
