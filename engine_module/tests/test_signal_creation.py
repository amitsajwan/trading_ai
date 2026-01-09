"""Tests for signal creation and lifecycle management."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from engine_module.contracts import AnalysisResult
from engine_module.signal_creator import (
    create_signals_from_decision,
    extract_conditions_from_reasoning,
    save_signal_to_mongodb,
    delete_pending_signals,
    sync_signals_to_monitor
)
from engine_module.signal_monitor import TradingCondition, ConditionOperator


def test_extract_conditions_from_reasoning():
    """Test condition extraction from reasoning text."""
    
    # Test RSI conditions
    reasoning1 = "RSI is below 30, indicating oversold condition. Buy when RSI crosses above 32."
    conditions = extract_conditions_from_reasoning(reasoning1)
    assert len(conditions) > 0
    assert any(c["indicator"] == "rsi_14" for c in conditions)
    
    # Test price conditions
    reasoning2 = "Price is currently 45000. Buy when price goes above 45500."
    conditions2 = extract_conditions_from_reasoning(reasoning2)
    assert len(conditions2) > 0
    assert any(c["indicator"] == "current_price" for c in conditions2)
    
    # Test empty reasoning
    conditions3 = extract_conditions_from_reasoning("")
    assert conditions3 == []


def test_create_signals_from_decision():
    """Test signal creation from orchestrator decision."""
    
    # Create sample analysis result
    decision = AnalysisResult(
        decision="BUY",
        confidence=0.75,
        details={
            "reasoning": "RSI is 28, indicating oversold. Buy when RSI crosses above 30.",
            "stop_loss": 44800.0,
            "take_profit": 46000.0
        }
    )
    
    # Create signals
    signals = create_signals_from_decision(
        analysis_result=decision,
        instrument="BANKNIFTY",
        current_price=45000.0,
        technical_indicators={"rsi_14": 28.5}
    )
    
    assert len(signals) > 0
    signal = signals[0]
    assert signal.instrument == "BANKNIFTY"
    assert signal.action == "BUY"
    assert signal.confidence == 0.75
    assert signal.stop_loss == 44800.0
    assert signal.take_profit == 46000.0
    assert signal.is_active is True
    
    # Test HOLD decision (should not create signals)
    hold_decision = AnalysisResult(decision="HOLD", confidence=0.5, details={})
    signals_hold = create_signals_from_decision(hold_decision, "BANKNIFTY")
    assert len(signals_hold) == 0


@pytest.mark.asyncio
async def test_save_signal_to_mongodb():
    """Test saving signal to MongoDB."""
    
    # Create mock MongoDB
    mock_collection = Mock()
    mock_collection.insert_one.return_value.inserted_id = "test_id_123"
    mock_db = {"signals": mock_collection}
    
    # Create test signal
    signal = TradingCondition(
        condition_id="test_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.GREATER_THAN,
        threshold=30.0,
        action="BUY"
    )
    
    # Save signal
    signal_id = await save_signal_to_mongodb(signal, mock_db)
    
    assert signal_id == "test_id_123"
    assert mock_collection.insert_one.called
    call_args = mock_collection.insert_one.call_args[0][0]
    assert call_args["condition_id"] == "test_001"
    assert call_args["instrument"] == "BANKNIFTY"
    assert call_args["status"] == "pending"


@pytest.mark.asyncio
async def test_delete_pending_signals():
    """Test deleting pending signals."""
    
    # Create mock MongoDB
    mock_collection = Mock()
    mock_collection.delete_many.return_value.deleted_count = 5
    mock_db = {"signals": mock_collection}
    
    # Delete pending signals
    deleted_count = await delete_pending_signals(mock_db, instrument="BANKNIFTY")
    
    assert deleted_count == 5
    assert mock_collection.delete_many.called
    query = mock_collection.delete_many.call_args[0][0]
    assert query["status"] == {"$in": ["pending", "expired"]}
    assert query["instrument"] == "BANKNIFTY"


@pytest.mark.asyncio
async def test_sync_signals_to_monitor():
    """Test syncing MongoDB signals to SignalMonitor."""
    
    # Create mock MongoDB with signals
    mock_signal_doc = {
        "condition_id": "test_001",
        "instrument": "BANKNIFTY",
        "indicator": "rsi_14",
        "operator": ">",
        "threshold": 30.0,
        "action": "BUY",
        "status": "pending",
        "is_active": True,
        "created_at": datetime.now().isoformat()
    }
    mock_collection = Mock()
    mock_collection.find.return_value = [mock_signal_doc]
    mock_db = {"signals": mock_collection}
    
    # Create mock SignalMonitor
    mock_monitor = Mock()
    mock_monitor.add_signal = Mock()
    
    # Sync signals
    synced_count = await sync_signals_to_monitor(mock_db, mock_monitor, instrument="BANKNIFTY")
    
    assert synced_count == 1
    assert mock_monitor.add_signal.called


def test_signal_lifecycle_flow():
    """Test complete signal lifecycle flow."""
    
    # Step 1: Create signal from decision
    decision = AnalysisResult(
        decision="BUY",
        confidence=0.8,
        details={"reasoning": "Buy when RSI > 30"}
    )
    
    signals = create_signals_from_decision(decision, "BANKNIFTY", current_price=45000.0)
    assert len(signals) == 1
    
    signal = signals[0]
    assert signal.is_active is True
    assert signal.action == "BUY"
    
    # Step 2: Signal should have proper structure
    assert signal.condition_id is not None
    assert signal.indicator in ["rsi_14", "current_price"]  # Should extract from reasoning or use default
    assert signal.expires_at is not None
    
    # Step 3: Signal should be ready for monitoring
    assert signal.confidence > 0
    assert signal.position_size > 0
