import pytest
from types import SimpleNamespace

from engine_module.api import build_orchestrator
from engine_module.execution_adapters import BacktestExecutionAdapter
from engine_module.enhanced_orchestrator import TradingContext


class FakeLLM:
    async def generate(self, request):
        # minimal judge-compatible payload
        class R:
            content = (
                '{'
                '"final_decision":"BUY",'
                '"confidence":0.8,'
                '"reasoning":"Test judge reasoning.",'
                '"valid_for_minutes":15,'
                '"signals":[{'
                '"signal_type":"ENTRY","action":"BUY","execution_mode":"CONDITIONAL",'
                '"position_size":1.0,"confidence":0.8,'
                '"entry_price":45000,"stop_loss":44750,"take_profit":45500,'
                '"conditions":[{"indicator":"current_price","operator":">","threshold":44900}],'
                '"rationale":"enter on price confirmation"'
                '}]'
                '}'
            )
        return R()


class FakeMongoClient:
    def __getitem__(self, name):
        return {}


class FakeMongoDB(dict):
    # mimic pymongo Database by exposing .client
    @property
    def client(self):
        return FakeMongoClient()


@pytest.mark.asyncio
async def test_build_orchestrator_all_modes_use_trading_orchestrator():
    # Test that all modes now use the same TradingOrchestrator with judge + signals
    for mode in ["LIVE", "PAPER", "BACKTEST"]:
        ctx = TradingContext(instrument="BANKNIFTY", mode=mode, run_id=f"t_{mode}")
        orch = build_orchestrator(
            llm_client=FakeLLM(),
            redis_client=None,
            mongo_db=FakeMongoDB(),
            agents=[],
            context=ctx,
        )
        # All modes should use TradingOrchestrator now
        from engine_module.orchestrator_stub import TradingOrchestrator
        assert isinstance(orch, TradingOrchestrator)
        # Should have mode in config
        assert orch.config.get("mode") == mode


@pytest.mark.asyncio
async def test_backtest_execution_adapter_decimal_safe():
    ad = BacktestExecutionAdapter(mode="BACKTEST", run_id="t2", redis_client=None, mongo_client=None)
    res = await ad.execute_trading_decision(
        instrument="BANKNIFTY",
        decision="BUY",
        confidence=0.8,
        analysis_details={"current_price": 45000.0, "entry_price": 45000.0, "quantity": 1},
        position_manager=None,
    )
    assert res is not None
    assert res["side"] == "BUY"

