"""Check canonical AI Wiki examples against the installed bounded engines.

Run through Odoo shell in an isolated database ending in _test.
This script neither writes cloud knowledge nor publishes business strategies.
"""
import hashlib
import json
import re
from pathlib import Path

if not env.cr.dbname.endswith('_test'):
    raise RuntimeError('Use an isolated test database.')

root = Path('/mnt/extra-addons')
wiki = root / 'docs/wiki'
engine = env['blue.extension.contract']
assert json.loads((wiki / 'domains/wcs/wcs-creation-v4-contract.json').read_text()) == engine._describe('wcs_creation/4')
assert json.loads((wiki / 'domains/equipment/device-protocol-v1-contract.json').read_text()) == engine._describe('device_protocol/1')
results = []
domains = [
    ('putaway', 'blue_stock_putaway/tests/data/putaway_regression_cases.json', {
        'same-lot': ('blue_scene_template_same_lot', 'putaway_policy/1'),
        'same-picking': ('blue_scene_template_same_picking', 'putaway_policy/1'),
        'same-batch-name': ('blue_scene_template_same_batch_name', 'putaway_policy/2'),
    }),
    ('wcs', 'blue_wcs_extension/tests/data/legacy_wcs_regression_cases.json', {
        key: ('template_' + key + '_v4', 'wcs_creation/4')
        for key in ['ready', 'repeat', 'triple', 'filter', 'all_picked', 'container', 'weight', 'scope', 'relay', 'empty']
    }),
]
for domain, fixture_path, examples in domains:
    fixtures = json.loads((root / fixture_path).read_text())
    for name, (fixture_name, contract) in examples.items():
        path = wiki / 'domains' / domain / 'examples' / (name + '.md')
        body = path.read_text()
        code = re.search(r'```python\n(.*?)```', body, re.S).group(1)
        cases = json.loads(re.search(r'```json\n(.*?)\n```', body, re.S).group(1))
        fixture = fixtures[fixture_name]
        assert code == fixture['code_text'], path
        assert cases == json.loads(fixture['test_cases']), path
        for case in cases:
            actual = engine._run(code, case['input'], contract)
            expected = case['expected_result'] if domain == 'wcs' else case['expected_order']
            if domain == 'putaway':
                actual = [row['location_id'] for row in actual]
            assert actual == expected, (path, case['name'])
        results.append({'page': str(path.relative_to(wiki)), 'contract': contract,
                        'code_sha256': hashlib.sha256(code.encode()).hexdigest(), 'cases': len(cases)})

fixtures = json.loads((root / 'blue_wcs_protocol/tests/data/protocol_regression_cases.json').read_text())
for name, fixture in fixtures.items():
    path = wiki / 'domains/equipment/examples' / (name + '.md')
    body = path.read_text()
    code = re.search(r'```python\n(.*?)```', body, re.S).group(1)
    cases = json.loads(re.search(r'```json\n(.*?)\n```', body, re.S).group(1))
    assert code == fixture['code'] and cases == fixture['cases'], path
    for case in cases:
        assert engine._run(code, case['input'], 'device_protocol/1') == case['expected_result'], (path, case['name'])
    results.append({'page': str(path.relative_to(wiki)), 'contract': 'device_protocol/1',
                    'code_sha256': hashlib.sha256(code.encode()).hexdigest(), 'cases': len(cases)})

if 'blue.erp.interface' in env:
    assert json.loads((wiki / 'domains/erp/erp-mapping-v1-contract.json').read_text()) == engine._describe('erp_mapping/1')
    erp = json.loads((root / 'blue_erp_interface/tests/data/mapping.json').read_text())
    for name, key in [('inbound-completion', 'cases'), ('inventory-difference', 'inventory_cases')]:
        path = wiki / 'domains/erp/examples' / (name + '.md')
        body = path.read_text()
        code = re.search(r'```python\n(.*?)```', body, re.S).group(1)
        cases = json.loads(re.search(r'```json\n(.*?)\n```', body, re.S).group(1))
        assert code == erp['code'] and cases == erp[key], path
        for case in cases:
            assert engine._run(code, case['input'], 'erp_mapping/1') == case['expected_result'], (path, case['name'])
        results.append({'page': str(path.relative_to(wiki)), 'contract': 'erp_mapping/1',
                        'code_sha256': hashlib.sha256(code.encode()).hexdigest(), 'cases': len(cases)})

for path in wiki.rglob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        target = target.split('#', 1)[0]
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        resolved = (path.parent / target).resolve()
        assert resolved.is_relative_to(wiki.resolve()) and resolved.is_file(), (path, target)

print('AI_WIKI_VALIDATION=' + json.dumps({'examples': len(results), 'cases': sum(r['cases'] for r in results),
                                        'contract_matches': True, 'links_valid': True, 'results': results}))
