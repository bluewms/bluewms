import json

import requests

from odoo.addons.blue_wcs_base.models.transport import TRANSPORTS

from ..tools.protocol import ProtocolError, run_protocol, validate_headers


def send_protocol(connection, payload):
    headers = {'Content-Type': 'application/json'}
    templates = connection.get('protocol_headers', {})
    key_used = any('$app_key' in value for value in templates.values())
    if connection['auth_mode'] == 'headers':
        if connection['api_key']:
            headers[connection['key_header']] = connection['api_key']
        if connection['api_secret']:
            headers[connection['secret_header']] = connection['api_secret']
    elif connection['api_key'] and not key_used:
        headers['Authorization'] = 'Bearer ' + connection['api_key']
    for name, template in templates.items():
        if ('$app_key' in template and not connection['api_key']) or ('$app_secret' in template and not connection['api_secret']):
            continue
        headers[name] = template.replace('$app_key', connection['api_key']).replace('$app_secret', connection['api_secret'])
    try:
        validate_headers({key: value for key, value in headers.items() if key != 'Content-Type'})
        response = requests.post(connection['endpoint'], json=payload, headers=headers,
                                 timeout=(5, 20), allow_redirects=False, stream=True)
        try:
            if response.status_code != 200:
                return 'unknown', '设备响应未确认接受,请核对后处理.'
            chunks, length = [], 0
            for chunk in response.iter_content(8192):
                length += len(chunk)
                if length > 262144:
                    return 'unknown', '设备响应超出限制,请核对后处理.'
                chunks.append(chunk)
            body = json.loads(b''.join(chunks))
        finally:
            response.close()
        source = connection['protocol_input']
        data = {'request': {**source['request'], 'phase': 'response', 'http_status': 200, 'message': body},
                'candidates': source['candidates']}
        result = run_protocol(connection['protocol_code'], data)
        # Do not echo vendor response text, authentication or generated reasons into logs.
        return {'accepted': ('accepted', '设备已确认接受任务.'),
                'rejected': ('failed', '设备明确拒绝任务,请核对配置.'),
                'unknown': ('unknown', '设备未明确确认,请核对后处理.')}[result['state']]
    except (requests.RequestException, ValueError, ProtocolError):
        return 'unknown', '通信结果未知,请先核对设备,勿盲目重发.'


TRANSPORTS['protocol'] = send_protocol
