"""Compatibility entrypoint; canonical publisher tools live in bluewms-wiki."""
import os
import runpy
from pathlib import Path

repo = Path(os.environ.get('BLUEWMS_WIKI_REPO', str(Path(__file__).resolve().parents[2] / 'bluewms-wiki')))
script = repo / 'scripts/build_knowledge_bundle.py'
if not script.is_file():
    raise SystemExit('Clone the private bluewms-wiki sibling repository, or set BLUEWMS_WIKI_REPO. Odoo runtime does not require it.')
runpy.run_path(str(script), run_name='__main__')
