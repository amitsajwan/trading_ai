import pytest
import asyncio
from engine_module.agents.technical_agent import TechnicalAgent


@pytest.mark.asyncio
async def test_technical_agent_basic_buy():
    agent = TechnicalAgent()
    # Create simple up-trending OHLC data
    ohlc = []
    price = 100.0
    for i in range(10):
        ohlc.append({
            "open": price - 1,
            "high": price + 1,
            "low": price - 2,
            "close": price,
        })
        price += 1.0

    res = await agent.analyze({"ohlc": ohlc})
    assert res.decision in {"BUY", "HOLD", "SELL"}
    assert isinstance(res.confidence, float)
    assert "rsi" in res.details


@pytest.mark.asyncio
async def test_missing_columns_returns_hold():
    agent = TechnicalAgent()
    ohlc = [{"open": 100, "high": 101}]  # missing low/close
    res = await agent.analyze({"ohlc": ohlc})
    assert res.decision == "HOLD"
    assert res.confidence == 0.0
    assert res.details["note"].startswith("MISSING_COLUMN_")

