"""Compatibility shim for `ui_shell` package.

The real implementation was moved to `dashboard/ui/ui_shell`. This shim
re-exports the public API for backwards compatibility with existing
imports and tests.
"""

import os

# Allow submodule imports like `ui_shell.api` to resolve to dashboard/ui/ui_shell
try:
    alt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard", "ui", "ui_shell"))
    if os.path.isdir(alt):
        __path__.insert(0, alt)
except Exception:
    pass

try:
    from dashboard.ui import ui_shell as _impl  # type: ignore
    # Re-export public symbols
    from dashboard.ui.ui_shell import *  # noqa: F401,F403
    __all__ = getattr(_impl, "__all__", [])
except Exception:
    # If the new location is not importable, provide a helpful error
    raise ImportError("ui_shell package moved to dashboard.ui.ui_shell; ensure package is installed or PYTHONPATH is configured accordingly")
