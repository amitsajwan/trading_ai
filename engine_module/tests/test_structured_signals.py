import pytest
from types import SimpleNamespace

from engine_module.signal_creator import create_signals_from_decision


def make_analysis_result_with_structured_signals():
    return SimpleNamespace(
        decision="BUY",
        confidence=0.82,
        details={
            "valid_for_minutes": 15,
            "signals": [
                {
                    "signal_type": "ENTRY",
                    "action": "BUY",
                    "execution_mode": "CONDITIONAL",
                    "position_size": 1.0,
                    "confidence": 0.82,
                    "entry_price": 45000,
                    "stop_loss": 44750,
                    "take_profit": 45500,
                    "conditions": [
                        {"indicator": "rsi_14", "operator": "crosses_above", "threshold": 50},
                        {"indicator": "current_price", "operator": ">", "threshold": 44900},
                    ],
                    "rationale": "Enter on momentum confirmation; price must hold above support.",
                },
                {
                    "signal_type": "EXIT",
                    "action": "CLOSE_LONG",
                    "execution_mode": "CONDITIONAL",
                    "position_size": 1.0,
                    "confidence": 0.75,
                    "conditions": [
                        {"indicator": "rsi_14", "operator": "crosses_below", "threshold": 45},
                    ],
                    "rationale": "Exit if momentum breaks down.",
                },
            ],
        },
    )


def test_create_signals_from_structured_specs():
    ar = make_analysis_result_with_structured_signals()
    signals = create_signals_from_decision(ar, instrument="BANKNIFTY", current_price=45010.0)
    assert len(signals) == 2

    entry = signals[0]
    assert entry.instrument == "BANKNIFTY"
    assert entry.action == "BUY"
    assert entry.indicator == "rsi_14"
    assert entry.operator.value in ("crosses_above",)  # enum value
    assert entry.stop_loss == 44750
    assert entry.take_profit == 45500
    assert entry.execution_mode == "CONDITIONAL"
    assert entry.expires_at is not None

    exit_sig = signals[1]
    assert exit_sig.action == "CLOSE_LONG"
    assert exit_sig.indicator == "rsi_14"
    assert exit_sig.operator.value in ("crosses_below",)


def test_judge_decision_includes_agent_info():
    """Test that judge-generated decisions include agent information for UI display."""
    from types import SimpleNamespace
    from engine_module.orchestrator_stub import TradingOrchestrator

    # Create mock agent results
    agent_results = [
        SimpleNamespace(agent="TechnicalAgent", decision="BUY", confidence=0.7),
        SimpleNamespace(agent="MomentumAgent", decision="HOLD", confidence=0.5),
        SimpleNamespace(agent="ResearchManager", decision="SELL", confidence=0.6)
    ]

    # Create orchestrator instance
    orchestrator = TradingOrchestrator(llm_client=None, agents=[])

    # Simulate judge response parsing
    mock_llm_response = SimpleNamespace(
        content='{"decision":"IRON_CONDOR","confidence":0.6,"reasoning":"Test reasoning","valid_for_minutes":15}'
    )

    aggregated = {"options_strategy": "IRON_CONDOR"}
    position_data = {"positions": []}

    # Parse judge response
    result = orchestrator._parse_llm_response(mock_llm_response, aggregated, agent_results, position_data)

    # Verify agent information is included
    assert "agent_snapshot" in result.details
    assert len(result.details["agent_snapshot"]) == 3
    assert result.details["agent_snapshot"][0]["agent"] == "TechnicalAgent"
    assert result.details["agent_snapshot"][0]["decision"] == "BUY"
    assert result.details["agent_snapshot"][0]["confidence"] == 0.7

    # Verify aggregated analysis is created for UI
    assert "aggregated_analysis" in result.details
    agg = result.details["aggregated_analysis"]
    assert "agent_breakdown" in agg
    assert agg["agent_breakdown"]["buy_signals"] == 1
    assert agg["agent_breakdown"]["sell_signals"] == 1
    assert agg["agent_breakdown"]["hold_signals"] == 1
    assert agg["agent_breakdown"]["total_agents"] == 3

