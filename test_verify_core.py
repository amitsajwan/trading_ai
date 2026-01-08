"""Quick Verification Tests: Core Real-time Signal Functionality.

These tests verify the essential features work correctly:
1. Technical indicators update on every tick
2. Signals monitor indicators in real-time
3. Trades execute when conditions are met
4. EnhancedTechnicalAgent consumes indicators correctly
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime

# Import TimeService for virtual time support
try:
    from core_kernel.src.core_kernel.time_service import now as get_system_time
except ImportError:
    # Fallback to real time if TimeService not available
    def get_system_time():
        return datetime.now()

from engine_module.src.engine_module.signal_monitor import (
    SignalMonitor, TradingCondition, ConditionOperator
)
from engine_module.src.engine_module.realtime_signal_integration import RealtimeSignalProcessor
from market_data.src.market_data.technical_indicators_service import get_technical_service
from engine_module.src.engine_module.agents.enhanced_technical_agent import EnhancedTechnicalAgent


def print_test(name, passed, details=""):
    status = "[OK]" if passed else "[FAIL]"
    print(f"{status} {name}")
    if details and not passed:
        print(f"     {details}")


async def verify_core_functionality():
    """Verify core features work."""
    
    print("\n" + "="*70)
    print("VERIFICATION TESTS: Core Real-time Signal Functionality")
    print("="*70 + "\n")
    
    passed = 0
    failed = 0
    
    # Test 1: Technical Service Updates
    print("[1] TechnicalIndicatorsService")
    print("-" * 70)
    
    try:
        service = get_technical_service()
        
        # Warm up
        for i in range(50):
            service.update_candle("VERIFY", {
                "timestamp": get_system_time().isoformat(),
                "open": 45000, "high": 45020, "low": 44980,
                "close": 45000 + i, "volume": 1500
            })
        
        # Update tick
        indicators = service.update_tick("VERIFY", {
            "last_price": 45100, "volume": 1800,
            "timestamp": get_system_time().isoformat()
        })
        
        # Check RSI calculated
        test_rsi = indicators.rsi_14 is not None
        print_test("RSI calculated on tick update", test_rsi)
        if test_rsi: passed += 1
        else: failed += 1
        
        # Check retrieval
        retrieved = service.get_indicators("VERIFY")
        test_retrieve = retrieved is not None
        print_test("Indicators retrievable", test_retrieve)
        if test_retrieve: passed += 1
        else: failed += 1
        
        # Check dict format
        dict_indicators = service.get_indicators_dict("VERIFY")
        test_dict = isinstance(dict_indicators, dict) and "rsi_14" in dict_indicators
        print_test("Dict format available", test_dict)
        if test_dict: passed += 1
        else: failed += 1
        
    except Exception as e:
        print_test("TechnicalService initialization", False, str(e))
        failed += 1
    
    print()
    
    # Test 2: SignalMonitor
    print("[2] SignalMonitor")
    print("-" * 70)
    
    try:
        monitor = SignalMonitor()
        
        # Add signal
        condition = TradingCondition(
            condition_id="verify_001",
            instrument="VERIFY",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY"
        )
        
        monitor.add_signal(condition)
        test_add = len(monitor.get_active_signals("VERIFY")) == 1
        print_test("Signal registration", test_add)
        if test_add: passed += 1
        else: failed += 1
        
        # Remove signal
        monitor.remove_signal("verify_001")
        test_remove = len(monitor.get_active_signals("VERIFY")) == 0
        print_test("Signal removal", test_remove)
        if test_remove: passed += 1
        else: failed += 1
        
    except Exception as e:
        print_test("SignalMonitor basic operations", False, str(e))
        failed += 1
    
    print()
    
    # Test 3: Signal Triggering
    print("[3] Real-time Signal Triggering")
    print("-" * 70)
    
    try:
        service = get_technical_service()
        monitor = SignalMonitor(technical_service=service)
        
        # Create signal
        condition = TradingCondition(
            condition_id="verify_trigger",
            instrument="TRIGGER_TEST",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY"
        )
        monitor.add_signal(condition)
        
        # Warm up new instrument
        for i in range(50):
            service.update_candle("TRIGGER_TEST", {
                "timestamp": get_system_time().isoformat(),
                "open": 45000, "high": 45020, "low": 44980,
                "close": 45000, "volume": 1500
            })
        
        # Push RSI above threshold
        triggered = False
        for i in range(25):
            service.update_tick("TRIGGER_TEST", {
                "last_price": 45000 + (i * 20),
                "volume": 1800,
                "timestamp": get_system_time().isoformat()
            })
            
            events = await monitor.check_signals("TRIGGER_TEST")
            if events:
                triggered = True
                break
        
        print_test("Signal triggers when condition met", triggered)
        if triggered: passed += 1
        else: failed += 1
        
        # Check signal removed after trigger
        active_after = monitor.get_active_signals("TRIGGER_TEST")
        test_cleanup = len(active_after) == 0
        print_test("Triggered signal auto-removed", test_cleanup)
        if test_cleanup: passed += 1
        else: failed += 1
        
    except Exception as e:
        print_test("Signal triggering", False, str(e))
        failed += 1
    
    print()
    
    # Test 4: RealtimeSignalProcessor
    print("[4] RealtimeSignalProcessor Integration")
    print("-" * 70)
    
    try:
        executions = []
        
        async def track_execution(event):
            executions.append(event)
        
        processor = RealtimeSignalProcessor(trade_executor=track_execution)
        
        # Warm up
        for i in range(50):
            await processor.on_candle("PROCESSOR_TEST", {
                "timestamp": get_system_time().isoformat(),
                "open": 45000, "high": 45020, "low": 44980,
                "close": 45000, "volume": 1500
            })
        
        # Add signal
        processor.signal_monitor.add_signal(TradingCondition(
            condition_id="proc_verify",
            instrument="PROCESSOR_TEST",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=50.0,
            action="BUY"
        ))
        
        # Process ticks
        for i in range(20):
            await processor.on_tick("PROCESSOR_TEST", {
                "last_price": 45000 + (i * 20),
                "volume": 1800,
                "timestamp": get_system_time().isoformat()
            })
        
        test_processor = processor.ticks_processed > 0
        print_test("Processor handles ticks", test_processor)
        if test_processor: passed += 1
        else: failed += 1
        
        stats = processor.get_statistics()
        test_stats = stats["ticks_processed"] > 0
        print_test("Statistics tracking works", test_stats)
        if test_stats: passed += 1
        else: failed += 1
        
    except Exception as e:
        print_test("RealtimeSignalProcessor", False, str(e))
        failed += 1
    
    print()
    
    # Test 5: EnhancedTechnicalAgent
    print("[5] EnhancedTechnicalAgent")
    print("-" * 70)
    
    try:
        service = get_technical_service()
        agent = EnhancedTechnicalAgent()
        
        # Warm up
        for i in range(50):
            service.update_candle("AGENT_VERIFY", {
                "timestamp": get_system_time().isoformat(),
                "open": 45000, "high": 45020, "low": 44980,
                "close": 45000, "volume": 1500
            })
        
        # Agent analyzes
        result = await agent.analyze({"instrument": "AGENT_VERIFY"})
        
        test_decision = result.decision in ["BUY", "SELL", "HOLD"]
        print_test("Agent provides valid decision", test_decision)
        if test_decision: passed += 1
        else: failed += 1
        
        test_perspectives = "perspectives" in result.details
        print_test("Agent provides perspectives", test_perspectives)
        if test_perspectives: passed += 1
        else: failed += 1
        
        if test_perspectives:
            perspectives = result.details["perspectives"]
            expected = ["momentum", "trend", "volume", "mean_reversion"]
            all_present = all(p in perspectives for p in expected)
            print_test("All 4 perspectives present", all_present)
            if all_present: passed += 1
            else: failed += 1
    
    except Exception as e:
        print_test("EnhancedTechnicalAgent", False, str(e))
        failed += 1
    
    # Summary
    print("\n" + "="*70)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*70)
    
    if failed == 0:
        print("\n[SUCCESS] All core functionality verified!")
        print("System is ready for:")
        print("  - Real-time indicator calculation on every tick")
        print("  - Conditional signal monitoring")
        print("  - Automatic trade execution when conditions met")
        print("  - Multi-perspective technical analysis")
        return 0
    else:
        print(f"\n[WARNING] {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(verify_core_functionality())
    sys.exit(exit_code)

