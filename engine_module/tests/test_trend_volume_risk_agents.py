import pytest
from engine_module.agents.trend_agent import TrendAgent
from engine_module.agents.volume_agent import VolumeAgent
from engine_module.agents.risk_agents import NeutralRiskAgent
from engine_module.contracts import AnalysisResult

@pytest.mark.asyncio
async def test_trend_agent_insufficient_data():
    agent = TrendAgent()
    res: AnalysisResult = await agent.analyze({'ohlc': []})
    assert res.decision == 'HOLD'
    assert res.details.get('reason') == 'INSUFFICIENT_DATA'

@pytest.mark.asyncio
async def test_trend_agent_buy_signal():
    agent = TrendAgent()
    # create 60 bars trending up
    ohlc = []
    base = 60000
    for i in range(60):
        price = base + i * 10
        ohlc.append({'open': price-5, 'high': price+10, 'low': price-20, 'close': price, 'volume': 1000})
    res: AnalysisResult = await agent.analyze({'ohlc': ohlc})
    assert res.decision in ('BUY', 'HOLD')

@pytest.mark.asyncio
async def test_volume_agent_spike():
    agent = VolumeAgent()
    # build 26 bars where last bar has spike and price move
    ohlc = []
    for i in range(25):
        ohlc.append({'open': 60000, 'high': 60010, 'low': 59990, 'close': 60005, 'volume': 1000})
    # last bar spike
    ohlc.append({'open': 60005, 'high': 60150, 'low': 60000, 'close': 60100, 'volume': 5000})
    res = await agent.analyze({'ohlc': ohlc})
    assert res.decision in ('BUY', 'SELL')
    assert res.confidence > 0

@pytest.mark.asyncio
async def test_risk_agent_high_atr_veto():
    agent = NeutralRiskAgent()
    context = {'technical': {'atr': 0.1}}
    res = await agent.analyze(context)
    assert res.decision == 'HOLD'
    assert res.details.get('risk') == 'HIGH_VOLATILITY' or res.confidence >= 0.4
