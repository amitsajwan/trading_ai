from engine_module.contracts import Orchestrator, Agent, AnalysisResult
from engine_module.enhanced_orchestrator import TradingDecision
from datetime import datetime


def test_analysis_result_fields():
    res = AnalysisResult(decision="hold", confidence=0.5)
    assert res.decision == "hold"
    assert res.confidence == 0.5


def test_protocols_exist():
    assert hasattr(Orchestrator, "run_cycle")
    assert hasattr(Agent, "analyze")


def test_trading_decision_fields():
    """Test TradingDecision dataclass fields."""
    decision = TradingDecision(
        action="BUY",
        confidence=0.75,
        reasoning="Test reasoning",
        entry_price=23000.0,
        stop_loss=22800.0,
        take_profit=23500.0,
        quantity=10,
        risk_amount=200.0,
        agent_signals={},
        timestamp=datetime.now(),
        position_action="OPEN_NEW"
    )
    
    assert decision.action == "BUY"
    assert decision.confidence == 0.75
    assert decision.position_action == "OPEN_NEW"
    assert decision.entry_price == 23000.0
    assert decision.quantity == 10


def test_trading_decision_to_dict():
    """Test TradingDecision to_dict method includes position_action."""
    decision = TradingDecision(
        action="BUY",
        confidence=0.75,
        reasoning="Test",
        entry_price=23000.0,
        stop_loss=22800.0,
        take_profit=23500.0,
        quantity=10,
        risk_amount=200.0,
        agent_signals={},
        timestamp=datetime.now(),
        position_action="ADD_TO_LONG"
    )
    
    decision_dict = decision.to_dict()
    assert decision_dict['action'] == "BUY"
    assert decision_dict['position_action'] == "ADD_TO_LONG"
    assert 'agent_signals' in decision_dict
    assert 'timestamp' in decision_dict

