"""GenAI integration helpers for Enhanced Dashboard Pro.

This module isolates optional imports of genai_module so that
missing dependencies do not break the main dashboard.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:  # Optional GenAI router + health fragment
    from genai_module.api_endpoints import (  # type: ignore[import]
        get_health_fragment as _get_genai_health_fragment,
        router as genai_router,
    )
except Exception:  # pragma: no cover - graceful fallback
    genai_router = None  # type: ignore[assignment]

    def _get_genai_health_fragment() -> Dict[str, Any]:  # type: ignore[override]
        return {"genai": {"status": "unavailable", "error": "Module not imported"}}


def get_genai_router():
    """Return the GenAI router if available, else None.

    Using a helper avoids leaking optional imports into dashboard_pro.py.
    """

    return genai_router


def get_genai_health_fragment() -> Dict[str, Any]:
    """Return GenAI health fragment in a safe way.

    The structure is expected to look like::

        {"genai": {...}}
    """

    try:
        frag = _get_genai_health_fragment()
        return frag if isinstance(frag, dict) else {"genai": {"status": "error", "error": "Invalid fragment"}}
    except Exception as exc:  # pragma: no cover - defensive
        return {"genai": {"status": "error", "error": str(exc)}}

