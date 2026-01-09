from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)

trading_router = APIRouter(prefix="/api/trading", tags=["trading"])

_trading_signals: list[dict] = []

# Try to get SignalMonitor instance (global singleton)
_signal_monitor = None
try:
    # Add engine_module to path
    engine_path = os.path.join(os.path.dirname(__file__), "..", "..", "engine_module", "src")
    if engine_path not in sys.path:
        sys.path.insert(0, engine_path)
    
    from engine_module.signal_monitor import get_signal_monitor
    _signal_monitor = get_signal_monitor()
except Exception:
    # SignalMonitor not available
    pass


@trading_router.post("/cycle")
async def trading_cycle():
    """Run a trading cycle - proxies to engine API."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post("http://localhost:8006/api/v1/analyze", 
                                       json={"instrument": "BANKNIFTY", "context": {}})
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "decision": data.get("decision"), "confidence": data.get("confidence")}
            else:
                return {"success": False, "error": f"Engine API returned {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@trading_router.get("/signals")
async def get_signals(instrument: str = "BANKNIFTY"):
    """Get trading signals - fetches from engine API MongoDB."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:8006/api/v1/signals/{instrument}")
            if response.status_code == 200:
                return {"signals": response.json()}
            else:
                return {"signals": []}
    except Exception as e:
        logger.error(f"Failed to fetch signals: {e}")
        return {"signals": []}


@trading_router.get("/positions")
async def get_positions():
    """Get active positions - proxies to user API."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8007/api/trading/positions")
            if response.status_code == 200:
                return {"positions": response.json()}
            else:
                return {"positions": []}
    except Exception as e:
        return {"positions": []}


@trading_router.get("/stats")
async def get_trading_stats():
    """Get trading statistics - proxies to user API."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8007/api/trading/stats")
            if response.status_code == 200:
                return response.json()
            else:
                return {"total_trades": 0, "win_rate": 0.0}
    except Exception as e:
        return {"total_trades": 0, "win_rate": 0.0}


@trading_router.get("/dashboard")
async def trading_dashboard():
    """Get trading dashboard summary."""
    try:
        signals_resp = await get_signals()
        positions_resp = await get_positions()
        return {
            "status": "ok",
            "signals": len(signals_resp.get("signals", [])),
            "positions": len(positions_resp.get("positions", []))
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "signals": 0, "positions": 0}


@trading_router.get("/conditions/{signal_id}")
async def trading_conditions(signal_id: str):
    """Check if signal conditions are met for execution.
    
    This actually checks the SignalMonitor and technical indicators.
    """
    try:
        if not _signal_monitor:
            # Try to get signal from MongoDB
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    # Get signal from engine API
                    response = await client.get(f"http://localhost:8006/api/v1/signals/BANKNIFTY?limit=100")
                    if response.status_code == 200:
                        signals = response.json()
                        found = next((s for s in signals if s.get("signal_id") == signal_id or str(s.get("signal_id")) == signal_id), None)
                        if found:
                            # Signal exists but monitor not available
                            return {
                                "conditions_met": False,
                                "can_execute": False,
                                "reason": "SignalMonitor not available - cannot check conditions in real-time",
                                "signal": found
                            }
                    return {"error": "Signal not found", "conditions_met": False, "can_execute": False}
            except Exception:
                return {"error": "Signal not found", "conditions_met": False, "can_execute": False}
        
        # Get active signals from SignalMonitor
        active_signals = _signal_monitor.get_active_signals()
        found_signal = next((s for s in active_signals if s.condition_id == signal_id), None)
        
        if not found_signal:
            return {"error": "Signal not found in active signals", "conditions_met": False, "can_execute": False}
        
        # Check conditions by calling check_signals
        try:
            from market_data.src.market_data.technical_indicators_service import get_technical_service
            technical_service = get_technical_service()
            
            # Get latest indicators
            indicators = technical_service.get_indicators_dict(found_signal.instrument)
            if not indicators:
                return {
                    "conditions_met": False,
                    "can_execute": False,
                    "reason": "Technical indicators not available"
                }
            
            # Manually evaluate condition
            current_value = indicators.get(found_signal.indicator)
            if current_value is None:
                return {
                    "conditions_met": False,
                    "can_execute": False,
                    "reason": f"Indicator {found_signal.indicator} not available"
                }
            
            # Evaluate condition
            conditions_met = _evaluate_condition_manual(found_signal, current_value)
            
            return {
                "conditions_met": conditions_met,
                "can_execute": conditions_met,
                "signal": {
                    "condition_id": found_signal.condition_id,
                    "instrument": found_signal.instrument,
                    "action": found_signal.action,
                    "indicator": found_signal.indicator,
                    "threshold": found_signal.threshold,
                    "current_value": current_value
                }
            }
        except Exception as e:
            return {
                "conditions_met": False,
                "can_execute": False,
                "error": str(e)
            }
            
    except Exception as e:
        return {"error": str(e), "conditions_met": False, "can_execute": False}


def _evaluate_condition_manual(condition, current_value: float) -> bool:
    """Manually evaluate a condition."""
    try:
        current_value = float(current_value)
        threshold = float(condition.threshold)
        
        if condition.operator.value == ">":
            return current_value > threshold
        elif condition.operator.value == "<":
            return current_value < threshold
        elif condition.operator.value == ">=":
            return current_value >= threshold
        elif condition.operator.value == "<=":
            return current_value <= threshold
        elif condition.operator.value == "==":
            return abs(current_value - threshold) < 0.01
        else:
            # For crosses_above/below, we can't determine without previous value
            # Assume not met for safety
            return False
    except Exception:
        return False


@trading_router.post("/execute/{signal_id}")
async def execute_signal(signal_id: str):
    """Execute a signal immediately (bypasses condition checking).

    Flow:
      1. Fetch full signal doc from engine API
      2. Build trade payload
      3. Call user_module `/api/trading/execute`
      4. If success, mark the signal executed in engine DB via engine API
    """
    try:
        import httpx

        # 1) Fetch full signal document from engine API
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"http://localhost:8006/api/v1/signals/by-id/{signal_id}")
            signal_doc = None
            if resp.status_code == 200:
                signal_doc = resp.json()
            else:
                # Fallback: fetch list and search
                resp2 = await client.get(f"http://localhost:8006/api/v1/signals/BANKNIFTY?limit=100")
                if resp2.status_code == 200:
                    signals = resp2.json()
                    found = next((s for s in signals if s.get("signal_id") == signal_id or str(s.get("signal_id")) == signal_id), None)
                    if found:
                        signal_doc = found

            if not signal_doc:
                raise HTTPException(status_code=404, detail="Signal not found")

            # 2) Build trade payload
            trade_data = {
                "user_id": "default_user",
                "instrument": signal_doc.get("instrument", "BANKNIFTY"),
                "side": signal_doc.get("action", "BUY"),
                "quantity": int(signal_doc.get("position_size") or 1),
                "order_type": "MARKET",
                "price": None,
                "stop_loss": signal_doc.get("stop_loss"),
                "take_profit": signal_doc.get("take_profit"),
                "instrument_type": signal_doc.get("strategy_type", "SPOT"),
                "signal_id": signal_id
            }

            # 3) Execute via user_module
            try:
                async with httpx.AsyncClient(timeout=30.0) as client2:
                    user_resp = await client2.post("http://localhost:8007/api/trading/execute", json=trade_data)
                    if user_resp.status_code == 200:
                        result = user_resp.json()

                        # 4) Mark executed in engine API
                        try:
                            await client.post("http://localhost:8006/api/v1/signals/mark-executed", params={"signal_id": signal_id}, json={"execution_info": result})
                        except Exception as mark_err:
                            logger.warning(f"Failed to mark signal executed via engine API: {mark_err}")

                        return {"success": True, "executed": True, "signal_id": signal_id, "result": result}
                    else:
                        return {"success": False, "error": f"user_module returned {user_resp.status_code}", "detail": user_resp.text}
            except Exception as trade_err:
                logger.error(f"Trade execution error: {trade_err}", exc_info=True)
                return {"success": False, "error": str(trade_err)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute signal failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@trading_router.post("/execute-when-ready/{signal_id}")
async def execute_when_ready(signal_id: str):
    """Mark signal for conditional execution - monitor conditions and execute when met.
    
    This adds the signal to SignalMonitor if not already there, enabling real-time monitoring.
    """
    try:
        if not _signal_monitor:
            raise HTTPException(status_code=503, detail="SignalMonitor not available")
        
        # Get signal from MongoDB
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:8006/api/v1/signals/BANKNIFTY?limit=100")
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Signal not found")
            
            signals = response.json()
            found = next((s for s in signals if s.get("signal_id") == signal_id or str(s.get("signal_id")) == signal_id), None)
            if not found:
                raise HTTPException(status_code=404, detail="Signal not found")
        
        # Sync signal to SignalMonitor (if not already active)
        from engine_module.src.engine_module.signal_creator import sync_signals_to_monitor
        from engine_module.src.engine_module.api_service import get_mongo_client
        
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        
        # Sync just this instrument's signals
        synced = await sync_signals_to_monitor(db, _signal_monitor, instrument=found.get("instrument"))
        
        # Verify signal is now active
        active_signals = _signal_monitor.get_active_signals(found.get("instrument"))
        signal_active = any(s.condition_id == signal_id for s in active_signals)
        
        return {
            "success": True,
            "signal_id": signal_id,
            "monitoring": signal_active,
            "message": "Signal added to real-time monitoring. Will execute automatically when conditions are met."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set up conditional execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
