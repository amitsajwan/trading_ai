import pytest
from engine_module.agents.execution_agent import ExecutionAgent


@pytest.mark.asyncio
async def test_execution_agent_paper_trade_success():
    agent = ExecutionAgent(paper_trading=True)
    ctx = {
        "final_signal": "BUY",
        "position_size": 1,
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "current_price": 101.0,
        "confidence": 0.6
    }

    res = await agent.analyze(ctx)
    assert res.decision == "BUY"
    assert res.details["order"]["filled_price"] == 100.0
    assert res.details["order"]["filled_quantity"] == 1


@pytest.mark.asyncio
async def test_execution_agent_validation_failure():
    agent = ExecutionAgent(paper_trading=True)
    ctx = {
        "final_signal": "BUY",
        "position_size": 1,
        "entry_price": 100.0,
        "stop_loss": 105.0,  # invalid: stop loss above entry for BUY
        "take_profit": 110.0,
        "current_price": 101.0,
        "confidence": 0.6
    }

    res = await agent.analyze(ctx)
    assert res.decision == "HOLD"
    assert "errors" in res.details

