"""Comprehensive Test Suite: Real-time Signal-to-Trade System.

Tests the complete integration:
1. TechnicalIndicatorsService - Real-time indicator calculation
2. SignalMonitor - Conditional signal monitoring
3. RealtimeSignalProcessor - Integration layer
4. End-to-end flow - Agent → Signal → Monitor → Execute
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

# Add paths
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Import TimeService for virtual time support
try:
    from core_kernel.src.core_kernel.time_service import now as get_system_time
except ImportError:
    # Fallback to real time if TimeService not available
    def get_system_time():
        return datetime.now()

from engine_module.src.engine_module.signal_monitor import (
    SignalMonitor,
    TradingCondition,
    ConditionOperator,
    SignalTriggerEvent,
    get_signal_monitor
)
from engine_module.src.engine_module.realtime_signal_integration import (
    RealtimeSignalProcessor,
    create_realtime_processor
)
from market_data.src.market_data.technical_indicators_service import (
    get_technical_service,
    TechnicalIndicators
)
from engine_module.src.engine_module.agents.enhanced_technical_agent import (
    EnhancedTechnicalAgent
)

logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def record_pass(self, test_name: str):
        self.passed += 1
        print(f"  [PASS] {test_name}")
    
    def record_fail(self, test_name: str, reason: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {reason}")
        print(f"  [FAIL] {test_name}: {reason}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        print(f"{'='*70}")
        if self.errors:
            print("\nFailures:")
            for error in self.errors:
                print(f"  - {error}")
        return self.failed == 0


results = TestResults()


def test_technical_service_singleton():
    """Test 1: TechnicalIndicatorsService singleton pattern."""
    print("\n[Test Suite 1] TechnicalIndicatorsService")
    print("-" * 70)
    
    try:
        service1 = get_technical_service()
        service2 = get_technical_service()
        
        if service1 is service2:
            results.record_pass("Singleton pattern works")
        else:
            results.record_fail("Singleton pattern works", "Different instances returned")
    except Exception as e:
        results.record_fail("Singleton pattern works", str(e))


def test_technical_service_indicators():
    """Test 2: Indicator calculation."""
    try:
        service = get_technical_service()
        
        # Warm up with candles
        for i in range(50):
            candle = {
                "timestamp": get_system_time().isoformat(),
                "open": 45000 + i,
                "high": 45020 + i,
                "low": 44980 + i,
                "close": 45010 + i,
                "volume": 1500
            }
            service.update_candle("TEST_INST", candle)
        
        # Update tick
        tick = {
            "last_price": 45123.50,
            "volume": 1800,
            "timestamp": get_system_time().isoformat()
        }
        indicators = service.update_tick("TEST_INST", tick)
        
        # Verify indicators calculated
        if indicators.rsi_14 is not None:
            results.record_pass("RSI calculation")
        else:
            results.record_fail("RSI calculation", "RSI is None")
        
        if indicators.current_price == 45123.50:
            results.record_pass("Current price tracking")
        else:
            results.record_fail("Current price tracking", f"Expected 45123.50, got {indicators.current_price}")
        
        # Test get_indicators
        retrieved = service.get_indicators("TEST_INST")
        if retrieved is not None:
            results.record_pass("get_indicators() retrieval")
        else:
            results.record_fail("get_indicators() retrieval", "Returns None")
        
        # Test get_indicators_dict
        indicators_dict = service.get_indicators_dict("TEST_INST")
        if isinstance(indicators_dict, dict) and "rsi_14" in indicators_dict:
            results.record_pass("get_indicators_dict() retrieval")
        else:
            results.record_fail("get_indicators_dict() retrieval", "Invalid dict format")
        
    except Exception as e:
        results.record_fail("Indicator calculation", str(e))


def test_signal_monitor_basic():
    """Test 3: SignalMonitor basic operations."""
    print("\n[Test Suite 2] SignalMonitor Basic Operations")
    print("-" * 70)
    
    try:
        monitor = SignalMonitor()
        
        # Test add_signal
        condition = TradingCondition(
            condition_id="test_basic_001",
            instrument="BANKNIFTY",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY"
        )
        
        signal_id = monitor.add_signal(condition)
        if signal_id == "test_basic_001":
            results.record_pass("add_signal()")
        else:
            results.record_fail("add_signal()", f"Expected test_basic_001, got {signal_id}")
        
        # Test get_active_signals
        active = monitor.get_active_signals("BANKNIFTY")
        if len(active) == 1 and active[0].condition_id == "test_basic_001":
            results.record_pass("get_active_signals()")
        else:
            results.record_fail("get_active_signals()", f"Expected 1 signal, got {len(active)}")
        
        # Test remove_signal
        removed = monitor.remove_signal("test_basic_001")
        if removed:
            results.record_pass("remove_signal()")
        else:
            results.record_fail("remove_signal()", "Failed to remove")
        
        active_after = monitor.get_active_signals("BANKNIFTY")
        if len(active_after) == 0:
            results.record_pass("Signal removed from active list")
        else:
            results.record_fail("Signal removed from active list", f"Still has {len(active_after)} signals")
        
    except Exception as e:
        results.record_fail("SignalMonitor basic operations", str(e))


async def test_signal_monitor_triggering():
    """Test 4: Signal triggering logic."""
    print("\n[Test Suite 3] SignalMonitor Triggering")
    print("-" * 70)
    
    try:
        tech_service = get_technical_service()
        monitor = SignalMonitor(technical_service=tech_service)
        
        # Warm up
        for i in range(50):
            candle = {
                "timestamp": get_system_time().isoformat(),
                "open": 45000 + i,
                "high": 45020 + i,
                "low": 44980 + i,
                "close": 45010 + i,
                "volume": 1500
            }
            tech_service.update_candle("BANKNIFTY", candle)
        
        # Create signal with GREATER_THAN
        condition = TradingCondition(
            condition_id="test_trigger_gt",
            instrument="BANKNIFTY",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY"
        )
        monitor.add_signal(condition)
        
        # Update ticks to push RSI above threshold
        triggered = False
        for i in range(30):
            tick = {
                "last_price": 45000 + (i * 20),
                "volume": 1800,
                "timestamp": get_system_time().isoformat()
            }
            tech_service.update_tick("BANKNIFTY", tick)
            
            events = await monitor.check_signals("BANKNIFTY")
            if events:
                triggered = True
                if events[0].action == "BUY" and events[0].indicator_name == "rsi_14":
                    results.record_pass("GREATER_THAN operator triggers")
                else:
                    results.record_fail("GREATER_THAN operator triggers", "Invalid event data")
                break
        
        if not triggered:
            results.record_fail("GREATER_THAN operator triggers", "Signal never triggered")
        
        # Test that triggered signal is removed
        active_after = monitor.get_active_signals("BANKNIFTY")
        if len(active_after) == 0:
            results.record_pass("Triggered signal auto-removed")
        else:
            results.record_fail("Triggered signal auto-removed", f"Still has {len(active_after)} active")
        
        # Test get_triggered_signals
        history = monitor.get_triggered_signals()
        if len(history) > 0:
            results.record_pass("Triggered signals stored in history")
        else:
            results.record_fail("Triggered signals stored in history", "No history found")
        
    except Exception as e:
        results.record_fail("Signal triggering", str(e))


async def test_multi_condition():
    """Test 5: Multi-condition signals."""
    print("\n[Test Suite 4] Multi-Condition Signals")
    print("-" * 70)
    
    try:
        tech_service = get_technical_service()
        monitor = SignalMonitor(technical_service=tech_service)
        
        # Warm up
        for i in range(50):
            candle = {
                "timestamp": get_system_time().isoformat(),
                "open": 45000,
                "high": 45020,
                "low": 44980,
                "close": 45000,
                "volume": 1500
            }
            tech_service.update_candle("TEST_MULTI", candle)
        
        # Create multi-condition signal
        condition = TradingCondition(
            condition_id="test_multi_001",
            instrument="TEST_MULTI",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY",
            additional_conditions=[
                {"indicator": "current_price", "operator": ">", "threshold": 45100}
            ]
        )
        monitor.add_signal(condition)
        
        # Test with only primary condition met (RSI > 50 but price < 45100)
        partial_triggered = False
        for i in range(10):
            tick = {
                "last_price": 45000,  # Below 45100
                "volume": 1800,
                "timestamp": get_system_time().isoformat()
            }
            tech_service.update_tick("TEST_MULTI", tick)
            events = await monitor.check_signals("TEST_MULTI")
            if events:
                partial_triggered = True
                break
        
        if not partial_triggered:
            results.record_pass("Multi-condition: Partial conditions don't trigger")
        else:
            results.record_fail("Multi-condition: Partial conditions don't trigger", "Triggered with partial conditions")
        
        # Now meet all conditions
        full_triggered = False
        for i in range(15):
            tick = {
                "last_price": 45100 + (i * 10),  # Above 45100
                "volume": 1800,
                "timestamp": get_system_time().isoformat()
            }
            tech_service.update_tick("TEST_MULTI", tick)
            events = await monitor.check_signals("TEST_MULTI")
            if events:
                full_triggered = True
                break
        
        if full_triggered:
            results.record_pass("Multi-condition: All conditions trigger")
        else:
            results.record_fail("Multi-condition: All conditions trigger", "Never triggered with all conditions")
        
    except Exception as e:
        results.record_fail("Multi-condition signals", str(e))


async def test_realtime_processor():
    """Test 6: RealtimeSignalProcessor integration."""
    print("\n[Test Suite 5] RealtimeSignalProcessor Integration")
    print("-" * 70)
    
    try:
        # Create processor
        trade_executed = []
        
        async def test_executor(event: SignalTriggerEvent):
            trade_executed.append(event)
        
        processor = RealtimeSignalProcessor(trade_executor=test_executor)
        
        if processor.technical_service is not None:
            results.record_pass("Processor has technical service")
        else:
            results.record_fail("Processor has technical service", "Service is None")
        
        if processor.signal_monitor is not None:
            results.record_pass("Processor has signal monitor")
        else:
            results.record_fail("Processor has signal monitor", "Monitor is None")
        
        # Warm up
        for i in range(50):
            candle = {
                "timestamp": get_system_time().isoformat(),
                "open": 45000,
                "high": 45020,
                "low": 44980,
                "close": 45000,
                "volume": 1500
            }
            processor.technical_service.update_candle("PROC_TEST", candle)
        
        # Add signal
        condition = TradingCondition(
            condition_id="processor_test_001",
            instrument="PROC_TEST",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY"
        )
        processor.signal_monitor.add_signal(condition)
        
        # Process ticks through processor
        for i in range(20):
            tick = {
                "last_price": 45000 + (i * 20),
                "volume": 1800,
                "timestamp": get_system_time().isoformat()
            }
            result = await processor.on_tick("PROC_TEST", tick)
            
            if result["signals_triggered"] > 0:
                break
        
        # Verify trade executor was called
        if len(trade_executed) > 0:
            results.record_pass("Trade executor callback invoked")
        else:
            results.record_fail("Trade executor callback invoked", "Executor never called")
        
        # Check statistics
        stats = processor.get_statistics()
        if stats["ticks_processed"] > 0:
            results.record_pass("Statistics tracking")
        else:
            results.record_fail("Statistics tracking", "No ticks tracked")
        
    except Exception as e:
        results.record_fail("RealtimeSignalProcessor", str(e))


async def test_end_to_end_flow():
    """Test 7: Complete end-to-end flow."""
    print("\n[Test Suite 6] End-to-End Flow")
    print("-" * 70)
    
    try:
        # Track execution
        executions = []
        
        async def track_execution(event: SignalTriggerEvent):
            executions.append({
                "condition_id": event.condition_id,
                "action": event.action,
                "price": event.current_price,
                "indicator": event.indicator_name,
                "value": event.indicator_value
            })
        
        # Create integrated system
        processor = create_realtime_processor(trade_executor=track_execution)
        
        # Step 1: Warm up system
        for i in range(50):
            candle = {
                "timestamp": get_system_time().isoformat(),
                "open": 45000,
                "high": 45020,
                "low": 44980,
                "close": 45000,
                "volume": 1500
            }
            await processor.on_candle("E2E_TEST", candle)
        
        results.record_pass("System warm-up")
        
        # Step 2: Agent creates conditional signal
        condition = TradingCondition(
            condition_id="e2e_rsi_oversold",
            instrument="E2E_TEST",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=35.0,
            action="BUY",
            position_size=1.0,
            stop_loss=44800,
            take_profit=45300
        )
        processor.signal_monitor.add_signal(condition)
        results.record_pass("Agent creates conditional signal")
        
        # Step 3: Market ticks flow through system
        ticks_before_trigger = 0
        for i in range(30):
            tick = {
                "last_price": 45000 + (i * 15),
                "volume": 1800,
                "timestamp": get_system_time().isoformat()
            }
            result = await processor.on_tick("E2E_TEST", tick)
            ticks_before_trigger += 1
            
            if result["signals_triggered"] > 0:
                break
        
        results.record_pass(f"Market ticks processed ({ticks_before_trigger} ticks)")
        
        # Step 4: Verify trade execution
        if len(executions) > 0:
            results.record_pass("Trade auto-executed when condition met")
            
            execution = executions[0]
            if execution["action"] == "BUY":
                results.record_pass("Correct trade action (BUY)")
            else:
                results.record_fail("Correct trade action (BUY)", f"Got {execution['action']}")
            
            if execution["condition_id"] == "e2e_rsi_oversold":
                results.record_pass("Correct condition triggered")
            else:
                results.record_fail("Correct condition triggered", f"Wrong ID: {execution['condition_id']}")
        else:
            results.record_fail("Trade auto-executed when condition met", "No executions recorded")
        
        # Step 5: Verify signal cleanup
        active = processor.signal_monitor.get_active_signals("E2E_TEST")
        if len(active) == 0:
            results.record_pass("Signal auto-removed after execution")
        else:
            results.record_fail("Signal auto-removed after execution", f"{len(active)} signals still active")
        
    except Exception as e:
        results.record_fail("End-to-end flow", str(e))


async def test_enhanced_technical_agent():
    """Test 8: EnhancedTechnicalAgent integration."""
    print("\n[Test Suite 7] EnhancedTechnicalAgent Integration")
    print("-" * 70)
    
    try:
        tech_service = get_technical_service()
        agent = EnhancedTechnicalAgent()
        
        # Warm up
        for i in range(50):
            candle = {
                "timestamp": get_system_time().isoformat(),
                "open": 45000,
                "high": 45020,
                "low": 44980,
                "close": 45000,
                "volume": 1500
            }
            tech_service.update_candle("AGENT_TEST", candle)
        
        # Agent analyzes with instrument
        context = {"instrument": "AGENT_TEST"}
        result = await agent.analyze(context)
        
        if result.decision in ["BUY", "SELL", "HOLD"]:
            results.record_pass("Agent provides valid decision")
        else:
            results.record_fail("Agent provides valid decision", f"Invalid: {result.decision}")
        
        if "perspectives" in result.details:
            results.record_pass("Agent provides perspectives")
            
            perspectives = result.details["perspectives"]
            expected = ["momentum", "trend", "volume", "mean_reversion"]
            
            all_present = all(p in perspectives for p in expected)
            if all_present:
                results.record_pass("All 4 perspectives present")
            else:
                missing = [p for p in expected if p not in perspectives]
                results.record_fail("All 4 perspectives present", f"Missing: {missing}")
        else:
            results.record_fail("Agent provides perspectives", "No perspectives in details")
        
        if "weighted_scores" in result.details:
            results.record_pass("Agent provides weighted scores")
        else:
            results.record_fail("Agent provides weighted scores", "No scores in details")
        
    except Exception as e:
        results.record_fail("EnhancedTechnicalAgent", str(e))


async def test_signal_expiry():
    """Test 9: Signal auto-expiry."""
    print("\n[Test Suite 8] Signal Auto-Expiry")
    print("-" * 70)
    
    try:
        monitor = SignalMonitor()
        
        # Create signal that expires in 1 second
        expiry_time = (get_system_time() + timedelta(seconds=1)).isoformat()
        condition = TradingCondition(
            condition_id="test_expiry_001",
            instrument="EXPIRY_TEST",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY",
            expires_at=expiry_time
        )
        
        monitor.add_signal(condition)
        
        # Check it's active
        active_before = monitor.get_active_signals("EXPIRY_TEST")
        if len(active_before) == 1:
            results.record_pass("Signal added with expiry")
        else:
            results.record_fail("Signal added with expiry", "Not added")
        
        # Wait for expiry
        await asyncio.sleep(1.5)
        
        # Check signals (should trigger expiry cleanup)
        tech_service = get_technical_service()
        monitor._technical_service = tech_service
        await monitor.check_signals("EXPIRY_TEST")
        
        # Verify removed
        active_after = monitor.get_active_signals("EXPIRY_TEST")
        if len(active_after) == 0:
            results.record_pass("Expired signal auto-removed")
        else:
            results.record_fail("Expired signal auto-removed", f"Still has {len(active_after)} active")
        
    except Exception as e:
        results.record_fail("Signal expiry", str(e))


async def run_all_tests():
    """Run complete test suite."""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE TEST SUITE: Real-time Signal-to-Trade System")
    print("=" * 70)
    
    # Synchronous tests
    test_technical_service_singleton()
    test_technical_service_indicators()
    test_signal_monitor_basic()
    
    # Async tests
    await test_signal_monitor_triggering()
    await test_multi_condition()
    await test_realtime_processor()
    await test_end_to_end_flow()
    await test_enhanced_technical_agent()
    await test_signal_expiry()
    
    # Summary
    success = results.summary()
    
    if success:
        print("\n[SUCCESS] All tests passed! System is production-ready.")
        return 0
    else:
        print("\n[WARNING] Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)

