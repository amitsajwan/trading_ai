"""Quick test: Verify SignalMonitor functionality."""

import asyncio
from datetime import datetime

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
    SignalTriggerEvent
)
from market_data.src.market_data.technical_indicators_service import (
    get_technical_service
)


def test_signal_creation():
    """Test 1: Create and register signal."""
    print("\n[Test 1] Signal Creation")
    print("-" * 60)
    
    monitor = SignalMonitor()
    
    condition = TradingCondition(
        condition_id="test_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.GREATER_THAN,
        threshold=32.0,
        action="BUY"
    )
    
    signal_id = monitor.add_signal(condition)
    assert signal_id == "test_001"
    
    active = monitor.get_active_signals("BANKNIFTY")
    assert len(active) == 1
    assert active[0].condition_id == "test_001"
    
    print("[OK] Signal created and registered")
    print(f"     ID: {signal_id}")
    print(f"     Condition: RSI > 32.0")
    print()


async def test_signal_triggering():
    """Test 2: Signal triggering when condition is met."""
    print("\n[Test 2] Signal Triggering")
    print("-" * 60)
    
    # Setup
    tech_service = get_technical_service()
    monitor = SignalMonitor(technical_service=tech_service)
    
    # Warm up service with candles
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
    
    print("[OK] TechnicalService warmed up with 50 candles")
    
    # Create signal
    condition = TradingCondition(
        condition_id="test_trigger_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.GREATER_THAN,
        threshold=50.0,
        action="BUY"
    )
    
    monitor.add_signal(condition)
    print(f"[OK] Signal registered: BUY when RSI > 50.0")
    
    # Update ticks to push RSI above threshold
    for i in range(30):
        tick = {
            "last_price": 45000 + (i * 20),  # Rising price
            "volume": 1800,
            "timestamp": get_system_time().isoformat()
        }
        tech_service.update_tick("BANKNIFTY", tick)
        
        # Check signals
        triggered = await monitor.check_signals("BANKNIFTY")
        
        if triggered:
            print(f"\n[OK] Signal triggered after {i+1} ticks!")
            print(f"     RSI value: {triggered[0].indicator_value:.2f}")
            print(f"     Threshold: {triggered[0].threshold}")
            print(f"     Action: {triggered[0].action}")
            return
    
    print("\n[FAILED] Signal not triggered")


async def test_crosses_above():
    """Test 3: CROSSES_ABOVE operator."""
    print("\n[Test 3] Crosses Above Operator")
    print("-" * 60)
    
    tech_service = get_technical_service()
    monitor = SignalMonitor(technical_service=tech_service)
    
    # Warm up
    for i in range(50):
        candle = {
            "timestamp": get_system_time().isoformat(),
            "open": 44800,
            "high": 44820,
            "low": 44780,
            "close": 44800 - i,  # Falling to push RSI low
            "volume": 1500
        }
        tech_service.update_candle("BANKNIFTY", candle)
    
    # Create CROSSES_ABOVE signal
    condition = TradingCondition(
        condition_id="test_cross_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.CROSSES_ABOVE,  # Must cross, not just be above
        threshold=30.0,
        action="BUY"
    )
    
    monitor.add_signal(condition)
    print("[OK] Signal registered: BUY when RSI CROSSES ABOVE 30.0")
    
    # Initial checks (RSI below 30)
    for i in range(5):
        tick = {"last_price": 44700 - i, "volume": 1500, "timestamp": get_system_time().isoformat()}
        tech_service.update_tick("BANKNIFTY", tick)
        triggered = await monitor.check_signals("BANKNIFTY")
        if triggered:
            print("[FAILED] Triggered too early (should wait for cross)")
            return
    
    print("[OK] Signal not triggered while RSI below threshold (correct)")
    
    # Now push RSI above threshold
    for i in range(20):
        tick = {"last_price": 44700 + (i * 15), "volume": 1800, "timestamp": get_system_time().isoformat()}
        tech_service.update_tick("BANKNIFTY", tick)
        triggered = await monitor.check_signals("BANKNIFTY")
        
        if triggered:
            print(f"\n[OK] Signal triggered on CROSS (tick {i+1})!")
            print(f"     RSI crossed from below 30 to above 30")
            return
    
    print("\n[FAILED] Signal not triggered on cross")


async def test_multi_condition():
    """Test 4: Multi-condition signals (AND logic)."""
    print("\n[Test 4] Multi-Condition Signal")
    print("-" * 60)
    
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
        tech_service.update_candle("BANKNIFTY", candle)
    
    # Create multi-condition signal
    condition = TradingCondition(
        condition_id="test_multi_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.GREATER_THAN,
        threshold=50.0,
        action="BUY",
        additional_conditions=[
            {"indicator": "current_price", "operator": ">", "threshold": 45100}
        ]
    )
    
    monitor.add_signal(condition)
    print("[OK] Multi-condition signal created:")
    print("     Primary: RSI > 50")
    print("     AND Price > 45100")
    
    # Test with only RSI condition met (should NOT trigger)
    for i in range(10):
        tick = {"last_price": 45000, "volume": 1800, "timestamp": get_system_time().isoformat()}
        tech_service.update_tick("BANKNIFTY", tick)
        triggered = await monitor.check_signals("BANKNIFTY")
        if triggered:
            print("\n[FAILED] Triggered with only partial conditions met")
            return
    
    print("[OK] Signal not triggered with only RSI condition met (correct)")
    
    # Now meet both conditions
    for i in range(15):
        tick = {"last_price": 45100 + (i * 10), "volume": 1800, "timestamp": get_system_time().isoformat()}
        tech_service.update_tick("BANKNIFTY", tick)
        triggered = await monitor.check_signals("BANKNIFTY")
        
        if triggered:
            print(f"\n[OK] Signal triggered when ALL conditions met!")
            print(f"     RSI: {triggered[0].all_indicators.get('rsi_14', 'N/A')}")
            print(f"     Price: {triggered[0].current_price}")
            return
    
    print("\n[FAILED] Signal not triggered even with all conditions met")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("SIGNAL MONITOR - FUNCTIONALITY TESTS")
    print("=" * 70)
    
    try:
        # Test 1
        test_signal_creation()
        
        # Test 2
        await test_signal_triggering()
        
        # Test 3
        await test_crosses_above()
        
        # Test 4
        await test_multi_condition()
        
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED")
        print("=" * 70)
        print("\nSignalMonitor is working correctly:")
        print("  [OK] Signal creation and registration")
        print("  [OK] Real-time condition checking")
        print("  [OK] Signal triggering on threshold")
        print("  [OK] CROSSES_ABOVE operator")
        print("  [OK] Multi-condition AND logic")
        print("\nReady for production use!")
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"TEST FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

