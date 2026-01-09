import pytest
from engine_module.agents.technical_agent import TechnicalAgent
from engine_module.contracts import AnalysisResult

@pytest.mark.asyncio
async def test_technical_agent_missing_columns():
    agent = TechnicalAgent()
    # ohlc missing 'open'
    ohlc = [{'high': 60010, 'low': 59900, 'close': 60000}]
    res: AnalysisResult = await agent.analyze({'ohlc': ohlc})
    assert res.decision == 'HOLD'
    assert 'MISSING_COLUMN_open' in res.details.get('note', '')

@pytest.mark.asyncio
async def test_technical_agent_basic():
    agent = TechnicalAgent()
    ohlc = []
    # create 30 bars with required columns
    for i in range(30):
        ohlc.append({'open': 60000 + i, 'high': 60050 + i, 'low': 59950 + i, 'close': 60025 + i})
    res: AnalysisResult = await agent.analyze({'ohlc': ohlc})
    assert res.decision in ('BUY', 'SELL', 'HOLD')
    assert isinstance(res.details, dict)
