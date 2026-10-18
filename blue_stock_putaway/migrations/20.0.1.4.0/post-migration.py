"""Retire shipped examples without touching policy drafts, versions or releases."""

import hashlib

from odoo import SUPERUSER_ID, api


SHIPPED_DIGESTS = {'blue_scene_template_same_batch_name': {'code_text': '9972e3339b33b2e6d6f413d9b93c8267df90ee25ea261df073abbd53ea538a93',
                                         'requirements': '74bb09f086cd4349c8e972de17d30447b22b39240694889059f4c3d7fe825883',
                                         'test_cases': 'c121f3a0430eb2e3c52e95d3b500153be526a01ef14e2c54c80b4104c5eedcb3'},
 'blue_scene_template_same_lot': {'code_text': 'ecc86171c6e7de25321a05fe14baedb32e8a9e205ccf4e284e7f64694fbc923d',
                                  'requirements': 'f5540f2b8ceb053e5ecf3ef6a83296dba3b24c7988570cb4e585d4d17c37a7d1',
                                  'test_cases': '3df6423dd01e4f7e477ad6be8198c6c7acbd35b4ebdc34532b1336727ac676e4'},
 'blue_scene_template_same_picking': {'code_text': 'ec0ec15aeb7b7e58f60223ad7fa435c2ebd23482dce02e937759ecd2bf5c2131',
                                      'requirements': '707a4fa732ce09761dfd6311a20a7567678dd47af33d92328201ca0783f45214',
                                      'test_cases': '3df6423dd01e4f7e477ad6be8198c6c7acbd35b4ebdc34532b1336727ac676e4'}}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xml_id, digests in SHIPPED_DIGESTS.items():
        definition = env.ref('blue_stock_putaway.' + xml_id, raise_if_not_found=False)
        if not definition:
            continue
        values = {'cloud_managed': True, 'active': False}
        for field, expected in digests.items():
            # Preserve administrator-modified legacy content for manual recovery.
            if hashlib.sha256((definition[field] or '').encode()).hexdigest() == expected:
                values[field] = False
        definition.write(values)
