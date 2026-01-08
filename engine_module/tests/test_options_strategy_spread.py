import pytest

from engine_module.options_strategy_engine import evaluate, RuleConfig

CHAIN = {
    "available": True,
    "futures_price": 45250.0,
    "expiry": "2026-01-30",
    "chain": [
        {"strike": 45000, "ce_ltp": 425.75, "ce_oi": 145000, "ce_iv": 20.8, "ce_delta": 0.45,
         "pe_ltp": 125.50, "pe_oi": 112000, "pe_iv": 21.2, "pe_delta": -0.28},
        {"strike": 45250, "ce_ltp": 225.25, "ce_oi": 180000, "ce_iv": 19.6, "ce_delta": 0.35,
         "pe_ltp": 285.75, "pe_oi": 165000, "pe_iv": 23.0, "pe_delta": -0.36},
        {"strike": 45500, "ce_ltp": 95.50,  "ce_oi": 95000,  "ce_iv": 18.9, "ce_delta": 0.22,
         "pe_ltp": 525.25, "pe_oi": 78000,  "pe_iv": 24.5, "pe_delta": -0.52},
    ]
}

ORDERFLOW = {"available": True, "imbalance": 0.15}


def test_buy_signal_returns_bull_call_spread():
    cfg = RuleConfig(min_oi=75000, target_delta=0.35)
    result = evaluate("BUY", CHAIN, ORDERFLOW, cfg)
    assert result["available"] is True
    assert result.get("recommendation") is not None
    assert result.get("strategy_type") == "Bull Call Spread"
    legs = result.get("legs")
    assert isinstance(legs, list) and len(legs) == 2
    assert {legs[0]["side"], legs[1]["side"]} == {"BUY", "SELL"}
    assert legs[0]["option_type"] == legs[1]["option_type"] == "CE"
    assert result.get("net_debit") is not None


def test_sell_signal_returns_bear_put_spread():
    cfg = RuleConfig(min_oi=75000, target_delta=0.35)
    result = evaluate("SELL", CHAIN, ORDERFLOW, cfg)
    assert result["available"] is True
    assert result.get("recommendation") is not None
    assert result.get("strategy_type") == "Bear Put Spread"
    legs = result.get("legs")
    assert isinstance(legs, list) and len(legs) == 2
    assert {legs[0]["side"], legs[1]["side"]} == {"BUY", "SELL"}
    assert legs[0]["option_type"] == legs[1]["option_type"] == "PE"
    assert result.get("net_debit") is not None

