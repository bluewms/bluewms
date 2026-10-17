from urllib.parse import urlsplit

import requests

from odoo.addons.blue_wcs_base.models.transport import TRANSPORTS


def send_wes(connection, payload):
    endpoint = connection['endpoint']
    token_url = connection['wes_token_url']
    if not endpoint or not token_url or not connection['wes_authorization'] or not connection['wes_app_id'] or not connection['wes_app_secret']:
        return 'failed', 'WES endpoint and token credentials are required.'
    if urlsplit(token_url).scheme not in ('http', 'https') or urlsplit(token_url).netloc != urlsplit(endpoint).netloc:
        return 'failed', 'WES token and task endpoints must use the same approved host.'
    headers = {'Authorization': connection['wes_authorization']}
    try:
        response = requests.post(token_url, data={'appId': connection['wes_app_id'], 'appSecret': connection['wes_app_secret']},
                                 headers=headers, timeout=(5, 20), allow_redirects=False)
        if response.status_code != 200 or len(response.content) > 65536:
            return 'failed', 'WES token retrieval failed; no task sent.'
        token = response.json().get('access_token')
        if not isinstance(token, str) or not token:
            return 'failed', 'WES token is missing; no task sent.'
    except (requests.RequestException, ValueError, AttributeError):
        return 'failed', 'WES authentication failed; no task sent.'
    try:
        response = requests.post(endpoint, json=payload, headers=dict(headers, **{'Blade-Auth': token}), timeout=(5, 20), allow_redirects=False)
        if response.status_code != 200 or len(response.content) > 262144:
            return 'unknown', 'WES task outcome requires reconciliation.'
        result = response.json()
        if isinstance(result, dict) and result.get('code') == 200:
            return 'accepted', 'WES accepted command.'
        return 'unknown', 'WES did not confirm acceptance; reconcile before retrying.'
    except (requests.RequestException, ValueError):
        return 'unknown', 'WES command outcome is unknown; reconcile before retrying.'


TRANSPORTS['wes'] = send_wes
