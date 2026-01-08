"""Demo: Real-time Signal-to-Trade Conversion.

This demonstrates the complete flow:
1. Agent generates conditional signal: "BUY when RSI > 32"
2. SignalMonitor stores the condition
3. Market ticks update indicators in real-time
4. When RSI crosses 32, trade executes automatically
5. NO waiting for next 15-min analysis cycle!
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Signal monitoring system
from engine_module.src.engine_module.signal_monitor import (
    SignalMonitor,
    TradingCondition,
    ConditionOperator,
    get_signal_monitor
)

# Real-time integration
from engine_module.src.engine_module.realtime_signal_integration import (
    RealtimeSignalProcessor,
    create_realtime_processor
)

# Technical indicators service
from market_data.src.market_data.technical_indicators_service import (
    get_technical_service
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketDataSimulator:
    """Simulates real-time market data with controlled RSI movement."""
    
    def __init__(self, instrument: str = "BANKNIFTY"):
        self.instrument = instrument
        self.current_price = 45000.0
        self.tick_count = 0
        
    def generate_tick_sequence(self, rsi_target: float = 35) -> list:
        """Generate tick sequence that will push RSI to target value.
        
        Args:
            rsi_target: Target RSI value to reach
            
        Returns:
            List of tick dictionaries
        """
        ticks = []
        
        # Start with downward movement (RSI < 30)
        for i in range(20):
            self.current_price -= 10
            ticks.append({
                "instrument": self.instrument,
                "last_price": self.current_price,
                "volume": 1500,
                "timestamp": datetime.now().isoformat()
            })
        
        # Then upward movement to cross threshold
        for i in range(25):
            self.current_price += 15
            ticks.append({
                "instrument": self.instrument,
                "last_price": self.current_price,
                "volume": 1800,
                "timestamp": datetime.now().isoformat()
            })
        
        return ticks


async def demo_signal_to_trade_flow():
    """Complete demonstration of signal-to-trade conversion."""
    
    print("\n" + "=" * 80)
    print("DEMO: Real-time Signal-to-Trade Conversion")
    print("=" * 80)
    
    # === SETUP PHASE ===
    print("\n📋 SETUP PHASE")
    print("-" * 80)
    
    # Initialize components
    tech_service = get_technical_service()
    signal_monitor = get_signal_monitor()
    processor = create_realtime_processor()
    
    print("✓ TechnicalIndicatorsService initialized")
    print("✓ SignalMonitor initialized")
    print("✓ RealtimeSignalProcessor initialized")
    
    # Warm up with initial candles (needed for indicator calculation)
    print("\n🔥 Warming up with 50 candles...")
    simulator = MarketDataSimulator("BANKNIFTY")
    for i in range(50):
        candle = {
            "timestamp": datetime.now().isoformat(),
            "open": simulator.current_price,
            "high": simulator.current_price + 20,
            "low": simulator.current_price - 20,
            "close": simulator.current_price,
            "volume": 1500
        }
        tech_service.update_candle("BANKNIFTY", candle)
        simulator.current_price += 5  # Gradual movement
    
    print("✓ Warm-up complete\n")
    
    # === AGENT ANALYSIS PHASE (15-min cycle) ===
    print("\n🤖 AGENT ANALYSIS PHASE (Simulating 15-min cycle)")
    print("-" * 80)
    
    # Agent analyzes market and creates conditional signal
    # "Market is oversold, but not extreme. BUY when RSI recovers above 32"
    
    current_indicators = tech_service.get_indicators("BANKNIFTY")
    print(f"Current Market State:")
    print(f"  Price: {current_indicators.current_price:.2f}")
    print(f"  RSI: {current_indicators.rsi_14:.1f}" if current_indicators.rsi_14 else "  RSI: Calculating...")
    print(f"  Trend: {current_indicators.trend_direction}")
    
    print("\n🎯 Agent Decision: CREATE CONDITIONAL SIGNAL")
    print("   'BUY when RSI crosses above 32 (oversold recovery)'")
    
    # Create conditional signal
    condition = TradingCondition(
        condition_id="rsi_oversold_recovery_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.CROSSES_ABOVE,  # Crosses from below to above
        threshold=32.0,
        action="BUY",
        position_size=1.0,
        confidence=0.75,
        stop_loss=44800,
        take_profit=45400,
        strategy_type="SPOT"
    )
    
    # Register with monitor
    signal_monitor.add_signal(condition)
    
    print(f"\n✓ Signal registered with ID: {condition.condition_id}")
    print(f"  Waiting for: RSI to cross above {condition.threshold}")
    print(f"  Action: {condition.action}")
    print(f"  Stop Loss: {condition.stop_loss}")
    print(f"  Take Profit: {condition.take_profit}")
    
    # === REAL-TIME MONITORING PHASE ===
    print("\n\n📊 REAL-TIME MONITORING PHASE")
    print("-" * 80)
    print("Market ticks streaming... monitoring RSI on every tick...\n")
    
    # Generate tick sequence that will trigger the signal
    ticks = simulator.generate_tick_sequence(rsi_target=35)
    
    signal_triggered = False
    
    for i, tick in enumerate(ticks):
        # Process tick through real-time system
        result = await processor.on_tick("BANKNIFTY", tick)
        
        # Get current indicators
        indicators = tech_service.get_indicators("BANKNIFTY")
        
        # Display progress every 5 ticks
        if i % 5 == 0:
            rsi_str = f"{indicators.rsi_14:.1f}" if indicators.rsi_14 else "N/A"
            print(
                f"Tick #{i+1:3d}: Price={tick['last_price']:7.2f} | "
                f"RSI={rsi_str:6s} | "
                f"Active Signals: {result['signals_checked']} | "
                f"Triggered: {result['signals_triggered']}"
            )
        
        # Check if signal was triggered
        if result['signals_triggered'] > 0:
            signal_triggered = True
            print("\n" + "🎉" * 40)
            print("SIGNAL TRIGGERED! Trade executed automatically!")
            print("🎉" * 40)
            
            for event in result['triggered_events']:
                print(f"\n📈 Trade Details:")
                print(f"   Condition ID: {event.condition_id}")
                print(f"   Instrument: {event.instrument}")
                print(f"   Action: {event.action}")
                print(f"   Price: {event.current_price:.2f}")
                print(f"   RSI at trigger: {event.indicator_value:.2f}")
                print(f"   Threshold: {event.threshold}")
                print(f"   Stop Loss: {event.stop_loss}")
                print(f"   Take Profit: {event.take_profit}")
            
            break
        
        # Small delay to simulate real-time streaming
        await asyncio.sleep(0.02)
    
    # === SUMMARY PHASE ===
    print("\n\n📊 SUMMARY")
    print("=" * 80)
    
    stats = processor.get_statistics()
    print(f"Ticks Processed: {stats['ticks_processed']}")
    print(f"Signals Triggered: {stats['signals_triggered']}")
    print(f"Active Signals Remaining: {stats['active_signals']}")
    
    if signal_triggered:
        print("\n✅ SUCCESS: Signal converted to trade in real-time!")
        print("   Agent didn't wait for next 15-min cycle")
        print("   Trade executed as soon as RSI condition was met")
    else:
        print("\n❌ Signal not triggered during simulation")
    
    # Show triggered signals history
    triggered = signal_monitor.get_triggered_signals()
    if triggered:
        print(f"\n📜 Triggered Signals History:")
        for event in triggered:
            print(f"   {event.triggered_at}: {event.action} {event.instrument} "
                  f"@ {event.current_price:.2f} (RSI={event.indicator_value:.2f})")
    
    print("\n" + "=" * 80)


async def demo_multi_condition_signal():
    """Demonstrate multi-condition signal (AND logic)."""
    
    print("\n" + "=" * 80)
    print("DEMO: Multi-Condition Signal")
    print("=" * 80)
    
    print("\nExample: BUY when RSI > 35 AND Price > SMA20 (both conditions must be true)")
    
    signal_monitor = get_signal_monitor()
    
    # Create signal with multiple conditions
    condition = TradingCondition(
        condition_id="multi_condition_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.GREATER_THAN,
        threshold=35.0,
        action="BUY",
        additional_conditions=[
            {
                "indicator": "current_price",
                "operator": ">",
                "threshold": 45000.0  # Price must be above SMA20
            },
            {
                "indicator": "volume_ratio",
                "operator": ">",
                "threshold": 1.2  # Volume above average
            }
        ]
    )
    
    signal_monitor.add_signal(condition)
    
    print(f"\n✓ Multi-condition signal created:")
    print(f"   Primary: RSI > 35")
    print(f"   AND Price > 45000")
    print(f"   AND Volume Ratio > 1.2x")
    print(f"\n   All conditions must be TRUE for trade to execute")
    
    print("\n" + "=" * 80)


async def demo_architecture_comparison():
    """Compare old vs new signal execution."""
    
    print("\n" + "=" * 80)
    print("ARCHITECTURE COMPARISON: Signal Execution")
    print("=" * 80)
    
    print("\n[OLD] APPROACH (Periodic Analysis Only):")
    print("-" * 80)
    print("09:15 - Agent analyzes: 'Market oversold, BUY signal'")
    print("09:16 - Trade executed immediately")
    print("09:30 - Next analysis cycle")
    print("09:45 - Next analysis cycle")
    print("...")
    print("\nProblem: If market was at RSI=29 at 09:15, but hit RSI=32 at 09:20,")
    print("         the system misses the recovery! Must wait until 09:30.")
    
    print("\n[NEW] APPROACH (Real-time Conditional Signals):")
    print("-" * 80)
    print("09:15 - Agent analyzes: 'Market oversold, CREATE SIGNAL: BUY when RSI > 32'")
    print("09:16 - Tick received, RSI=29 -> Signal monitor checks -> No action")
    print("09:17 - Tick received, RSI=30 -> Signal monitor checks -> No action")
    print("09:18 - Tick received, RSI=33 -> [CONDITION MET] -> EXECUTE TRADE")
    print("09:30 - Next agent analysis cycle (can create new signals)")
    print("\nBenefit: Trade executes IMMEDIATELY when condition is met,")
    print("         not waiting for next 15-min cycle!")
    
    print("\n" + "=" * 80)
    
    print("\n[KEY DIFFERENCES]:")
    print("-" * 80)
    print("| Aspect              | Old (Periodic)     | New (Real-time)        |")
    print("|---------------------|-------------------|------------------------|")
    print("| Analysis Frequency  | Every 15 minutes  | Every 15 minutes       |")
    print("| Signal Check        | At analysis only  | EVERY TICK (~100ms)    |")
    print("| Trade Execution     | Immediate         | When condition met     |")
    print("| Latency             | Up to 15 min      | ~100-200ms             |")
    print("| Missed Opportunities| High              | Minimal                |")
    print("-" * 80)


if __name__ == "__main__":
    # Run architecture comparison first
    asyncio.run(demo_architecture_comparison())
    
    # Run main demo
    asyncio.run(demo_signal_to_trade_flow())
    
    # Show multi-condition example
    asyncio.run(demo_multi_condition_signal())

