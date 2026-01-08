"""Health response merging helpers for Enhanced Dashboard Pro.

This module contains the logic for combining the base /api/health
response from dashboard.app with GenAI and trading health fragments.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from dashboard_pro_genai import get_genai_health_fragment
from dashboard_pro_trading import get_trading_health_fragment


async def enrich_health_response(request: Request, response: Response) -> Response:
    """Return a new Response that merges GenAI + trading health.

    Called only for the /api/health endpoint from middleware.
    """

    # Extract existing body from response (consume iterator if present)
    body_bytes = b""
    try:
        if hasattr(response, "body_iterator") and response.body_iterator is not None:
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body_bytes += chunk
        else:
            body_bytes = getattr(response, "body", b"") or b""
    except Exception:
        body_bytes = getattr(response, "body", b"") or b""

    try:
        content: Dict[str, Any] = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        content = {}

    # Merge GenAI fragment
    genai_frag = get_genai_health_fragment()
    genai_data = genai_frag.get("genai") if isinstance(genai_frag, dict) else None
    if isinstance(genai_data, dict):
        content["genai"] = genai_data
        genai_status = genai_data.get("status")
        # Only mark as degraded if GenAI is in an actual error state
        if genai_status == "error":
            content["status"] = "degraded"

    # Merge trading health fragment
    trading_frag = await get_trading_health_fragment()
    trading_data = trading_frag.get("trading") if isinstance(trading_frag, dict) else None
    if isinstance(trading_data, dict):
        content["trading"] = trading_data
        if trading_data.get("status") == "error":
            content["status"] = "degraded"

    return JSONResponse(status_code=getattr(response, "status_code", 200), content=content)

