"""Validate uploadable WCS knowledge against the actual interpreter, on *_test only."""
import json
import re
from pathlib import Path

if not env.cr.dbname.endswith('_test'):
    raise RuntimeError('Use an isolated *_test database.')
root = Path('/mnt/extra-addons')
body = (root / 'docs/knowledge/wcs-ai-creation-v3-zh.md').read_text()
examples = json.loads((root / 'docs/knowledge/wcs-ai-creation-examples.json').read_text())
spec = env['blue.extension.contract']._describe('wcs_creation/3')
assert json.loads((root / 'docs/knowledge/wcs-creation-v3-contract.json').read_text()) == spec
assert json.loads(re.search(r'## 附录 A\..*?```json\n(.*?)\n```', body, re.S).group(1)) == spec
records = json.loads((root / 'blue_wcs_extension/tests/data/legacy_wcs_regression_cases.json').read_text())
cases = 0
for section, example in zip(body.split('## 附录 B.')[1:], examples, strict=True):
    code = re.search(r'```python\n(.*?)```', section, re.S).group(1)
    trials = json.loads(re.search(r'```json\n(.*?)\n```', section, re.S).group(1))
    record = records['template_' + example['key'] + '_v3']
    assert code == example['code'] == record['code_text']
    assert trials == example['tests'] == json.loads(record['test_cases'])
    for case in trials:
        assert env['blue.extension.contract']._run(code, case['input'], 'wcs_creation/3') == case['expected_result'], case['name']
        cases += 1
try:
    from jsonschema import Draft202012Validator
except ImportError:
    schema_check = 'jsonschema unavailable; structural and interpreter checks completed'
else:
    Draft202012Validator.check_schema(spec['input'])
    picking = env['wcs.plan'].search([('snapshot', 'like', 'wcs_creation/3')], limit=1).picking_id
    assert picking, 'Run the synthetic concurrency fixture first.'
    payload = picking._wcs_payload(picking.move_line_ids, {line.id: line.quantity for line in picking.move_line_ids})
    Draft202012Validator(spec['input']).validate(payload)
    schema_check = 'production payload and JSON Schema passed'
print('WCS_KNOWLEDGE_RESULT=' + json.dumps({'examples': len(examples), 'cases': cases, 'schema': schema_check}, ensure_ascii=False))
