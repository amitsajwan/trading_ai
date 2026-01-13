import pytest
from engine_module.contracts import AnalysisResult
from engine_module.src.engine_module.enhanced_orchestrator import EnhancedTradingOrchestrator


class DummyMarketProvider:
    async def get_ohlc_data(self, symbol: str, periods: int = 100):
        return [{'open': 100, 'high': 101, 'low': 99, 'close': 100}]


class FakeAgent:
    async def analyze(self, context):
        return AnalysisResult(decision='BUY', confidence=0.5, details=None)


@pytest.mark.asyncio
async def test_orchestrator_standardizes_agent_result():
    orchestrator = EnhancedTradingOrchestrator(market_data_provider=DummyMarketProvider())
    fake_agent = FakeAgent()

    # Call protected method directly to test standardization behavior
    res = await orchestrator._run_single_agent('FakeAgent', fake_agent, {})

    assert res is not None
    assert res.agent == 'FakeAgent'
    assert isinstance(res.details, dict)
    assert res.details.get('agent') == 'FakeAgent'
