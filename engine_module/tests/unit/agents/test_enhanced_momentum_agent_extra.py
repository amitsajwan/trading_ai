import pytest
from engine_module.agents.enhanced_momentum_agent import EnhancedMomentumAgent


@pytest.mark.asyncio
async def test_enhanced_momentum_agent_smoke():
    agent = EnhancedMomentumAgent()

    market_data = {'close': 100.0, 'rsi': 28.0, 'volume_ratio': 1.6, 'adx': 26.0, 'instrument': 'BANKNIFTY'}
    technical_indicators = {'rsi': 28.0, 'macd': 0.5, 'macd_signal': 0.1, 'ema_50': 98.0, 'volume_ratio': 1.6}
    multi_timeframe = {'15m': {'rsi': 25.0}, '1h': {'rsi': 27.0}, 'daily': {'rsi': 40.0}}

    res = await agent.analyze({
        'market_data': market_data,
        'technical_indicators': technical_indicators,
        'multi_timeframe': multi_timeframe,
        'current_positions': []
    })

    assert res is not None
    assert isinstance(res.decision, str)
    assert 0.0 <= res.confidence <= 1.0
    assert isinstance(res.details, dict)
