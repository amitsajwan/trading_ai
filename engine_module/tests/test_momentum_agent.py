import asyncio
import pytest
from engine_module.agents.momentum_agent import MomentumAgent
from engine_module.contracts import AnalysisResult

@pytest.mark.asyncio
async def test_momentum_agent_no_technical_data():
    agent = MomentumAgent()
    context = {}
    res: AnalysisResult = await agent.analyze(context)
    assert res.decision == 'HOLD'
    assert res.confidence == 0.0
    assert res.details.get('reason') == 'NO_TECHNICAL_DATA'

@pytest.mark.asyncio
async def test_momentum_agent_buy_signal():
    agent = MomentumAgent()
    tech = {
        'rsi': 75.0,
        'sma_20': 60000.0,
        'volume_ratio': 2.0,
        'price_change_pct': 1.0
    }
    context = {'technical_indicators': tech, 'current_price': 60500.0}
    res: AnalysisResult = await agent.analyze(context)
    assert res.decision == 'BUY'
    assert res.confidence >= 0.7

@pytest.mark.asyncio
async def test_momentum_agent_missing_indicators():
    agent = MomentumAgent()
    tech = {'rsi': None, 'sma_20': None}
    context = {'technical_indicators': tech, 'current_price': 60000.0}
    res: AnalysisResult = await agent.analyze(context)
    assert res.decision == 'HOLD'
    assert res.confidence == 0.0
