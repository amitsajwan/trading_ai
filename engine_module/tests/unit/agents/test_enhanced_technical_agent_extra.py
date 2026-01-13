import pytest
from engine_module.agents.enhanced_technical_agent import EnhancedTechnicalAgent


@pytest.mark.asyncio
async def test_enhanced_technical_agent_basic_smoke():
    agent = EnhancedTechnicalAgent()
    indicators = {
        'rsi_14': 65.0,
        'macd_value': 1.2,
        'macd_signal': 0.5,
        'volume_ratio': 1.3,
        'current_price': 100.0,
        'sma_20': 98.0,
        'sma_50': 95.0,
        'adx_14': 30.0,
        'bollinger_upper': 105.0,
        'bollinger_lower': 95.0,
        'bollinger_middle': 100.0
    }

    res = await agent.analyze({'indicators': indicators})
    assert res is not None
    assert isinstance(res.decision, str)
    assert 0.0 <= res.confidence <= 1.0
    assert isinstance(res.details, dict)
