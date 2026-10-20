import copy
import json

import requests

from .contract import ProtocolError, run_mapping, validate_headers


def send(connection, operation, body, templates, code, snapshot):
    headers = {'Content-Type': 'application/json', 'Idempotency-Key': connection['idempotency_key']}
    if connection['auth_mode'] == 'bearer' and connection['app_key']:
        headers['Authorization'] = 'Bearer ' + connection['app_key']
    for name, value in templates.items():
        if ('$app_key' in value and not connection['app_key']) or ('$app_secret' in value and not connection['app_secret']):
            return 'failed', ''
        headers[name] = value.replace('$app_key', connection['app_key']).replace('$app_secret', connection['app_secret'])
    try:
        validate_headers({key: value for key, value in headers.items() if key != 'Content-Type'})
    except ProtocolError:
        return 'failed', ''
    try:
        response = requests.post(connection['url'], json=body, headers=headers, timeout=(5, 20),
                                 allow_redirects=False, stream=True)
        try:
            if not 200 <= response.status_code < 300:
                return 'unknown', ''
            chunks, size = [], 0
            for chunk in response.iter_content(8192):
                size += len(chunk)
                if size > 262144:
                    return 'unknown', ''
                chunks.append(chunk)
            message = json.loads(b''.join(chunks))
            if type(message) is not dict:
                return 'unknown', ''
            payload = copy.deepcopy(snapshot)
            payload['request'].update(phase='response', message=message, http_status=response.status_code, operation=operation)
            result = run_mapping(code, payload)
            return {'accepted': 'done', 'rejected': 'failed', 'unknown': 'unknown'}[result['state']], result['external_number']
        finally:
            response.close()
    except (requests.RequestException, ValueError, ProtocolError):
        return 'unknown', ''
