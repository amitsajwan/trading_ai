from fastapi import APIRouter, Body, HTTPException
import os
from typing import Optional

control_router = APIRouter(prefix="/api/control", tags=["control"])

# In-memory state for tests / minimal compatibility
CONTROL_STATE = {"mode": os.getenv("DEFAULT_MODE", "paper_mock"), "balance": 1000000.0}


@control_router.get("/status")
async def control_status():
    return {"mode": CONTROL_STATE["mode"], "database": "mock", "balance": CONTROL_STATE["balance"]}


@control_router.get("/mode/info")
async def control_mode_info():
    """
    UI uses this endpoint to decide whether to subscribe in LIVE vs HISTORICAL mode.

    Source of truth:
    - Redis keys set by start_local / historical runner:
      - system:execution_mode (LIVE/HISTORICAL)
      - system:run_id
    Fallback:
    - CONTROL_STATE for legacy/dev
    """
    try:
        import redis

        r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"),
                        port=int(os.getenv("REDIS_PORT", "6379")),
                        decode_responses=True)

        mode: str = (r.get("system:execution_mode") or "").upper() or str(CONTROL_STATE["mode"]).upper()
        run_id: Optional[str] = r.get("system:run_id")
        instrument: str = r.get("system:instrument") or "BANKNIFTY"

        return {
            "mode": mode,
            "run_id": run_id or "",
            "instrument": instrument,
            "source": "redis"
        }
    except Exception:
        # Don’t error → UI must not fall back to LIVE due to a 500/JSON parse error.
        return {
            "mode": str(CONTROL_STATE["mode"]).upper(),
            "run_id": "",
            "instrument": "BANKNIFTY",
            "source": "fallback"
        }


@control_router.get("/mode/auto-switch")
async def control_auto_switch():
    return {"auto_switch": False}


@control_router.post("/mode/switch")
async def control_mode_switch(payload: dict = Body(...)):
    mode = payload.get("mode")
    if not mode:
        raise HTTPException(status_code=400, detail="Missing mode")
    if mode == "live" and not payload.get("confirm"):
        return {"confirmation_required": True}
    CONTROL_STATE["mode"] = mode
    return {"success": True, "mode": mode}


@control_router.post("/mode/clear-override")
async def clear_override():
    CONTROL_STATE["mode"] = os.getenv("DEFAULT_MODE", "paper_mock")
    return {"success": True}


@control_router.get("/balance")
async def get_balance():
    return {"balance": CONTROL_STATE["balance"]}


@control_router.post("/balance/set")
async def set_balance(payload: dict = Body(...)):
    CONTROL_STATE["balance"] = float(payload.get("balance", CONTROL_STATE["balance"]))
    return {"success": True, "balance": CONTROL_STATE["balance"]}
