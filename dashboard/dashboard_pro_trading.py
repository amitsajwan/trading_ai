"""Trading health helpers for Enhanced Dashboard Pro.

This module wraps the trading health integration from dashboard.app so
that the main dashboard_pro entrypoint can stay small and focused.
"""

from __future__ import annotations

from typing import Any, Dict
import inspect

try:
    # dashboard.app provides an async get_trading_health() helper
    from dashboard.app import get_trading_health as _get_trading_health  # type: ignore[import]
except Exception:  # pragma: no cover - fallback when dashboard is minimal
    _get_trading_health = None  # type: ignore[assignment]


async def get_trading_health_fragment() -> Dict[str, Any]:
    """Return trading health fragment for inclusion in /api/health.

    The structure is expected to look like::

        {"trading": {...}}

    If the underlying dashboard.app helper is not available, this
    returns a simple "unavailable" structure instead of raising.
    """

    # If dashboard.app did not expose the helper, return a basic fragment
    if _get_trading_health is None:
        return {
            "trading": {
                "status": "unavailable",
                "error": "Trading module not initialized",
            }
        }

    # Handle both async and sync implementations defensively
    try:
        if inspect.iscoroutinefunction(_get_trading_health):
            return await _get_trading_health()  # type: ignore[misc]

        # Synchronous implementation (older versions) – call directly
        result = _get_trading_health()  # type: ignore[call-arg]
        return result if isinstance(result, dict) else {
            "trading": {"status": "error", "error": "Invalid trading health structure"}
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "trading": {
                "status": "error",
                "error": str(exc),
            }
        }

