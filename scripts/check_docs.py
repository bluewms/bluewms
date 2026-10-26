"""Check maintained Markdown links; immutable upstream README is excluded."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
files = [*root.glob('README*.md'), *root.glob('blue_*/README.md'),
         *root.glob('blue_*/NOTICE.md'), *root.glob('docker/README.md'), *root.glob('scripts/README.md'),
         *(root / 'docs').rglob('*.md')]
files = [p for p in files if p.name != 'MuK-upstream-README.md']
errors = []
links = 0
for path in files:
    body = path.read_text(encoding='utf-8')
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', body):
        if target.startswith(('http:', 'https:', 'mailto:', 'data:')):
            continue
        target = target.split(' "', 1)[0].strip('<>')
        file, _, anchor = target.partition('#')
        resolved = (path.parent / unquote(file)).resolve() if file else path
        links += 1
        if not resolved.exists():
            errors.append('%s: %s' % (path.relative_to(root), target))
for error in errors:
    print(error, file=sys.stderr)
print('DOC_LINKS files=%s local_links=%s missing=%s' % (len(files), links, len(errors)))
raise SystemExit(bool(errors))
