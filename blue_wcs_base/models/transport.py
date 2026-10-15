"""Pure transport boundary. No database transaction spans an HTTP request."""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests


TRANSPORTS = {}

def send(connection, payload):
    if connection["adapter_code"] in TRANSPORTS:
        return TRANSPORTS[connection["adapter_code"]](connection, payload)
    if connection['adapter_code'] == 'simulation':
        return 'accepted', 'Simulation accepted; complete through the simulated event action.'
    if not connection['endpoint'] or not connection['api_key']:
        return 'failed', 'Device endpoint and credentials are required.'
    endpoint = connection['endpoint']
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + connection['api_key']}
    body = json.dumps(payload, ensure_ascii=False)
    if connection['adapter_code'] == 'hik':
        if not connection['api_secret']:
            return 'failed', 'HIK signing credentials are required.'
        url = urlsplit(endpoint)
        headers = {
            'Authorization': 'nonce="%s",method="HMAC-SHA256",timestamp="%s"' % (
                uuid.uuid4().hex[:8], datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')),
            'X-lr-appkey': connection['api_key'], 'X-lr-version': 'v1.0',
            'X-lr-request-id': uuid.uuid4().hex[:16], 'X-lr-trace-id': uuid.uuid4().hex,
            'X-lr-source': 'wms', 'Content-Type': 'application/json;charset=UTF-8', 'Host': url.netloc,
        }
        names = ('Authorization', 'Host', 'X-lr-appkey', 'X-lr-request-id', 'X-lr-source', 'X-lr-trace-id', 'X-lr-version')
        # This ordering follows the ZF HIK signature implementation.
        signing = 'POST %s HTTP/1.1\r\n' % (url.path or '/')
        signing += ''.join('%s: %s\r\n' % (name.upper(), headers[name]) for name in names if name in headers)
        signing += '\r\n' + body
        hashed = hmac.new(connection['api_secret'].encode(), signing.encode(), hashlib.sha256).hexdigest()
        endpoint += '?sign=' + hashlib.md5(hashed.encode()).hexdigest()[8:24]
    try:
        response = requests.post(endpoint, data=body.encode(), headers=headers, timeout=(5, 20), allow_redirects=False)
        # A proxy/error response does not establish that the device rejected the command.
        if response.status_code != 200 or len(response.content) > 262144:
            return 'unknown', 'Device response requires reconciliation.'
        result = response.json()
        if not isinstance(result, dict):
            return 'unknown', 'Invalid device response; reconcile before retrying.'
        accepted = result.get('code') == 'SUCCESS' if connection['adapter_code'] == 'hik' else result.get('accepted') is True
        return ('accepted', 'Device accepted command.') if accepted else ('unknown', 'No confirmed acceptance; reconcile before retrying.')
    except (requests.RequestException, ValueError):
        return 'unknown', 'Transport outcome is unknown; reconcile before retrying.'
