"""Core in-memory trading state for the dashboard.

This module centralizes the TRADING_SIGNALS, ACTIVE_POSITIONS,
TRADING_STATS, MARKET_DATA and PAPER_TRADING_CONFIG data structures so
that they can be reused across routes and helpers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

# In-memory fallback store for paper trades if DB isn't available
PAPER_TRADES_CACHE: List[dict] = []

TRADING_SIGNALS: List[dict] = []

ACTIVE_POSITIONS: List[dict] = []

TRADING_STATS: Dict[str, float] = {
    "cycles_run": 0,
    "signals_generated": 0,
    "trades_executed": 0,
    "total_pnl": 0.0,
    "win_rate": 0.0,
    "active_positions": 0,
}

MARKET_DATA: Dict[str, dict] = {}

# Paper Trading Configuration
PAPER_TRADING_CONFIG: Dict[str, object] = {
    "enabled": True,
    "account_balance": 100000.0,
    "max_position_size": 0.1,
    "max_positions": 3,
    "commission_per_trade": 20.0,
    "margin_required": 0.25,
    "daily_loss_limit": 0.05,
    "symbols_allowed": ["BANKNIFTY"],
    "real_time_updates": True,
    "data_source": "live_simulated",
}

__all__ = [
    "PAPER_TRADES_CACHE",
    "TRADING_SIGNALS",
    "ACTIVE_POSITIONS",
    "TRADING_STATS",
    "MARKET_DATA",
    "PAPER_TRADING_CONFIG",
]

