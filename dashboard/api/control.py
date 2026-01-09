from fastapi import APIRouter, Body, HTTPException
import os

control_router = APIRouter(prefix="/api/control", tags=["control"])

# In-memory state for tests / minimal compatibility
CONTROL_STATE = {"mode": os.getenv("DEFAULT_MODE", "paper_mock"), "balance": 1000000.0}


@control_router.get("/status")
async def control_status():
    return {"mode": CONTROL_STATE["mode"], "database": "mock", "balance": CONTROL_STATE["balance"]}


@control_router.get("/mode/info")
async def control_mode_info():
    return {"mode": CONTROL_STATE["mode"], "database": "mock"}


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
