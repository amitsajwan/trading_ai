"""Live market data and Zerodha/Kite integration helpers.

This module contains the live data simulation used for paper trading
and the optional Zerodha/market_data integration. app.py wires the
FastAPI lifecycle events to these helpers.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dashboard.core.state import MARKET_DATA, PAPER_TRADING_CONFIG

# Feature flags for external integrations (Zerodha + market_data)
try:  # market_data availability
    import importlib

    _market_data_store = importlib.util.find_spec("market_data.store")
    MARKET_DATA_MODULE_AVAILABLE: bool = _market_data_store is not None
except Exception:  # pragma: no cover
    MARKET_DATA_MODULE_AVAILABLE = False

# Backwards-compatible alias expected by older modules
# Some modules import the flag as `market_data_AVAILABLE` (lowercase) so
# expose a compatibility symbol to avoid ImportError during collection.
market_data_AVAILABLE = MARKET_DATA_MODULE_AVAILABLE

try:  # Kite/Zerodha integration flag
    from kiteconnect import KiteConnect  # type: ignore[import]

    KITE_AVAILABLE: bool = True
except Exception:  # pragma: no cover
    KiteConnect = None  # type: ignore[assignment]
    KITE_AVAILABLE = False


async def update_live_market_data() -> None:
    """Simulate live market data updates for Bank Nifty paper trading."""

    try:
        symbol = "BANKNIFTY"
        if symbol not in MARKET_DATA:
            return

        current_data = MARKET_DATA[symbol]
        base_price = current_data["price"]

        import random

        price_change_pct = random.uniform(-0.005, 0.005)
        new_price = base_price * (1 + price_change_pct)

        MARKET_DATA[symbol]["price"] = round(new_price, 2)
        MARKET_DATA[symbol]["last_update"] = datetime.now().isoformat()

        open_price = base_price * 0.995
        MARKET_DATA[symbol]["change_pct"] = round(((new_price - open_price) / open_price) * 100, 2)

        rsi_change = random.uniform(-2, 2)
        new_rsi = max(0, min(100, current_data["rsi_14"] + rsi_change))
        MARKET_DATA[symbol]["rsi_14"] = round(new_rsi, 1)

        volume_change_pct = random.uniform(-0.3, 0.3)
        new_volume = int(current_data["volume"] * (1 + volume_change_pct))
        MARKET_DATA[symbol]["volume"] = new_volume

        macd_change = random.uniform(-5, 5)
        MARKET_DATA[symbol]["macd_line"] = round(current_data["macd_line"] + macd_change, 1)

        adx_change = random.uniform(-1, 1)
        new_adx = max(10, min(50, current_data["adx"] + adx_change))
        MARKET_DATA[symbol]["adx"] = round(new_adx, 1)

        sma_change = random.uniform(-10, 10)
        MARKET_DATA[symbol]["sma_20"] = round(current_data["sma_20"] + sma_change, 2)

        ema_change = random.uniform(-8, 8)
        MARKET_DATA[symbol]["ema_20"] = round(current_data["ema_20"] + ema_change, 2)

        bb_center = (current_data["bb_upper"] + current_data["bb_lower"]) / 2
        bb_change = random.uniform(-15, 15)
        new_bb_center = bb_center + bb_change
        bb_width = current_data["bb_upper"] - current_data["bb_lower"]
        MARKET_DATA[symbol]["bb_upper"] = round(new_bb_center + bb_width / 2, 2)
        MARKET_DATA[symbol]["bb_lower"] = round(new_bb_center - bb_width / 2, 2)

        vwap_change = random.uniform(-5, 5)
        MARKET_DATA[symbol]["vwap"] = round(current_data["vwap"] + vwap_change, 2)

        print(f"Live data updated: {symbol} @ {new_price:.0f} (RSI: {new_rsi:.1f})")

    except Exception as exc:
        print(f"Error updating live data: {exc}")


# Zerodha/live data globals (initialized lazily in initializer)
_live_market_store: Any | None = None
_live_data_ingestion: Any | None = None
_kite_client: Any | None = None
_live_options_client: Any | None = None
_live_news_client: Any | None = None
_live_macro_client: Any | None = None


async def initialize_live_zerodha_data() -> bool:
    """Initialize live Zerodha data connections if dependencies are present."""

    global _live_market_store, _live_data_ingestion, _kite_client, _live_options_client, _live_news_client, _live_macro_client

    if not MARKET_DATA_MODULE_AVAILABLE or not KITE_AVAILABLE:
        print("Live Zerodha data not available - using simulated data")
        return False

    try:
        api_key = os.getenv("KITE_API_KEY")
        api_secret = os.getenv("KITE_API_SECRET")

        if not api_key or not api_secret:
            print("KITE_API_KEY and KITE_API_SECRET not found in environment")
            return False

        cred_path = Path("credentials.json")
        access_token = None
        if cred_path.exists():
            try:
                creds = json.loads(cred_path.read_text())
                access_token = creds.get("access_token")
            except Exception:
                pass

        if not access_token:
            print("No valid access token found - please authenticate with Kite first")
            print("Run: python market_data/src/market_data/tools/kite_auth.py")
            return False

        kite = KiteConnect(api_key=api_key)  # type: ignore[call-arg]
        kite.set_access_token(access_token)
        _kite_client = kite

        try:
            profile = kite.profile()
            print(f"Connected to Kite as: {profile.get('user_id')}")
        except Exception as exc:
            print(f"Kite connection failed: {exc}")
            return False

        from market_data.store import InMemoryMarketStore  # type: ignore[import]
        from market_data.adapters.unified_data_flow import UnifiedDataFlow  # type: ignore[import]
        from market_data.adapters.paper_broker import PaperBroker  # type: ignore[import]

        _live_market_store = InMemoryMarketStore()
        paper_broker = PaperBroker(initial_capital=PAPER_TRADING_CONFIG.get("account_balance", 100000.0))

        def on_candle_close(candle):  # pragma: no cover - callback wiring
            if paper_broker:
                paper_broker.update_market_price(candle.instrument, candle.close)

        def on_tick(tick):  # pragma: no cover
            if paper_broker:
                paper_broker.update_market_price(tick.instrument, tick.last_price)

        flow = UnifiedDataFlow(
            store=_live_market_store,
            data_source="zerodha",
            on_candle_close=on_candle_close,
            on_tick=on_tick,
            paper_broker=paper_broker,
            kite=kite,
            instrument_symbol="NIFTY BANK",
            from_date=None,
            to_date=None,
            interval="minute",
        )

        _live_data_ingestion = flow.ingestion
        print("Live Zerodha data services initialized successfully")
        return True

    except Exception as exc:
        print(f"Failed to initialize live Zerodha data: {exc}")
        return False


async def live_data_update_loop() -> None:
    """Background task to update live market data for paper trading."""

    global _live_market_store, _kite_client

    while True:
        try:
            await update_live_market_data()

            if _live_market_store and _kite_client:
                try:
                    live_tick = _live_market_store.get_latest_tick("BANKNIFTY")
                    if live_tick:
                        if "BANKNIFTY" not in MARKET_DATA:
                            MARKET_DATA["BANKNIFTY"] = {}

                        MARKET_DATA["BANKNIFTY"].update(
                            {
                                "price": live_tick.last_price,
                                "volume": live_tick.volume,
                                "last_update": datetime.now().isoformat(),
                                "source": "live_zerodha",
                            }
                        )
                        print(f"Updated MARKET_DATA with live tick: BANKNIFTY @ ₹{live_tick.last_price}")
                    else:
                        try:
                            instruments = ["NSE:NIFTY BANK"]
                            ltp_data = _kite_client.ltp(instruments)
                            if ltp_data:
                                ltp_info = ltp_data.get("NSE:NIFTY BANK", {})
                                price = ltp_info.get("last_price", 0)
                                volume = ltp_info.get("volume", 0)
                                if price > 0:
                                    if "BANKNIFTY" not in MARKET_DATA:
                                        MARKET_DATA["BANKNIFTY"] = {}

                                    MARKET_DATA["BANKNIFTY"].update(
                                        {
                                            "price": price,
                                            "volume": volume,
                                            "last_update": datetime.now().isoformat(),
                                            "source": "live_ltp",
                                        }
                                    )
                                    print(f"Updated MARKET_DATA with LTP: BANKNIFTY @ ₹{price}")
                        except Exception:
                            pass
                except Exception:
                    pass

            await asyncio.sleep(30)
        except Exception as exc:
            print(f"Live data update error: {exc}")
            await asyncio.sleep(30)


__all__ = [
    "MARKET_DATA_MODULE_AVAILABLE",
    "market_data_AVAILABLE",
    "KITE_AVAILABLE",
    "update_live_market_data",
    "initialize_live_zerodha_data",
    "live_data_update_loop",
    "_kite_client",
    "_live_market_store",
    "_live_options_client",
]

