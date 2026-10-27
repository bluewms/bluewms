"""Build exact Wiki pages from the committed canonical knowledge tree.

The output contains logical scopes only, never deployment IDs or credentials.
Run local validation before building; the remote publisher owns backups,
standard API writes, indexing, read-back and approved metadata updates.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def build(root, date):
    wiki = root / 'docs/wiki'
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    changed = subprocess.check_output(['git', 'status', '--porcelain', '--', 'docs/wiki'], cwd=root, text=True)
    if changed:
        raise RuntimeError('Commit the validated Wiki tree before building a publication.')
    registry = json.loads((root / 'docs/architecture/native-wiki-knowledge-registry.json').read_text())
    books = []
    for book in registry['books']:
        scope = book['scope']
        pages, files = [], []
        for relative in book['sources']:
            path = wiki / relative
            source = path.read_text(encoding='utf-8')
            contracts = book['contracts']
            if scope == 'putaway':
                if path.name == 'same-batch-name.md' or 'v2-contract' in path.name:
                    contracts = ['putaway_policy/2']
                elif 'v1-contract' in path.name:
                    contracts = ['putaway_policy/1']
            ref = relative if path.suffix == '.md' else relative + '.md'
            title = source.splitlines()[0].lstrip('# ') if path.suffix == '.md' else '完整合同核对附件: ' + json.loads(source)['contract']
            body = source if path.suffix == '.md' else '# ' + title + '\n\n本附件用于合同核对,本实例当前 contract_schema 优先.\n\n```json\n' + source.rstrip() + '\n```\n'

            def link(match):
                label, target = match.groups()
                if not target or target.startswith(('https:', 'http:', 'mailto:', '#')):
                    return match.group(0)
                destination = (path.parent / target.split('#', 1)[0]).resolve().relative_to(wiki.resolve()).as_posix()
                destination_scope = destination.split('/')[1] if destination.startswith('domains/') else 'common'
                if scope != destination_scope:
                    return label + ' (在 ' + destination_scope + ' 库检索: ' + destination + ')'
                return '[' + label + '](' + target.replace('.json', '.json.md') + ')'

            body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, body)
            template = relative.startswith('templates/')
            reference = '/reference/' in relative
            metadata = {'id': scope + '.' + relative.replace('/', '.'), 'title': title,
                'type': 'reference', 'locked': True, 'knowledge_scope': scope,
                'contracts': contracts, 'knowledge_status': 'format_template' if template else 'reference' if reference else 'verified',
                'generation_ready': not template and not reference,
                'source_commit': revision, 'source_path': 'docs/wiki/' + relative,
                'source_sha256': sha(source)}
            terms = {'common': 'AI 合同 草稿 验证 发布 工具 权限', 'putaway': 'putaway_policy 上架 托盘 同单 批次号 容量',
                'wcs': 'wcs_creation WCS repeat relay lines tasks 数量 载具', 'erp': 'erp_mapping ERP 入库 出库 调拨 完成 盘点 幂等',
                'equipment': 'device_protocol 设备 HTTP TUSK 回调 位置', 'barcode': 'barcode_policy 条码 QR 扫描 GS1 批次 数量'}[scope]
            content = '---\n' + ''.join(key + ': ' + json.dumps(value, ensure_ascii=False) + '\n' for key, value in metadata.items()) + '---\n\n检索词: ' + terms + '\n\n' + body
            pages.append({'ref': ref, 'content': content})
            files.append({'source': 'docs/wiki/' + relative, 'ref': ref,
                          'source_sha256': sha(source), 'page_sha256': sha(content)})
        books.append({'scope': scope, 'name': book['display_name'], 'contracts': book['contracts'],
                      'generation_ready': True, 'pages': pages, 'files': files})
    return {'date': date, 'source_commit': revision, 'source_root': 'docs/wiki', 'books': books}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(Path(__file__).resolve().parents[1], args.date)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    args.output.chmod(0o600)
    print(json.dumps({'source_commit': result['source_commit'], 'books': {b['scope']: len(b['files']) for b in result['books']}}, ensure_ascii=False))
