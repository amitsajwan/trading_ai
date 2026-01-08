import pytest
from engine_module.agents.fundamental_agent import FundamentalAgent
from engine_module.agents.portfolio_manager import PortfolioManagerAgent
from engine_module.agents.review_agent import ReviewAgent
from engine_module.agents.risk_agents import RiskAgent
from engine_module.agents.bear_researcher import BearResearcher
from engine_module.agents.bull_researcher import BullResearcher
from engine_module.agents.learning_agent import LearningAgent


@pytest.mark.asyncio
async def test_fundamental_agent_buy():
    a = FundamentalAgent()
    res = await a.analyze({"earnings_surprise": 0.1})
    assert res.decision == "BUY"


@pytest.mark.asyncio
async def test_portfolio_manager_votes():
    a = PortfolioManagerAgent()
    tech = {"bias": "BULLISH"}
    sent = {"bias": "BULLISH"}
    macro = {"bias": "NEUTRAL"}
    res = await a.analyze({"technical": tech, "sentiment": sent, "macro": macro})
    assert res.decision == "BUY"


@pytest.mark.asyncio
async def test_review_agent_summary():
    a = ReviewAgent()
    res = await a.analyze({"technical": {"rsi": 50}})
    assert res.decision == "HOLD"
    assert "summary" in res.details


@pytest.mark.asyncio
async def test_risk_agent_high_atr():
    a = RiskAgent()
    res = await a.analyze({"technical": {"atr": 0.1}})
    assert res.details["risk"] == "HIGH_VOLATILITY"


@pytest.mark.asyncio
async def test_bear_bull_researchers():
    bear = BearResearcher()
    bull = BullResearcher()
    bres = await bear.analyze({"technical": {"trend_direction": "DOWN"}})
    b2 = await bull.analyze({"technical": {"trend_direction": "UP"}})
    assert bres.decision == "SELL"
    assert b2.decision == "BUY"


@pytest.mark.asyncio
async def test_learning_agent_stub():
    a = LearningAgent()
    res = await a.analyze({})
    assert res.decision == "HOLD"
