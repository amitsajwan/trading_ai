"""Example: Real-time Technical Indicators Integration.

This demonstrates the proper architecture:
1. TechnicalIndicatorsService calculates indicators on EVERY market tick
2. Indicators stored in memory for instant access
3. EnhancedTechnicalAgent consumes pre-calculated indicators via API
4. Multiple agents can share the same indicator calculations (zero redundancy)

Architecture Flow:
    Market Data Feed → update_tick() → TechnicalIndicatorsService
                                             ↓
                                      Store indicators
                                             ↓
    Agent Analysis → get_indicators() → EnhancedTechnicalAgent → Trading Decision
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

# Service layer - Real-time indicator calculation
from market_data.technical_indicators_service import (
    get_technical_service,
    TechnicalIndicatorsService
)

# Agent layer - Indicator interpretation  
from engine_module.agents.enhanced_technical_agent import EnhancedTechnicalAgent
from engine_module.contracts import AnalysisResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketDataSimulator:
    """Simulates real-time market data feed."""
    
    def __init__(self, instrument: str = "BANKNIFTY"):
        self.instrument = instrument
        self.current_price = 45000.0
        self.tick_count = 0
        
    def generate_tick(self) -> Dict[str, Any]:
        """Generate next market tick."""
        # Simulate price movement
        import random
        price_change = random.uniform(-50, 50)
        self.current_price += price_change
        
        self.tick_count += 1
        
        return {
            "instrument": self.instrument,
            "last_price": self.current_price,
            "volume": random.randint(500, 2000),
            "timestamp": datetime.now().isoformat()
        }


async def run_realtime_demo():
    """Demonstrate real-time indicator calculation + agent consumption."""
    
    logger.info("=== Real-time Technical Indicators Demo ===\n")
    
    # Initialize components
    tech_service = get_technical_service()
    enhanced_agent = EnhancedTechnicalAgent()
    market_simulator = MarketDataSimulator("BANKNIFTY")
    
    logger.info("Step 1: Generate initial market candles (warm-up period)")
    logger.info("-" * 60)
    
    # Warm-up: Generate 50 candles to build indicator history
    for i in range(50):
        candle = {
            "timestamp": datetime.now().isoformat(),
            "open": market_simulator.current_price,
            "high": market_simulator.current_price + 20,
            "low": market_simulator.current_price - 20,
            "close": market_simulator.current_price,
            "volume": 1500
        }
        tech_service.update_candle("BANKNIFTY", candle)
        market_simulator.generate_tick()  # Move price
    
    logger.info(f"✓ Initialized with 50 candles\n")
    
    logger.info("Step 2: Real-time tick processing")
    logger.info("-" * 60)
    
    # Simulate 10 real-time ticks
    for tick_num in range(1, 11):
        # === SERVICE LAYER: Calculate indicators on every tick ===
        tick = market_simulator.generate_tick()
        indicators = tech_service.update_tick("BANKNIFTY", tick)
        
        logger.info(f"\nTick #{tick_num}: Price={tick['last_price']:.2f}")
        logger.info(f"  Indicators calculated:")
        logger.info(f"    • RSI: {indicators.rsi_14:.1f}" if indicators.rsi_14 else "    • RSI: N/A")
        logger.info(f"    • SMA20: {indicators.sma_20:.1f}" if indicators.sma_20 else "    • SMA20: N/A")
        logger.info(f"    • Trend: {indicators.trend_direction} (strength: {indicators.trend_strength:.0f})")
        logger.info(f"    • Volume Ratio: {indicators.volume_ratio:.2f}x" if indicators.volume_ratio else "    • Volume Ratio: N/A")
        
        # === AGENT LAYER: Every 5 ticks, run agent analysis ===
        if tick_num % 5 == 0:
            logger.info(f"\n  → Running EnhancedTechnicalAgent analysis...")
            
            # Agent fetches pre-calculated indicators (NO calculation inside agent!)
            context = {
                "instrument": "BANKNIFTY",
                "indicators": indicators  # Pass pre-calculated indicators
            }
            
            analysis: AnalysisResult = await enhanced_agent.analyze(context)
            
            logger.info(f"  ✓ Agent Decision: {analysis.decision} (confidence: {analysis.confidence:.0%})")
            logger.info(f"  ✓ Weighted Scores:")
            logger.info(f"      BUY:  {analysis.details['weighted_scores']['buy']:.2f}")
            logger.info(f"      SELL: {analysis.details['weighted_scores']['sell']:.2f}")
            logger.info(f"      HOLD: {analysis.details['weighted_scores']['hold']:.2f}")
            
            # Show perspective breakdown
            logger.info(f"  ✓ Perspectives:")
            for perspective, details in analysis.details['perspectives'].items():
                logger.info(f"      {perspective.upper()}: {details['signal']} ({details['confidence']:.0%})")
        
        await asyncio.sleep(0.1)  # Simulate time between ticks
    
    logger.info("\n" + "=" * 60)
    logger.info("Demo complete!")
    logger.info("=" * 60)
    logger.info("\nKey Takeaways:")
    logger.info("1. ✅ Indicators calculated ONCE per tick by service")
    logger.info("2. ✅ EnhancedTechnicalAgent consumes via API (no redundant calculations)")
    logger.info("3. ✅ Multiple agents can share same indicator data")
    logger.info("4. ✅ Service stores indicators in memory for instant access")
    logger.info("5. ✅ Clear separation: Service=calculation, Agent=interpretation\n")


async def compare_architectures():
    """Compare old vs new architecture."""
    
    print("\n" + "=" * 70)
    print("ARCHITECTURE COMPARISON: Old vs New")
    print("=" * 70)
    
    print("\n❌ OLD ARCHITECTURE (Redundant):")
    print("-" * 70)
    print("  Market Tick → Store Raw OHLC")
    print("                     ↓")
    print("  MomentumAgent   → Calculate RSI, MACD, Volume")
    print("  TrendAgent      → Calculate SMA, EMA, ADX")  
    print("  VolumeAgent     → Calculate Volume Ratios, RSI")
    print("  MeanRevAgent    → Calculate Bollinger, RSI")
    print("                     ↓")
    print("  Problem: RSI calculated 3x, SMA 3x per analysis cycle!")
    print("  Cost: 3-4x redundant calculations, wasted tokens/compute")
    
    print("\n✅ NEW ARCHITECTURE (Optimized):")
    print("-" * 70)
    print("  Market Tick → TechnicalIndicatorsService.update_tick()")
    print("                     ↓")
    print("              Calculate ALL indicators ONCE")
    print("              Store in memory/Redis")
    print("                     ↓")
    print("  EnhancedTechnicalAgent.analyze()")
    print("    ├─ Momentum perspective   (reads RSI, MACD from service)")
    print("    ├─ Trend perspective      (reads SMA, EMA, ADX from service)")
    print("    ├─ Volume perspective     (reads volume ratio from service)")
    print("    └─ MeanReversion perspective (reads Bollinger from service)")
    print("                     ↓")
    print("              Aggregate perspectives → Final Decision")
    
    print("\n  Benefits:")
    print("  ✓ Each indicator calculated exactly ONCE per tick")
    print("  ✓ All 4 agents replaced by 1 multi-perspective agent")
    print("  ✓ Service can be shared across multiple systems")
    print("  ✓ Real-time updates on every market tick")
    print("  ✓ Zero redundancy, optimal performance")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Show architecture comparison
    asyncio.run(compare_architectures())
    
    # Run real-time demo
    asyncio.run(run_realtime_demo())

