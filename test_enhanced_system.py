#!/usr/bin/env python3
"""
Test Enhanced Trading System - End-to-End Verification
"""

import asyncio
import sys
import os

# Add module paths
sys.path.insert(0, 'engine_module/src')
sys.path.insert(0, 'risk_module/src')
sys.path.insert(0, 'backtesting_module/src')

async def test_enhanced_agents():
    """Test enhanced agents individually"""
    print("Testing Enhanced Agents...")

    from engine_module.agents.momentum_agent import MomentumAgent
    from engine_module.agents.trend_agent import TrendAgent
    from engine_module.agents.mean_reversion_agent import MeanReversionAgent
    from engine_module.agents.volume_agent import VolumeAgent

    # Sample market data
    sample_data = {
        'ohlc': [
            {'timestamp': '2024-01-01T09:15:00', 'open': 23000, 'high': 23050, 'low': 22980, 'close': 23020, 'volume': 15000000},
            {'timestamp': '2024-01-01T09:30:00', 'open': 23020, 'high': 23080, 'low': 23000, 'close': 23060, 'volume': 18000000},
            {'timestamp': '2024-01-01T09:45:00', 'open': 23060, 'high': 23100, 'low': 23040, 'close': 23080, 'volume': 22000000},
        ] * 10,  # Repeat for more data
        'symbol': 'NIFTY50',
        'current_price': 23080
    }

    agents = [
        ('Momentum', MomentumAgent()),
        ('Trend', TrendAgent()),
        ('MeanReversion', MeanReversionAgent()),
        ('Volume', VolumeAgent()),
    ]

    results = {}
    for name, agent in agents:
        try:
            result = await agent.analyze(sample_data)
            results[name] = {
                'decision': result.decision,
                'confidence': result.confidence,
                'success': True
            }
            print(f"  {name} Agent: {result.decision} ({result.confidence:.1%})")
        except Exception as e:
            results[name] = {'success': False, 'error': str(e)}
            print(f"  {name} Agent: FAILED - {e}")

    return results


async def test_orchestrator():
    """Test enhanced orchestrator"""
    print("\nTesting Enhanced Orchestrator...")

    try:
        from engine_module.enhanced_orchestrator import EnhancedTradingOrchestrator

        # Simple market data provider for testing
        class TestMarketDataProvider:
            async def get_ohlc_data(self, symbol, periods=50):
                return [
                    {'timestamp': f'2024-01-{i:02d}T10:00:00', 'open': 23000+i*5, 'high': 23020+i*5,
                     'low': 22980+i*5, 'close': 23000+i*5, 'volume': 15000000}
                    for i in range(periods)
                ]

        provider = TestMarketDataProvider()
        orchestrator = EnhancedTradingOrchestrator(provider, {'symbol': 'NIFTY50'})

        # Test cycle
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)

        print(f"  Orchestrator Decision: {result.decision}")
        print(f"  Confidence: {result.confidence:.1%}")
        print("  Success: True")

        return {'success': True, 'decision': result.decision, 'confidence': result.confidence}

    except Exception as e:
        print(f"  Orchestrator Test: FAILED - {e}")
        return {'success': False, 'error': str(e)}


async def test_risk_management():
    """Test risk management system"""
    print("\nTesting Risk Management...")

    try:
        from risk_module.risk_manager import RiskManager

        config = {
            'initial_capital': 100000,
            'max_risk_per_trade_pct': 1.0,
            'max_portfolio_risk_pct': 5.0,
            'max_daily_loss_pct': 3.0,
            'max_consecutive_losses': 3,
            'min_reward_ratio': 1.5,
            'max_position_size_pct': 5.0,
            'margin_requirement_pct': 10.0,
            'max_open_positions': 3,
            'cooldown_after_loss_min': 15,
            'circuit_breaker_loss_pct': 10.0,
        }

        risk_manager = RiskManager(config)

        # Test risk assessment
        signal = {
            'entry_price': 23100,
            'stop_loss': 23000,
            'take_profit': 23200,
            'confidence': 0.75
        }

        risk_metrics = await risk_manager.assess_trade_risk(signal)

        print(f"  Risk Assessment: {risk_metrics.risk_checks_passed}")
        print(f"  Position Size: {risk_metrics.position_size}")
        print(f"  Risk Amount: {risk_metrics.risk_amount}")
        print("  Success: True")

        return {
            'success': True,
            'approved': risk_metrics.risk_checks_passed,
            'position_size': risk_metrics.position_size
        }

    except Exception as e:
        print(f"  Risk Management Test: FAILED - {e}")
        return {'success': False, 'error': str(e)}


async def test_integration_api():
    """Test enhanced API integration"""
    print("\nTesting Enhanced API Integration...")

    try:
        from engine_module.enhanced_api import EnhancedTradingAPI

        api = EnhancedTradingAPI({
            'symbol': 'NIFTY50',
            'min_confidence_threshold': 0.6
        })

        # Initialize
        success = await api.initialize()
        if not success:
            print("  API Initialization: FAILED")
            return {'success': False, 'error': 'Initialization failed'}

        # Test cycle
        result = await api.run_trading_cycle('NIFTY50')

        print(f"  API Cycle Result: {result.get('decision', 'N/A')}")
        print("  Success: True")

        return {
            'success': True,
            'has_signal': result.get('execution_ready', False),
            'decision': result.get('decision')
        }

    except Exception as e:
        print(f"  API Integration Test: FAILED - {e}")
        return {'success': False, 'error': str(e)}


async def main():
    """Run all tests"""
    print("=" * 60)
    print("ENHANCED TRADING SYSTEM - VERIFICATION TESTS")
    print("=" * 60)

    # Run all tests
    test_results = {}

    test_results['agents'] = await test_enhanced_agents()
    test_results['orchestrator'] = await test_orchestrator()
    test_results['risk_management'] = await test_risk_management()
    test_results['api_integration'] = await test_integration_api()

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, result in test_results.items():
        status = "PASS" if result.get('success', False) else "FAIL"
        if not result.get('success', False):
            all_passed = False
        print(f"{test_name.upper():<15}: {status}")

    print("\nOverall Status:", "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED")

    if all_passed:
        print("\n[SUCCESS] Enhanced Trading System is fully operational!")
        print("   - Agents: Working")
        print("   - Orchestrator: Working")
        print("   - Risk Management: Working")
        print("   - API Integration: Working")
        print("\nReady for production use!")
    else:
        print("\n[WARN] Some tests failed. Check the output above for details.")

    return all_passed


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test suite failed: {e}")
        exit(1)

