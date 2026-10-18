"""Compatibility entry point: validate the current split Wiki publication package."""
from pathlib import Path

source = Path('/mnt/extra-addons/scripts/validate_wcs_wiki_package.py')
exec(compile(source.read_text(), str(source), 'exec'))
