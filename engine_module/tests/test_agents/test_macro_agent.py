import pytest
from engine_module.agents.macro_agent import MacroAgent


@pytest.mark.asyncio
async def test_macro_agent_default():
    agent = MacroAgent()
    res = await agent.analyze({})
    assert res.decision == "HOLD"
    assert isinstance(res.confidence, float)
    assert "sector_headwind_score" in res.details


@pytest.mark.asyncio
async def test_macro_agent_inflation_risk(monkeypatch):
    agent = MacroAgent()

    def fake_llm(prompt, rf):
        return {"macro_regime": "RISK_OFF", "macro_headwind_score": -0.2, "confidence_score": 0.8}

    monkeypatch.setattr(agent, "_call_llm_structured", fake_llm)

    res = await agent.analyze({"inflation_rate": 7.0, "instrument_name": "NIFTY"})
    assert res.decision == "SELL"
    assert abs(res.confidence - 0.8) < 1e-6
    assert res.details["macro_bias"] == "BEARISH"

