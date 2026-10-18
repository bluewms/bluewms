"""Regression-only legacy data; never installed or supplied to the production AI tools."""
import json

from odoo.tools import file_open


def load_legacy_examples(env):
    with file_open('blue_wcs_extension/tests/data/legacy_wcs_regression_cases.json') as source:
        fixtures = json.load(source)
    for xml_id, values in fixtures.items():
        env.ref('blue_wcs_extension.' + xml_id).write(dict(values, cloud_managed=False))
    return fixtures
