import pytest
from engine_module.agents.options_analysis_agent import OptionsAnalysisAgent


@pytest.mark.asyncio
async def test_options_analysis_agent_recommends_strategy():
    agent = OptionsAnalysisAgent()

    # Minimal calls/puts data
    calls = [
        {'strike': 100.0, 'price': 10.0, 'oi': 100, 'iv': 20.0, 'delta': 0.5},
        {'strike': 105.0, 'price': 3.0, 'oi': 50, 'iv': 18.0, 'delta': 0.3}
    ]
    puts = [
        {'strike': 100.0, 'price': 12.0, 'oi': 80, 'iv': 21.0, 'delta': -0.5},
        {'strike': 95.0, 'price': 4.0, 'oi': 40, 'iv': 19.0, 'delta': -0.3}
    ]

    res = await agent.analyze({'calls': calls, 'puts': puts, 'underlying_price': 100.0, 'pcr': 1.0, 'max_pain': 100.0, 'consensus_direction': 'HOLD'})

    assert res is not None
    assert isinstance(res.decision, str)
    assert 0.0 <= res.confidence <= 1.0
    assert isinstance(res.details, dict)
