"""Mode and startup helpers for the trading dashboard.

This module coordinates CURRENT_MODE, _mode_manager, and service
startup. app.py hooks these into FastAPI's lifecycle events.
"""

from __future__ import annotations

import asyncio
from typing import Any

from dashboard.core.state import PAPER_TRADING_CONFIG
from dashboard.core.live_data import initialize_live_zerodha_data, live_data_update_loop

try:
    from core_kernel.src.core_kernel.mode_manager import get_mode_manager  # type: ignore[import]

    _mode_manager = get_mode_manager()
except Exception:  # pragma: no cover
    _mode_manager = None


# Default mode if nothing is configured - None means no mode selected
CURRENT_MODE: str | None = None

# Background task references
_options_algo_task: Any | None = None
_live_data_task: Any | None = None


async def start_services() -> None:
    """Startup hook to initialize services and background tasks."""

    global CURRENT_MODE, _options_algo_task, _live_data_task

    print("Starting dashboard services...")

    # Auto-switch mode if mode manager is available
    if _mode_manager is not None:
        try:
            # First, sync CURRENT_MODE with mode manager's current state
            mode_info = _mode_manager.get_mode_info()
            stored_mode = mode_info.get("current_mode")
            if stored_mode:
                CURRENT_MODE = stored_mode
                print(f"Loaded mode from manager: {stored_mode}")
            
            # Then check if auto-switch is needed
            should_switch, suggested_mode, reason = _mode_manager.check_auto_switch()
            if should_switch and suggested_mode != "live":
                switched, new_mode, _ = _mode_manager.auto_switch(require_confirmation_for_live=True)
                if switched:
                    CURRENT_MODE = new_mode
                    print(f"Auto-switched to {new_mode} mode: {reason}")
            else:
                print(f"Current mode: {CURRENT_MODE}")
        except Exception as exc:
            print(f"Warning: Could not check auto-switch: {exc}")

    # Initialize live Zerodha data if available
    live_data_initialized = False
    try:
        live_data_initialized = await initialize_live_zerodha_data()
    except Exception as exc:
        print(f"Live Zerodha data initialization failed: {exc}")

    if live_data_initialized:
        print("Live Zerodha data initialized")

    # Start live data updates for paper trading
    if PAPER_TRADING_CONFIG.get("enabled") and PAPER_TRADING_CONFIG.get("real_time_updates"):
        print("Starting live market data updates...")
        _live_data_task = asyncio.create_task(live_data_update_loop())

    print("All services started")


__all__ = ["CURRENT_MODE", "start_services", "_mode_manager"]

