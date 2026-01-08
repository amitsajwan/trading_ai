# core_kernel top-level package shim
# This package exposes the implementation in `core_kernel/src/core_kernel/`.

from pathlib import Path
import os

# If a packaged implementation exists under `src/core_kernel`, prefer that
# implementation by adding it to the package search path. This allows `import
# core_kernel.contracts` to resolve correctly even when tests run from the
# repository root (where this top-level directory exists).
_try_src = Path(__file__).resolve().parent / "src" / "core_kernel"
if _try_src.exists():
    _src_path = str(_try_src)
    if _src_path not in __path__:
        __path__.insert(0, _src_path)

# End of shim


