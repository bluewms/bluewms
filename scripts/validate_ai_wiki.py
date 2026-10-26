"""Optional cross-repository Wiki validation; not an Odoo runtime dependency."""
import os
import runpy
from pathlib import Path

repo = Path(os.environ.get('BLUEWMS_WIKI_REPO', str(Path(__file__).resolve().parents[2] / 'bluewms-wiki')))
script = repo / 'scripts/validate_wiki.py'
if not script.is_file():
    raise RuntimeError('Clone the private bluewms-wiki sibling repository, or set BLUEWMS_WIKI_REPO.')
os.environ.setdefault('BLUEWMS_ODOO_ROOT', str(Path(__file__).resolve().parents[1]))
runpy.run_path(str(script), run_name='__main__', init_globals={'env': env} if 'env' in globals() else {})
