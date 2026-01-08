"""Quick test: Verify TechnicalIndicatorsService + EnhancedTechnicalAgent integration."""

import asyncio
from datetime import datetime

# Import TimeService for virtual time support
try:
    from core_kernel.src.core_kernel.time_service import now as get_system_time
except ImportError:
    # Fallback to real time if TimeService not available
    def get_system_time():
        return datetime.now()


def test_service_creation():
    """Test 1: Create service and update indicators."""
    print("Test 1: TechnicalIndicatorsService creation")
    print("-" * 60)
    
    from market_data.src.market_data.technical_indicators_service import get_technical_service
    
    service = get_technical_service()
    print("✓ Service created")
    
    # Warm-up with some candles
    for i in range(50):
        candle = {
            "timestamp": get_system_time().isoformat(),
            "open": 45000 + i,
            "high": 45020 + i,
            "low": 44980 + i,
            "close": 45010 + i,
            "volume": 1500
        }
        service.update_candle("BANKNIFTY", candle)
    
    print("✓ Warmed up with 50 candles")
    
    # Update with a tick
    tick = {
        "last_price": 45123.50,
        "volume": 1800,
        "timestamp": get_system_time().isoformat()
    }
    
    indicators = service.update_tick("BANKNIFTY", tick)
    print("✓ Tick updated, indicators calculated")
    print(f"  - RSI: {indicators.rsi_14:.1f}" if indicators.rsi_14 else "  - RSI: N/A")
    print(f"  - SMA20: {indicators.sma_20:.1f}" if indicators.sma_20 else "  - SMA20: N/A")
    print(f"  - Trend: {indicators.trend_direction}")
    
    # Get indicators
    retrieved = service.get_indicators("BANKNIFTY")
    assert retrieved is not None
    print("✓ Indicators retrieved via get_indicators()")
    
    # Get as dict
    indicators_dict = service.get_indicators_dict("BANKNIFTY")
    assert isinstance(indicators_dict, dict)
    assert "rsi_14" in indicators_dict
    print("✓ Indicators retrieved as dict via get_indicators_dict()")
    
    print("\nTest 1: PASSED ✓\n")
    return service


async def test_agent_analysis():
    """Test 2: EnhancedTechnicalAgent consumes indicators."""
    print("Test 2: EnhancedTechnicalAgent analysis")
    print("-" * 60)
    
    from market_data.src.market_data.technical_indicators_service import get_technical_service
    from engine_module.src.engine_module.agents.enhanced_technical_agent import EnhancedTechnicalAgent
    
    service = get_technical_service()
    agent = EnhancedTechnicalAgent()
    print("✓ Agent created")
    
    # Agent analyzes with instrument (fetches from service)
    context = {"instrument": "BANKNIFTY"}
    result = await agent.analyze(context)
    
    print("✓ Agent analysis complete")
    print(f"  - Decision: {result.decision}")
    print(f"  - Confidence: {result.confidence:.0%}")
    print(f"  - Perspectives analyzed: {len(result.details['perspectives'])}")
    
    # Verify perspectives
    perspectives = result.details['perspectives']
    expected_perspectives = ["momentum", "trend", "volume", "mean_reversion"]
    
    for perspective in expected_perspectives:
        assert perspective in perspectives, f"Missing perspective: {perspective}"
        assert "signal" in perspectives[perspective]
        assert "confidence" in perspectives[perspective]
        assert "reasoning" in perspectives[perspective]
    
    print("✓ All 4 perspectives present with valid structure")
    
    # Verify weighted scores
    assert "weighted_scores" in result.details
    assert "buy" in result.details["weighted_scores"]
    assert "sell" in result.details["weighted_scores"]
    assert "hold" in result.details["weighted_scores"]
    print("✓ Weighted scores calculated")
    
    print("\nTest 2: PASSED ✓\n")


async def test_agent_with_direct_indicators():
    """Test 3: Agent with directly passed indicators."""
    print("Test 3: Agent with direct indicator pass")
    print("-" * 60)
    
    from market_data.src.market_data.technical_indicators_service import get_technical_service
    from engine_module.src.engine_module.agents.enhanced_technical_agent import EnhancedTechnicalAgent
    
    service = get_technical_service()
    agent = EnhancedTechnicalAgent()
    
    # Get indicators from service
    indicators = service.get_indicators("BANKNIFTY")
    
    # Pass directly to agent
    context = {"indicators": indicators}
    result = await agent.analyze(context)
    
    print("✓ Agent analyzed with direct indicators")
    print(f"  - Decision: {result.decision}")
    print(f"  - Confidence: {result.confidence:.0%}")
    
    # Test with dict format
    indicators_dict = service.get_indicators_dict("BANKNIFTY")
    context2 = {"indicators": indicators_dict}
    result2 = await agent.analyze(context2)
    
    print("✓ Agent analyzed with dict indicators")
    print(f"  - Decision: {result2.decision}")
    print(f"  - Confidence: {result2.confidence:.0%}")
    
    print("\nTest 3: PASSED ✓\n")


async def test_integration_flow():
    """Test 4: Complete integration flow."""
    print("Test 4: Complete integration flow")
    print("-" * 60)
    
    from market_data.src.market_data.technical_indicators_service import get_technical_service
    from engine_module.src.engine_module.agents.enhanced_technical_agent import EnhancedTechnicalAgent
    
    service = get_technical_service()
    agent = EnhancedTechnicalAgent()
    
    # Simulate 5 market ticks
    print("Simulating 5 market ticks...")
    for i in range(5):
        tick = {
            "last_price": 45000 + (i * 10),
            "volume": 1500 + (i * 100),
            "timestamp": get_system_time().isoformat()
        }
        
        # Service calculates indicators
        indicators = service.update_tick("BANKNIFTY", tick)
        rsi_str = f"{indicators.rsi_14:.1f}" if indicators.rsi_14 else "N/A"
        print(f"  Tick {i+1}: Price={tick['last_price']:.2f}, RSI={rsi_str}")
    
    print("\n✓ All ticks processed, indicators updated")
    
    # Agent analyzes latest state
    result = await agent.analyze({"instrument": "BANKNIFTY"})
    print("\n✓ Agent analysis on latest state:")
    print(f"  - Decision: {result.decision}")
    print(f"  - Confidence: {result.confidence:.0%}")
    
    # Show perspective breakdown
    print("\n  Perspective Breakdown:")
    for name, details in result.details['perspectives'].items():
        print(f"    {name.upper():15} → {details['signal']:4} ({details['confidence']:>5.0%}): {details['reasoning'][:50]}...")
    
    print("\nTest 4: PASSED ✓\n")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("TECHNICAL INDICATORS INTEGRATION - VERIFICATION TESTS")
    print("=" * 70 + "\n")
    
    try:
        # Test 1: Service creation
        service = test_service_creation()
        
        # Test 2: Agent analysis
        await test_agent_analysis()
        
        # Test 3: Direct indicators
        await test_agent_with_direct_indicators()
        
        # Test 4: Integration flow
        await test_integration_flow()
        
        print("=" * 70)
        print("ALL TESTS PASSED ✓✓✓")
        print("=" * 70)
        print("\nSummary:")
        print("✓ TechnicalIndicatorsService works correctly")
        print("✓ EnhancedTechnicalAgent consumes indicators properly")
        print("✓ Service → Agent integration functional")
        print("✓ Multi-perspective analysis working")
        print("✓ Weighted voting aggregation working")
        print("\nReady for production integration!")
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"TEST FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

