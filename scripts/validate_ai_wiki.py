"""Check canonical AI Wiki examples against the installed bounded engines.

Run through Odoo shell in an isolated database ending in _test, or use
--offline for the same pure interpreters without database/business validation.
This script neither writes cloud knowledge nor publishes business strategies.
"""
import hashlib
import json
import re
import importlib
import sys
import types
from pathlib import Path

def offline_engine(root):
    """Load the same pure interpreter modules without importing Odoo models.

    Namespace packages only resolve the helpers' normal import paths. They do
    not simulate an Environment, ORM or business service.
    """
    namespaces = {'odoo': None, 'odoo.addons': None}
    for addon in ('blue_extension_contract', 'blue_wcs_extension', 'blue_wcs_protocol',
                  'blue_erp_interface', 'blue_barcode_extension'):
        namespaces['odoo.addons.' + addon] = root / addon
        for sub in ('tools', 'models'):
            namespaces['odoo.addons.' + addon + '.' + sub] = root / addon / sub
    for name, path in namespaces.items():
        module = types.ModuleType(name)
        module.__path__ = [str(path)] if path else []
        sys.modules[name] = module
    prefix = 'odoo.addons.'
    policy = importlib.import_module(prefix + 'blue_extension_contract.tools.policy')
    putaway = importlib.import_module(prefix + 'blue_extension_contract.tools.schema')
    wcs = importlib.import_module(prefix + 'blue_wcs_extension.models.creation_v4')
    wcs_schema = importlib.import_module(prefix + 'blue_wcs_extension.models.creation_v4_schema')
    device = importlib.import_module(prefix + 'blue_wcs_protocol.tools.protocol')
    erp = importlib.import_module(prefix + 'blue_erp_interface.tools.contract')
    barcode = importlib.import_module(prefix + 'blue_barcode_extension.tools.contract')

    class Engine:
        def _run(self, code, payload, contract):
            if contract.startswith('putaway_policy/'):
                return policy.run_policy(code, payload)
            return {'wcs_creation/4': wcs.run_creation_v4,
                    'device_protocol/1': device.run_protocol,
                    'erp_mapping/1': erp.run_mapping,
                    'barcode_policy/1': barcode.run_barcode}[contract](code, payload)

        def _describe(self, contract):
            if contract.startswith('putaway_policy/'):
                return putaway.putaway_schema(contract)
            return {'wcs_creation/4': wcs_schema.creation_schema_v4,
                    'device_protocol/1': device.protocol_schema,
                    'erp_mapping/1': erp.mapping_schema,
                    'barcode_policy/1': barcode.schema}[contract]()
    return Engine()


if 'env' in globals():
    if not env.cr.dbname.endswith('_test'):
        raise RuntimeError('Use an isolated test database.')
    root = Path('/mnt/extra-addons')
    engine = env['blue.extension.contract']
    has_erp = 'blue.erp.interface' in env
    has_barcode = bool(env['ir.module.module'].search_count([
        ('name', '=', 'blue_barcode_extension'), ('state', '=', 'installed')]))
    mode = 'isolated_odoo'
else:
    if sys.argv[1:] != ['--offline']:
        raise RuntimeError('Use Odoo shell in an isolated database, or pass --offline for pure data checks.')
    root = Path(__file__).resolve().parents[1]
    engine = offline_engine(root)
    has_erp = has_barcode = True
    mode = 'offline_pure_interpreters'
wiki = root / 'docs/wiki'
for version in (1, 2):
    assert json.loads((wiki / ('domains/putaway/putaway-policy-v%s-contract.json' % version)).read_text()) == engine._describe('putaway_policy/%s' % version)
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

if has_erp:
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

if has_barcode:
    assert json.loads((wiki / 'domains/barcode/barcode-policy-v1-contract.json').read_text()) == engine._describe('barcode_policy/1')
    for name, filename in [('delimiter-qr', 'delimiter_qr.json'), ('native-and-qr', 'native_qr.json')]:
        fixture = json.loads((root / 'blue_barcode_extension/tests/data' / filename).read_text())
        path = wiki / 'domains/barcode/examples' / (name + '.md')
        body = path.read_text()
        code = re.search(r'```python\n(.*?)```', body, re.S).group(1)
        cases = json.loads(re.search(r'```json\n(.*?)\n```', body, re.S).group(1))
        assert code == fixture['code'] and cases == fixture['cases'], path
        for case in cases:
            assert engine._run(code, case['input'], 'barcode_policy/1') == case['expected_result'], (path, case['name'])
        results.append({'page': str(path.relative_to(wiki)), 'contract': 'barcode_policy/1',
                        'code_sha256': hashlib.sha256(code.encode()).hexdigest(), 'cases': len(cases)})

for path in wiki.rglob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        target = target.split('#', 1)[0]
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        resolved = (path.parent / target).resolve()
        assert resolved.is_relative_to(wiki.resolve()) and resolved.is_file(), (path, target)

print('AI_WIKI_VALIDATION=' + json.dumps({'mode': mode, 'examples': len(results), 'cases': sum(r['cases'] for r in results),
                                        'contract_matches': True, 'links_valid': True, 'results': results}))
