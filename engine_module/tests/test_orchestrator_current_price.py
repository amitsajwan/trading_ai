import pytest
from engine_module.enhanced_orchestrator import EnhancedTradingOrchestrator
from engine_module.orchestrator_stub import TradingOrchestrator
from engine_module.contracts import AnalysisResult


class DummyMarketProvider:
    async def get_ohlc_data(self, symbol: str, periods: int = 100):
        return [{'open': 100, 'high': 101, 'low': 99, 'close': 100}]

    async def get_latest_ticks(self, instrument: str, limit: int = 1):
        return [{'last_price': 55555.0}]


class FakeAgent:
    def __init__(self):
        self.last_context = None

    async def analyze(self, context):
        # capture context for assertions
        self.last_context = context
        return AnalysisResult(decision='HOLD', confidence=0.0, details={})


@pytest.mark.asyncio
async def test_enhanced_orchestrator_uses_latest_tick():
    market = DummyMarketProvider()
    agent = FakeAgent()

    orchestrator = EnhancedTradingOrchestrator(market_data_provider=market)
    # Override agents with our fake agent
    orchestrator.agents = {'fake': agent}

    await orchestrator.run_cycle({'symbol': 'BANKNIFTY'})

    assert agent.last_context is not None
    assert agent.last_context.get('current_price') == 55555.0


@pytest.mark.asyncio
async def test_orchestrator_stub_fetches_latest_tick(monkeypatch):
    market = DummyMarketProvider()
    orch = TradingOrchestrator(llm_client=None, market_data_provider=market)

    called = {'cp': None}

    def fake_create_signals_from_decision(analysis_result, instrument, technical_indicators=None, current_price=None, strategy_config=None):
        called['cp'] = current_price
        return []

    # Patch the function in signal_creator module
    import engine_module.signal_creator as sc
    monkeypatch.setattr(sc, 'create_signals_from_decision', fake_create_signals_from_decision)

    decision = AnalysisResult(decision='BUY', confidence=0.7, details={'reasoning': 'RSI > 30'})

    # Call method; current_price is None so stub should fetch latest tick
    await orch._create_signals_from_decision(decision, instrument='BANKNIFTY', current_price=None)

    assert called['cp'] == 55555.0
