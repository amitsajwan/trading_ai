"""Enhanced Dashboard Pro - Complete Trading & GenAI Integration

Provides a unified dashboard that seamlessly combines:
- Advanced Trading Cockpit with signal management and position monitoring
- GenAI health monitoring and API endpoints
- Real-time system status and performance analytics

This is the complete dashboard solution for professional trading operations.
"""

from __future__ import annotations

from dashboard.app import app, add_camel_aliases
from starlette.requests import Request

from dashboard_pro_config import DASHBOARD_HOST, DASHBOARD_PORT
from dashboard_pro_genai import get_genai_router
from dashboard_pro_health import enrich_health_response


# Mount GenAI router (exposes /genai/* endpoints) if available
genai_router = get_genai_router()
if genai_router is not None:
    try:
        app.include_router(genai_router)
        print("GenAI router mounted successfully")
    except Exception as e:
        print(f"Failed to mount GenAI router: {e}")

# Trading cockpit is already included in dashboard.app, so no additional mounting needed
print("Trading Cockpit integrated successfully")

__all__ = ["app", "add_camel_aliases"]


# Middleware: intercept /api/health responses and merge GenAI + trading health fragments
@app.middleware("http")
async def merge_genai_health(request: Request, call_next):
    """Call the underlying app, then merge health fragments for /api/health.

    This avoids modifying external dashboard.app source and keeps the
    integration self-contained.
    """

    response = await call_next(request)

    # Only modify the main health endpoint paths we expose
    if request.url.path not in ("/api/health", "/health"):
        return response

    return await enrich_health_response(request, response)


if __name__ == "__main__":
    import uvicorn

    print("Starting Enhanced Dashboard Pro - Trading Cockpit + GenAI Integration")
    print(f"Available at: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print("Features:")
    print("  * Advanced Trading Cockpit with signal management")
    print("  * GenAI health monitoring and endpoints")
    print("  * Unified system status and analytics")
    print("  * Real-time position monitoring and risk management")
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)

