"""Trading Dashboard Package.

This package intentionally exposes a small shim that uses `app_minimal`.
The shim registers `dashboard.app` in sys.modules so other modules that
perform `from dashboard.app import ...` will receive the minimal stub
implementation during this recovery/debug session.
"""
import sys
from . import app_minimal as _app_minimal

# Expose commonly-imported symbols
app = _app_minimal.app
add_camel_aliases = _app_minimal.add_camel_aliases
start_historical_replay = _app_minimal.start_historical_replay
technical_indicators = _app_minimal.technical_indicators

# Ensure `import dashboard.app` returns the minimal module
sys.modules.setdefault('dashboard.app', _app_minimal)

__all__ = ["app", "add_camel_aliases", "start_historical_replay", "technical_indicators"]

