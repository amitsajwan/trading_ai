import pytest
from engine_module.contracts import AnalysisResult
from engine_module.signal_creator import create_signals_from_decision
from engine_module.signal_monitor import SignalMonitor, TradingCondition, ConditionOperator


class FakeTechnicalService:
    def __init__(self, indicators):
        self._indicators = indicators

    def get_indicators_dict(self, instrument):
        return self._indicators


@pytest.mark.asyncio
async def test_signal_creation_and_realtime_trigger():
    # Build a synthetic AnalysisResult with a reasoning that contains an RSI condition
    analysis = AnalysisResult(
        decision="BUY",
        confidence=0.75,
        details={
            "reasoning": "RSI > 30 and volume > 100000",
            "entry_price": 100.0
        }
    )

    # Create signals from the analysis result
    signals = create_signals_from_decision(analysis, instrument="BANKNIFTY", current_price=100.0)

    assert signals, "Expected at least one TradingCondition to be created"

    # Prepare a SignalMonitor with a technical service that meets the condition
    indicators = {
        "rsi_14": 35.0,
        "volume": 200000,
        "current_price": 100.0
    }
    tech_service = FakeTechnicalService(indicators)
    monitor = SignalMonitor(technical_service=tech_service)

    # Register the signal and run the check
    cond = signals[0]
    monitor.add_signal(cond)

    triggered = await monitor.check_signals("BANKNIFTY")

    assert triggered, "Expected the signal to trigger based on provided indicators"
    event = triggered[0]
    assert event.action in ("BUY", "SELL")
    assert event.indicator_value is not None
    assert event.current_price == indicators.get("current_price")
