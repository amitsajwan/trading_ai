import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

import pytest

try:
    from kiteconnect import KiteConnect
except Exception:  # pragma: no cover - dependency issues
    KiteConnect = None  # type: ignore

from data.options_chain_fetcher import OptionsChainFetcher
from data.market_memory import MarketMemory
from engines.rule_engine import RuleEngine, RuleSignal
from data.order_flow_analyzer import OrderFlowAnalyzer


CREDENTIAL_FILES = [
    Path("credentials.json"),
    Path("kite_credentials.json"),
]


def load_kite() -> Optional[KiteConnect]:
    """Load KiteConnect using credentials file or env vars."""
    if KiteConnect is None:
        return None

    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")

    # Fallback to credentials file
    if not api_key or not access_token:
        cred_path = next((p for p in CREDENTIAL_FILES if p.exists()), None)
        if not cred_path:
            return None
        with cred_path.open() as f:
            creds = json.load(f)
        api_key = creds.get("api_key") or creds.get("apiKey")
        access_token = creds.get("access_token") or creds.get("accessToken")

    if not api_key or not access_token:
        return None

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def _find_banknifty_fut_token(kite: KiteConnect) -> Optional[int]:
    """Resolve BankNifty token by preferring NSE index 'NIFTY BANK', then NFO FUT nearest expiry."""
    try:
        # Prefer NSE index exact match
        try:
            for inst in kite.instruments("NSE"):
                ts = (inst.get("tradingsymbol") or "").upper()
                if ts == "NIFTY BANK":
                    return inst.get("instrument_token")
        except Exception:
            pass

        # Fallback to NFO futures (nearest non-expired)
        futs: List[Dict[str, Any]] = []
        today = datetime.now().date()
        for inst in kite.instruments("NFO"):
            if inst.get("segment") != "NFO-FUT":
                continue
            ts = (inst.get("tradingsymbol") or "").upper()
            if "BANKNIFTY" not in ts:
                continue
            expiry = inst.get("expiry")
            try:
                exp_date = expiry.date() if hasattr(expiry, "date") else expiry
            except Exception:
                exp_date = expiry
            if exp_date and exp_date >= today:
                futs.append(inst)
        if futs:
            futs.sort(key=lambda x: x.get("expiry"))
            return futs[0].get("instrument_token")
        return None
    except Exception:
        return None


@pytest.mark.live
@pytest.mark.skipif(KiteConnect is None, reason="kiteconnect not installed")
def test_kite_connects_and_ltp_banknifty():
    kite = load_kite()
    if not kite:
        pytest.skip("Kite credentials not configured; set KITE_API_KEY and KITE_ACCESS_TOKEN or credentials.json")

    token = _find_banknifty_fut_token(kite)
    if not token:
        pytest.skip("BANKNIFTY token not found via instruments(); check API permissions or market segment access")

    q = kite.quote([token])
    data = q.get(str(token)) or q.get(token)
    assert data and isinstance(data, dict)
    assert data.get("last_price", 0) > 0


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.skipif(KiteConnect is None, reason="kiteconnect not installed")
async def test_options_chain_live_has_oi_and_volume():
    kite = load_kite()
    if not kite:
        pytest.skip("Kite credentials not configured; set KITE_API_KEY and KITE_ACCESS_TOKEN or credentials.json")

    mm = MarketMemory()  # Works in fallback if Redis absent
    fetcher = OptionsChainFetcher(kite, mm, instrument_symbol="BANKNIFTY")

    await fetcher.initialize()
    chain = await fetcher.fetch_options_chain()

    assert chain.get("available"), f"Options chain not available: {chain}"
    assert isinstance(chain.get("futures_price"), (int, float))

    strikes = chain.get("strikes", {})
    assert isinstance(strikes, dict) and len(strikes) > 0

    # Find at least one strike with CE/PE data populated
    validated = False
    for sdata in strikes.values():
        ce_ltp = sdata.get("ce_ltp")
        pe_ltp = sdata.get("pe_ltp")
        ce_oi = sdata.get("ce_oi")
        pe_oi = sdata.get("pe_oi")
        ce_vol = sdata.get("ce_volume")
        pe_vol = sdata.get("pe_volume")
        if all(k is not None for k in [ce_ltp, pe_ltp, ce_oi, pe_oi, ce_vol, pe_vol]):
            # Allow zeros off-hours; just ensure numeric types
            assert isinstance(ce_ltp, (int, float))
            assert isinstance(pe_ltp, (int, float))
            assert isinstance(ce_oi, (int, float))
            assert isinstance(pe_oi, (int, float))
            assert isinstance(ce_vol, (int, float))
            assert isinstance(pe_vol, (int, float))
            validated = True
            break

    assert validated, "No strike had full CE/PE LTP/OI/volume data"


@pytest.mark.live
@pytest.mark.skipif(KiteConnect is None, reason="kiteconnect not installed")
def test_market_depth_available_or_skip():
    kite = load_kite()
    if not kite:
        pytest.skip("Kite credentials not configured; set KITE_API_KEY and KITE_ACCESS_TOKEN or credentials.json")

    token = _find_banknifty_fut_token(kite)
    if not token:
        pytest.skip("BANKNIFTY token not found via instruments(); check API permissions or market segment access")

    q = kite.quote([token])
    data = q.get(str(token)) or q.get(token) or {}
    depth = data.get("depth")
    if not depth:
        pytest.skip("Market depth not available for current plan or instrument")

    assert isinstance(depth.get("buy", []), list)
    assert isinstance(depth.get("sell", []), list)


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.skipif(KiteConnect is None, reason="kiteconnect not installed")
async def test_rule_engine_emits_signal_with_real_price():
    kite = load_kite()
    if not kite:
        pytest.skip("Kite credentials not configured; set KITE_API_KEY and KITE_ACCESS_TOKEN or credentials.json")

    token = _find_banknifty_fut_token(kite)
    if not token:
        pytest.skip("BANKNIFTY token not found via instruments(); check API permissions or market segment access")

    q = kite.quote([token])
    data = q.get(str(token)) or q.get(token)
    assert data and isinstance(data, dict)

    ltp = float(data.get("last_price", 0))
    assert ltp > 0

    # Also pull a small options chain snapshot to attach OI context
    mm = MarketMemory()
    fetcher = OptionsChainFetcher(kite, mm, instrument_symbol="BANKNIFTY")
    await fetcher.initialize()
    chain = await fetcher.fetch_options_chain()

    oi_data = {}
    for strike, sdata in chain.get("strikes", {}).items():
        if all(k in sdata for k in ("ce_oi", "pe_oi")):
            oi_data[strike] = {"ce_oi": sdata.get("ce_oi", 0), "pe_oi": sdata.get("pe_oi", 0)}
            break

    engine = RuleEngine(kite=None, market_memory=mm)

    # Create a simple rule that should pass with current price
    rule = RuleSignal(
        rule_id="test_rule",
        name="LTP Above Tiny Threshold",
        direction="BUY",
        instrument="BANKNIFTY",
        conditions=[{"type": "fut_ltp_above", "value": max(1.0, ltp * 0.5)}],
        risk_pct=0.5,
        sl_pct=10.0,
        target_pct=20.0,
    )
    engine.active_rules = [rule]

    tick = {
        "instrument": "BANKNIFTY",
        "last_price": ltp,
        "timestamp": datetime.now().isoformat(),
    }
    if oi_data:
        tick["oi_data"] = oi_data

    signals = await engine.evaluate_rules(tick)
    assert isinstance(signals, list)
    assert any(s.get("rule_id") == "test_rule" for s in signals), "Expected signal not emitted"


@pytest.mark.live
@pytest.mark.skipif(KiteConnect is None, reason="kiteconnect not installed")
def test_depth_analytics_when_available():
    kite = load_kite()
    if not kite:
        pytest.skip("Kite credentials not configured; set KITE_API_KEY and KITE_ACCESS_TOKEN or credentials.json")

    token = _find_banknifty_fut_token(kite)
    if not token:
        pytest.skip("BANKNIFTY token not found via instruments(); check API permissions or market segment access")

    q = kite.quote([token])
    data = q.get(str(token)) or q.get(token) or {}
    depth = data.get("depth")
    if not depth:
        pytest.skip("Market depth not available for current plan or instrument")

    buy_levels = depth.get("buy", []) or []
    sell_levels = depth.get("sell", []) or []
    if not buy_levels or not sell_levels:
        pytest.skip("Depth lists empty; cannot analyze order flow")

    # Extract best bid/ask using top-of-book heuristics
    try:
        best_bid = max([lvl.get("price") for lvl in buy_levels if lvl.get("price") is not None])
    except ValueError:
        best_bid = None
    try:
        best_ask = min([lvl.get("price") for lvl in sell_levels if lvl.get("price") is not None])
    except ValueError:
        best_ask = None

    ltp = float(data.get("last_price") or 0)

    spread_info = OrderFlowAnalyzer.analyze_bid_ask_spread(best_bid, best_ask, ltp)
    assert "mid_price" in spread_info
    if best_bid is not None and best_ask is not None and best_bid < best_ask:
        assert spread_info["spread"] >= 0
        assert spread_info["bid_price"] == best_bid
        assert spread_info["ask_price"] == best_ask

    depth_info = OrderFlowAnalyzer.analyze_market_depth(buy_levels, sell_levels)
    assert set(["support_levels", "resistance_levels", "total_buy_depth", "total_sell_depth", "depth_imbalance"]).issubset(depth_info.keys())
    assert isinstance(depth_info["support_levels"], list)
    assert isinstance(depth_info["resistance_levels"], list)

    large_orders = OrderFlowAnalyzer.detect_large_orders(buy_levels, sell_levels, threshold=1)
    # Structure assertions (do not enforce presence of large orders)
    assert set(["large_buy_orders", "large_sell_orders", "has_large_orders", "large_order_pressure"]).issubset(large_orders.keys())
    assert isinstance(large_orders["large_buy_orders"], list)
    assert isinstance(large_orders["large_sell_orders"], list)
