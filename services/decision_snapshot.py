"""Decision snapshot builder for BANKNIFTY (and NIFTY).

Aggregates hot data from Redis (ticks, depth) and options-chain summary
into a compact snapshot for algo decision-making and API consumption.
"""
import json
import asyncio
from datetime import datetime, UTC
from typing import Any, Dict, Optional
from pathlib import Path

from data.market_memory import MarketMemory
from data.order_flow_analyzer import OrderFlowAnalyzer
from data.options_chain_fetcher import OptionsChainFetcher
from config.settings import settings

try:
    from kiteconnect import KiteConnect
except Exception:  # pragma: no cover - optional at runtime
    KiteConnect = None  # type: ignore


def _instrument_key() -> str:
    sym = (settings.instrument_symbol or "NIFTY BANK").upper().replace(" ", "")
    if "BANKNIFTY" in sym or "NIFTYBANK" in sym:
        return "BANKNIFTY"
    return "NIFTY"


def _make_kite() -> Optional[KiteConnect]:
    if KiteConnect is None:
        return None
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        return None
    try:
        creds = json.loads(cred_path.read_text())
        api_key = creds.get("api_key") or creds.get("apiKey")
        access_token = creds.get("access_token") or creds.get("accessToken")
        if not api_key or not access_token:
            return None
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        return kite
    except Exception:
        return None


async def build_snapshot(market_memory: Optional[MarketMemory] = None) -> Dict[str, Any]:
    """Build a decision snapshot for the configured instrument."""
    mm = market_memory or MarketMemory()
    instrument = _instrument_key()

    # LTP
    ltp = mm.get_current_price(instrument)

    # Latest depth tick (if any)
    latest_tick = None
    try:
        if mm._redis_available and mm.redis_client:
            keys = mm.redis_client.keys(f"tick:{instrument}:*")
            if keys:
                latest_key = sorted(keys)[-1]
                raw = mm.redis_client.get(latest_key)
                if raw:
                    latest_tick = json.loads(raw)
    except Exception:
        latest_tick = None

    # Depth analytics
    spread = {}
    depth_view = {}
    large_orders = {}
    imbalance = {}
    best_bid = None
    best_ask = None
    total_bid_qty = None
    total_ask_qty = None

    if latest_tick and isinstance(latest_tick, dict):
        depth = latest_tick.get("depth") or {}
        buy_levels = depth.get("buy") or []
        sell_levels = depth.get("sell") or []
        if buy_levels:
            best_bid = buy_levels[0].get("price")
        if sell_levels:
            best_ask = sell_levels[0].get("price")
        spread = OrderFlowAnalyzer.analyze_bid_ask_spread(best_bid, best_ask, float(ltp or 0))
        depth_view = OrderFlowAnalyzer.analyze_market_depth(buy_levels, sell_levels)
        large_orders = OrderFlowAnalyzer.detect_large_orders(buy_levels, sell_levels)
        total_bid_qty = sum(lvl.get("quantity", 0) for lvl in buy_levels[:5]) if buy_levels else 0
        total_ask_qty = sum(lvl.get("quantity", 0) for lvl in sell_levels[:5]) if sell_levels else 0
        buy_q = int(latest_tick.get("total_bid_quantity") or total_bid_qty or 0)
        sell_q = int(latest_tick.get("total_ask_quantity") or total_ask_qty or 0)
        imbalance = OrderFlowAnalyzer.calculate_buy_sell_imbalance(buy_q, sell_q)

    # Options chain summary
    options_summary: Dict[str, Any] = {"available": False}
    try:
        kite = _make_kite()
        if kite:
            fetcher = OptionsChainFetcher(kite, mm, instrument_symbol=("NIFTY BANK" if instrument == "BANKNIFTY" else "NIFTY"))
            await fetcher.initialize()
            chain = await fetcher.fetch_options_chain()
            if chain.get("available"):
                strikes = chain.get("strikes", {}) or {}
                # PCR
                total_ce_oi = 0
                total_pe_oi = 0
                for sdata in strikes.values():
                    total_ce_oi += int(sdata.get("ce_oi") or 0)
                    total_pe_oi += int(sdata.get("pe_oi") or 0)
                pcr = (total_pe_oi / total_ce_oi) if total_ce_oi else None
                # ATM strike approximation
                fut_price = chain.get("futures_price") or ltp or 0
                if isinstance(fut_price, (int, float)):
                    atm = int(round(float(fut_price) / 100) * 100)
                else:
                    atm = None
                atm_row = strikes.get(atm, {}) if atm else {}
                options_summary = {
                    "available": True,
                    "futures_price": chain.get("futures_price"),
                    "atm_strike": atm,
                    "ce_ltp": atm_row.get("ce_ltp"),
                    "pe_ltp": atm_row.get("pe_ltp"),
                    "ce_oi": atm_row.get("ce_oi"),
                    "pe_oi": atm_row.get("pe_oi"),
                    "pcr": pcr,
                    "total_ce_oi": total_ce_oi,
                    "total_pe_oi": total_pe_oi,
                    "strikes_sampled": len(strikes),
                }
    except Exception:
        pass

    snapshot: Dict[str, Any] = {
        "instrument": instrument,
        "timestamp": datetime.now(UTC).isoformat(),
        "ltp": ltp,
        "depth": {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "total_bid_qty": total_bid_qty,
            "total_ask_qty": total_ask_qty,
            "spread": spread,
            "view": depth_view,
            "large_orders": large_orders,
            "imbalance": imbalance,
        },
        "options": options_summary,
    }

    # store in Redis for fast API use
    try:
        if mm._redis_available and mm.redis_client:
            mm.redis_client.setex(
                f"snapshot:{instrument}:latest",
                60,
                json.dumps(snapshot)
            )
    except Exception:
        pass

    return snapshot


async def build_and_store_forever(interval_seconds: int = 20):
    mm = MarketMemory()
    while True:
        try:
            await build_snapshot(mm)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
