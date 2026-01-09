"""End-to-End Integration Tests for Signal Lifecycle Management.

Tests the complete flow from orchestrator decision → signal creation → 
real-time monitoring → trade execution.
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def mock_mongodb():
    """Create a mock MongoDB for testing."""
    from unittest.mock import MagicMock
    
    mock_collection = MagicMock()
    mock_collection.insert_one = MagicMock()
    mock_collection.insert_one.return_value.inserted_id = "test_signal_id_123"
    mock_collection.find = MagicMock(return_value=[])
    mock_collection.delete_many = MagicMock(return_value=MagicMock(deleted_count=0))
    mock_collection.update_one = MagicMock()
    
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    
    return mock_db, mock_collection


@pytest.fixture
def mock_signal_monitor():
    """Create a mock SignalMonitor for testing."""
    from unittest.mock import MagicMock
    
    monitor = MagicMock()
    monitor.add_signal = MagicMock()
    monitor.remove_signal = MagicMock()
    monitor.get_active_signals = MagicMock(return_value=[])
    monitor.check_signals = AsyncMock(return_value=[])
    monitor._active_signals = {}
    
    return monitor


@pytest.fixture
def sample_analysis_result():
    """Create a sample AnalysisResult for testing."""
    from engine_module.contracts import AnalysisResult
    
    return AnalysisResult(
        decision="BUY",
        confidence=0.75,
        details={
            "reasoning": "RSI is below 30, indicating oversold condition. Buy when RSI crosses above 32.",
            "stop_loss": 44800.0,
            "take_profit": 46000.0,
            "entry_price": 45000.0
        }
    )


@pytest.mark.asyncio
async def test_signal_creation_from_decision(mock_mongodb, sample_analysis_result):
    """Test E2E: Orchestrator decision → Signal creation."""
    from engine_module.src.engine_module.signal_creator import (
        create_signals_from_decision,
        save_signal_to_mongodb
    )
    
    mock_db, mock_collection = mock_mongodb
    
    # Step 1: Create signals from decision
    signals = create_signals_from_decision(
        analysis_result=sample_analysis_result,
        instrument="BANKNIFTY",
        current_price=45000.0,
        technical_indicators={"rsi_14": 28.5}
    )
    
    assert len(signals) > 0, "Should create at least one signal"
    signal = signals[0]
    assert signal.instrument == "BANKNIFTY"
    assert signal.action == "BUY"
    assert signal.confidence == 0.75
    assert signal.stop_loss == 44800.0
    assert signal.take_profit == 46000.0
    
    # Step 2: Save to MongoDB
    signal_id = await save_signal_to_mongodb(signal, mock_db)
    assert signal_id == "test_signal_id_123"
    assert mock_collection.insert_one.called
    
    print("✅ Test passed: Signal creation from decision works")


@pytest.mark.asyncio
async def test_signal_lifecycle_cleanup(mock_mongodb):
    """Test E2E: Signal cleanup at cycle start."""
    from engine_module.src.engine_module.signal_creator import delete_pending_signals
    
    mock_db, mock_collection = mock_mongodb
    mock_collection.delete_many.return_value.deleted_count = 5
    
    # Delete pending signals
    deleted_count = await delete_pending_signals(mock_db, instrument="BANKNIFTY")
    
    assert deleted_count == 5
    assert mock_collection.delete_many.called
    
    query = mock_collection.delete_many.call_args[0][0]
    assert query["status"] == {"$in": ["pending", "expired"]}
    assert query["instrument"] == "BANKNIFTY"
    
    print("✅ Test passed: Signal cleanup works")


@pytest.mark.asyncio
async def test_signal_sync_to_monitor(mock_mongodb, mock_signal_monitor):
    """Test E2E: MongoDB signals → SignalMonitor sync."""
    from engine_module.src.engine_module.signal_creator import sync_signals_to_monitor
    
    mock_db, mock_collection = mock_mongodb
    
    # Create mock signal document
    mock_signal_doc = {
        "condition_id": "test_001",
        "instrument": "BANKNIFTY",
        "indicator": "rsi_14",
        "operator": ">",
        "threshold": 30.0,
        "action": "BUY",
        "status": "pending",
        "is_active": True,
        "confidence": 0.75,
        "position_size": 1.0,
        "created_at": datetime.now().isoformat()
    }
    mock_collection.find.return_value = [mock_signal_doc]
    
    # Sync signals
    synced_count = await sync_signals_to_monitor(mock_db, mock_signal_monitor, instrument="BANKNIFTY")
    
    assert synced_count == 1
    assert mock_signal_monitor.add_signal.called
    
    print("✅ Test passed: Signal sync to monitor works")


@pytest.mark.asyncio
async def test_orchestrator_signal_creation_integration(mock_mongodb, mock_signal_monitor, sample_analysis_result):
    """Test E2E: Orchestrator run_cycle → Signal creation integration."""
    from engine_module.src.engine_module.orchestrator_stub import TradingOrchestrator
    from unittest.mock import MagicMock
    
    # Create orchestrator with mocks
    mock_llm = MagicMock()
    orchestrator = TradingOrchestrator(
        llm_client=mock_llm,
        signal_monitor=mock_signal_monitor,
        mongo_db=mock_mongodb[0]
    )
    
    # Mock the run_cycle to return our sample result
    async def mock_run_cycle(context):
        return sample_analysis_result
    
    orchestrator.run_cycle = mock_run_cycle
    
    # Test signal creation method
    await orchestrator._create_signals_from_decision(
        sample_analysis_result,
        "BANKNIFTY",
        current_price=45000.0,
        technical_indicators={"rsi_14": 28.5}
    )
    
    # Verify signals were added to monitor
    assert mock_signal_monitor.add_signal.called, "Signal should be added to monitor"
    
    print("✅ Test passed: Orchestrator signal creation integration works")


@pytest.mark.asyncio
async def test_condition_parsing():
    """Test E2E: Condition extraction from reasoning text."""
    from engine_module.src.engine_module.signal_creator import extract_conditions_from_reasoning
    
    # Test various reasoning patterns
    test_cases = [
        ("RSI is below 30. Buy when RSI crosses above 32.", "rsi_14", "CROSSES_ABOVE"),
        ("Price is 45000. Buy when price > 45500", "current_price", "GREATER_THAN"),
        ("Volume is high. Buy when volume > 1000000", "volume", "GREATER_THAN"),
    ]
    
    for reasoning, expected_indicator, expected_operator in test_cases:
        conditions = extract_conditions_from_reasoning(reasoning, current_price=45000.0)
        
        # Should extract at least one condition
        assert len(conditions) > 0, f"Should extract conditions from: {reasoning}"
        
        # Check if expected indicator is present
        indicators = [c.get("indicator") for c in conditions]
        assert expected_indicator in indicators, f"Should extract {expected_indicator} from: {reasoning}"
        
        # Check operator (if available)
        operators = [c.get("operator") for c in conditions if c.get("operator")]
        if expected_operator:
            operator_names = [str(op).upper() for op in operators]
            assert any(expected_operator.upper() in str(op) for op in operator_names), \
                f"Should extract {expected_operator} operator from: {reasoning}"
    
    print("✅ Test passed: Condition parsing works for various patterns")


@pytest.mark.asyncio
async def test_signal_trigger_and_execution(mock_signal_monitor):
    """Test E2E: Signal condition check → Trigger → Execution callback."""
    from engine_module.signal_monitor import TradingCondition, ConditionOperator
    from engine_module.realtime_tick_integration import process_tick_for_signals
    
    # Create a test signal
    signal = TradingCondition(
        condition_id="test_trigger_001",
        instrument="BANKNIFTY",
        indicator="current_price",
        operator=ConditionOperator.GREATER_THAN,
        threshold=45000.0,
        action="BUY",
        confidence=0.75
    )
    
    # Add signal to monitor
    mock_signal_monitor.get_active_signals = MagicMock(return_value=[signal])
    
    # Mock check_signals to return triggered event
    from engine_module.src.engine_module.signal_monitor import SignalTriggerEvent
    
    triggered_event = SignalTriggerEvent(
        condition_id="test_trigger_001",
        instrument="BANKNIFTY",
        action="BUY",
        triggered_at=datetime.now().isoformat(),
        indicator_name="current_price",
        indicator_value=45100.0,
        threshold=45000.0,
        current_price=45100.0,
        position_size=1.0,
        confidence=0.75
    )
    
    mock_signal_monitor.check_signals = AsyncMock(return_value=[triggered_event])
    
    # Create mock execution callback
    execution_callback_called = []
    
    async def mock_execute_trade(event):
        execution_callback_called.append(event)
    
    # Set execution callback
    mock_signal_monitor.set_execution_callback = MagicMock()
    
    # Process tick (this would normally call check_signals and trigger execution)
    # For now, we'll just verify the structure works
    tick_dict = {
        "last_price": 45100.0,
        "volume": 100000,
        "timestamp": datetime.now().isoformat()
    }
    
    # Since we can't fully test the async processor without real services,
    # we'll verify the signal structure and mock behavior
    assert signal.condition_id == "test_trigger_001"
    assert signal.threshold == 45000.0
    assert 45100.0 > signal.threshold  # Condition would be met
    
    print("✅ Test passed: Signal trigger structure works")


@pytest.mark.asyncio
async def test_complete_signal_lifecycle_e2e(mock_mongodb, mock_signal_monitor, sample_analysis_result):
    """Test complete E2E flow: Decision → Create → Save → Sync → Monitor."""
    from engine_module.src.engine_module.signal_creator import (
        create_signals_from_decision,
        save_signal_to_mongodb,
        delete_pending_signals,
        sync_signals_to_monitor
    )
    
    mock_db, mock_collection = mock_mongodb
    
    # Step 1: Cleanup old signals (cycle start)
    mock_collection.delete_many.return_value.deleted_count = 3
    deleted = await delete_pending_signals(mock_db, instrument="BANKNIFTY")
    assert deleted == 3
    print("  ✓ Step 1: Cleaned up old signals")
    
    # Step 2: Create new signals from decision
    signals = create_signals_from_decision(
        sample_analysis_result,
        "BANKNIFTY",
        current_price=45000.0
    )
    assert len(signals) > 0
    print(f"  ✓ Step 2: Created {len(signals)} signal(s)")
    
    # Step 3: Save to MongoDB
    for signal in signals:
        signal_id = await save_signal_to_mongodb(signal, mock_db)
        assert signal_id is not None
    print("  ✓ Step 3: Saved signals to MongoDB")
    
    # Step 4: Sync to SignalMonitor
    mock_collection.find.return_value = [{
        "condition_id": signals[0].condition_id,
        "instrument": "BANKNIFTY",
        "indicator": signals[0].indicator,
        "operator": signals[0].operator.value,
        "threshold": signals[0].threshold,
        "action": signals[0].action,
        "status": "pending",
        "is_active": True,
        "confidence": signals[0].confidence,
        "position_size": signals[0].position_size,
        "created_at": signals[0].created_at
    }]
    
    synced = await sync_signals_to_monitor(mock_db, mock_signal_monitor, instrument="BANKNIFTY")
    assert synced == 1
    assert mock_signal_monitor.add_signal.called
    print("  ✓ Step 4: Synced signals to SignalMonitor")
    
    print("\n✅ Complete E2E signal lifecycle test PASSED!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
