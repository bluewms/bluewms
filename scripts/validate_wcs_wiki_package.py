"""Validate offline Wiki publication material without any cloud writes."""
import hashlib
import json
import re
from pathlib import Path

if not env.cr.dbname.endswith('_test'):
    raise RuntimeError('Use an isolated test database.')
root = Path('/mnt/extra-addons')
fixtures = json.loads((root / 'blue_wcs_extension/tests/data/legacy_wcs_regression_cases.json').read_text())
wiki = root / 'docs/wiki/domains/wcs'
package = root / 'docs/wiki-publication/wcs-v4'
engine = env['blue.extension.contract']
assert json.loads((wiki / 'wcs-creation-v4-contract.json').read_text()) == engine._describe('wcs_creation/4')
recipes = (package / 'skill/resources/07-approved-wcs-examples.md').read_text()
count = 0
for name, fixture in fixtures.items():
    if not name.endswith('_v4'):
        continue
    key = name[len('template_'):-len('_v4')]
    body = (wiki / 'examples' / (key + '.md')).read_text()
    code = re.search(r'```python\n(.*?)```', body, re.S).group(1)
    cases = json.loads(re.search(r'```json\n(.*?)\n```', body, re.S).group(1))
    assert code == fixture['code_text']
    assert cases == json.loads(fixture['test_cases'])
    cloud_code = re.search(r'## wcs\.' + key + r' .*?```python\n(.*?)```', recipes, re.S).group(1)
    assert code == cloud_code
    for case in cases:
        assert engine._run(code, case['input'], 'wcs_creation/4') == case['expected_result']
        count += 1
manifest = json.loads((package / 'manifest.json').read_text())
for name, expected in manifest['files'].items():
    assert hashlib.sha256((package / name).read_bytes()).hexdigest() == expected['sha256'], name
assert manifest['cloud_writes_performed'] is False
print('WCS_WIKI_PACKAGE_RESULT=' + json.dumps({'examples': 10, 'cases': count, 'bundle_bytes': manifest['bundle_size_bytes'], 'cloud_written': False}))
