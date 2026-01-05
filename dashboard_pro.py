"""Dashboard shim that delegates to dashboard.app and merges GenAI health into /api/health."""

from dashboard.app import app, add_camel_aliases
from starlette.requests import Request
from starlette.responses import JSONResponse
import json

try:
    from genai_module.api_endpoints import get_health_fragment, router as genai_router
except ImportError:
    # Fallback if genai endpoints not available
    def get_health_fragment():
        return {"genai": {"status": "unavailable", "error": "Module not imported"}}
    genai_router = None

# Mount genai router (exposes /genai/* endpoints)
if genai_router:
    try:
        app.include_router(genai_router)
    except Exception:
        # If app is not a FastAPI instance or include fails in some environments, skip silently
        pass

__all__ = ["app", "add_camel_aliases"]


# Middleware: intercept /api/health responses and merge genai health fragment
@app.middleware("http")
async def merge_genai_health(request: Request, call_next):
    """Call the underlying app, then merge GenAI health fragment into the response for /api/health.

    This avoids modifying external `dashboard.app` source and keeps the integration self-contained.
    """
    response = await call_next(request)

    # Only modify the main health endpoint
    if request.url.path != "/api/health":
        return response

    # Extract existing body from response (consume iterator if present)
    body_bytes = b""
    try:
        async for chunk in response.body_iterator:
            body_bytes += chunk
    except Exception:
        # Fallback to attribute access if iterator not available
        body_bytes = getattr(response, "body", b"") or b""

    try:
        content = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        content = {}

    try:
        genai_frag = get_health_fragment()
        if "genai" in genai_frag:
            content["genai"] = genai_frag["genai"]
            # If GenAI reports degraded, mark overall health as degraded and return 503
            if genai_frag["genai"].get("status") != "ok":
                content["status"] = "degraded"
                return JSONResponse(status_code=503, content=content)
    except Exception as e:
        # If fetching the fragment fails, surface it as degraded
        content.setdefault("genai", {})
        content["genai"]["status"] = "degraded"
        content["genai"]["error"] = str(e)
        content["status"] = "degraded"
        return JSONResponse(status_code=503, content=content)

    return JSONResponse(status_code=response.status_code, content=content)
