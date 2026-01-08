"""Project-local site customization to make `*/src` packages importable.

This is a convenience for running pytest and Python tools from the repository root
without requiring developers to set PYTHONPATH or do editable installs.
"""
from pathlib import Path
import sys

_root = Path(__file__).resolve().parent
for child in _root.iterdir():
    src = child / "src"
    if src.is_dir():
        p = str(src)
        if p not in sys.path:
            sys.path.insert(0, p)
# Ensure repo root is on path
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
