"""Health and status helpers for the trading dashboard.

This module contains pure-logic helpers that compute trading health
and overall system status. The FastAPI routes in app.py delegate to
these functions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from dashboard.core.state import TRADING_SIGNALS, ACTIVE_POSITIONS, TRADING_STATS, PAPER_TRADING_CONFIG


async def get_trading_health() -> Dict[str, Any]:
    """Get trading system health status for dashboard integration.

    Returns a dict shaped like::

        {"trading": {...}}
    """

    try:
        signals_count = len(TRADING_SIGNALS)
        positions_count = len(ACTIVE_POSITIONS)

        trading_status = "ok"
        issues = []

        if signals_count == 0:
            issues.append("No signals available")
        if positions_count == 0:
            issues.append("No active positions")

        # Check for stuck signals (older than 1 hour)
        now = datetime.now()
        old_signals = 0
        for signal in TRADING_SIGNALS:
            try:
                ts = signal.get("timestamp")
                if ts:
                    signal_time = datetime.fromisoformat(ts)
                    if (now - signal_time).total_seconds() > 3600:
                        old_signals += 1
            except Exception:
                continue

        if old_signals > 0:
            trading_status = "degraded"
            issues.append(f"{old_signals} signals older than 1 hour")

        paper_trading_info: Dict[str, Any] = {}
        if PAPER_TRADING_CONFIG.get("enabled"):
            paper_trading_info = {
                "account_balance": PAPER_TRADING_CONFIG.get("account_balance"),
                "max_position_size": PAPER_TRADING_CONFIG.get("max_position_size"),
                "max_positions": PAPER_TRADING_CONFIG.get("max_positions"),
                "daily_loss_limit": PAPER_TRADING_CONFIG.get("daily_loss_limit"),
                "symbols_allowed": PAPER_TRADING_CONFIG.get("symbols_allowed"),
            }

        return {
            "trading": {
                "status": trading_status,
                "signals_count": signals_count,
                "positions_count": positions_count,
                "total_pnl": TRADING_STATS.get("total_pnl", 0),
                "win_rate": TRADING_STATS.get("win_rate", 0),
                "issues": issues,
                "last_update": datetime.now().isoformat(),
                **paper_trading_info,
            }
        }

    except Exception as exc:  # Defensive fallback
        return {
            "trading": {
                "status": "error",
                "error": str(exc),
                "signals_count": 0,
                "positions_count": 0,
            }
        }


async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status (DB, cache, market)."""

    try:
        mongo_status = "error"
        redis_status = "error"

        # MongoDB health
        try:
            from pymongo import MongoClient  # type: ignore[import]
            import os

            # Use MONGODB_URI env var if set (Docker uses mongodb://mongodb:27017)
            # Otherwise default to localhost:27018 (host-mapped Docker port)
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27018/")
            
            # Extract just the connection string without database name for health check
            if mongo_uri.endswith("/zerodha_trading"):
                mongo_uri = mongo_uri.rsplit("/", 1)[0] + "/"
            
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            mongo_status = "ok"
        except Exception:
            pass

        # Redis health
        try:
            import redis  # type: ignore[import]
            import os

            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            r = redis.Redis(host=host, port=port, db=0)
            r.ping()
            redis_status = "ok"
        except Exception:
            pass

        # Market hours (NSE)
        now = datetime.now()
        market_open = (
            now.weekday() < 5
            and now.time() >= datetime.strptime("09:15", "%H:%M").time()
            and now.time() <= datetime.strptime("15:30", "%H:%M").time()
        )

        return {
            "status": "ok" if mongo_status == "ok" and redis_status == "ok" else "degraded",
            "database": mongo_status,
            "cache": redis_status,
            "market_open": market_open,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "uptime": "Active",
            "components": {
                "data_module": "operational",
                "genai_module": "operational",
                "user_module": "operational",
                "engine_module": "operational",
                "ui_shell": "operational",
            },
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "timestamp": datetime.now().isoformat(),
        }


__all__ = ["get_trading_health", "get_system_status"]

