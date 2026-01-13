#!/usr/bin/env python3
"""
Enhanced Trading Integration - Seamless Integration with Existing System

This script demonstrates how to integrate the enhanced 15-minute cycle trading system
with your existing modular architecture. It shows how to use the enhanced agents,
orchestrator, and risk management within your current system.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add module paths to work with existing system
sys.path.insert(0, 'engine_module/src')
sys.path.insert(0, 'risk_module/src')
sys.path.insert(0, 'backtesting_module/src')
sys.path.insert(0, 'data_niftybank/src')

async def demo_enhanced_agents():
    """Demonstrate enhanced agents working with existing contracts."""
    print("=== ENHANCED AGENTS DEMO ===")

    from engine_module.contracts import AnalysisResult
    from engine_module.agents.momentum_agent import MomentumAgent
    from engine_module.agents.trend_agent import TrendAgent
    from engine_module.agents.mean_reversion_agent import MeanReversionAgent
    from engine_module.agents.volume_agent import VolumeAgent

    # Create sample market data (OHLC format expected by agents)
    sample_ohlc = [
        {'timestamp': '2024-01-01T09:15:00', 'open': 23000, 'high': 23050, 'low': 22980, 'close': 23020, 'volume': 15000000},
        {'timestamp': '2024-01-01T09:30:00', 'open': 23020, 'high': 23080, 'low': 23000, 'close': 23060, 'volume': 18000000},
        {'timestamp': '2024-01-01T09:45:00', 'open': 23060, 'high': 23100, 'low': 23040, 'close': 23080, 'volume': 22000000},
        {'timestamp': '2024-01-01T10:00:00', 'open': 23080, 'high': 23120, 'low': 23060, 'close': 23100, 'volume': 25000000},
        {'timestamp': '2024-01-01T10:15:00', 'open': 23100, 'high': 23150, 'low': 23080, 'close': 23120, 'volume': 20000000},
        # Add more data points...
    ] * 5  # Repeat for more history

    context = {
        'ohlc': sample_ohlc,
        'symbol': 'NIFTY50',
        'current_price': 23120
    }

    # Test each enhanced agent
    agents = [
        ('Momentum Agent', MomentumAgent()),
        ('Trend Agent', TrendAgent()),
        ('Mean Reversion Agent', MeanReversionAgent()),
        ('Volume Agent', VolumeAgent()),
    ]

    print("Testing enhanced agents with sample market data:")
    print()

    for agent_name, agent in agents:
        try:
            result = await agent.analyze(context)
            print(f"[+] {agent_name}:")
            print(f"   Decision: {result.decision}")
            print(f"   Confidence: {result.confidence:.0%}")
            if result.details and 'reasoning' in result.details:
                reasoning = result.details['reasoning']
                if isinstance(reasoning, list):
                    reasoning = reasoning[:2]  # Show first 2 reasons
                print(f"   Reasoning: {reasoning}")
            print()
        except Exception as e:
            print(f"[ERROR] {agent_name} failed: {e}")
            print()


async def demo_enhanced_orchestrator():
    """Demonstrate enhanced orchestrator with market data provider."""
    print("=== ENHANCED ORCHESTRATOR DEMO ===")

    from engine_module.enhanced_orchestrator import EnhancedTradingOrchestrator

    # Simple market data provider for demo
    class DemoMarketDataProvider:
        async def get_ohlc_data(self, symbol: str, periods: int = 100):
            # Generate sample data
            data = []
            price = 23000
            for i in range(periods):
                price += (i % 10 - 5) * 2  # Some trend
                data.append({
                    'timestamp': f'2024-01-{i%28+1:02d}T{(9+i%9):02d}:{(15+i*15)%60:02d}:00',
                    'open': price,
                    'high': price + 20,
                    'low': price - 20,
                    'close': price + (i % 3 - 1) * 10,
                    'volume': 20000000 + i * 100000
                })
            return data[-periods:]

    # Initialize orchestrator
    market_provider = DemoMarketDataProvider()
    orchestrator = EnhancedTradingOrchestrator(market_provider, {
        'symbol': 'NIFTY50',
        'min_confidence_threshold': 0.6,
        'account_size': 100000
    })

    print("Running orchestrator cycles...")
    print()

    for cycle in range(1, 4):
        print(f"--- Cycle {cycle} ---")

        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)

        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence:.0%}")
        print(f"Details: {result.details.get('reasoning', 'N/A')}")
        print()

        # Small delay
        await asyncio.sleep(0.5)


async def demo_risk_management():
    """Demonstrate risk management integration."""
    print("=== RISK MANAGEMENT DEMO ===")

    try:
        from risk_module.risk_manager import RiskManager, RiskMetrics

        # Initialize risk manager
        risk_config = {
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

        risk_manager = RiskManager(risk_config)

        # Sample trading signals
        signals = [
            {'entry_price': 23100, 'stop_loss': 23000, 'take_profit': 23200, 'confidence': 0.75},
            {'entry_price': 23050, 'stop_loss': 23150, 'take_profit': 22950, 'confidence': 0.80},
            {'entry_price': 23120, 'stop_loss': 23080, 'take_profit': 23180, 'confidence': 0.65},
        ]

        print("Risk assessment for sample signals:")
        print()

        for i, signal in enumerate(signals, 1):
            print(f"Signal {i}: Entry INR{signal['entry_price']}, SL INR{signal['stop_loss']}, TP INR{signal['take_profit']}")

            risk_metrics = await risk_manager.assess_trade_risk(signal)

            print(f"   [OK] Approved: {risk_metrics.risk_checks_passed}")
            print(f"   [INFO] Risk Level: {risk_metrics.risk_level.value}")
            print(f"   [TARGET] Position Size: {risk_metrics.position_size} shares")
            print(f"   [MONEY] Risk Amount: INR{risk_metrics.risk_amount:,.0f}")
            print(f"   [CHART] Reward Ratio: {risk_metrics.reward_ratio:.1f}:1")

            if risk_metrics.risk_warnings:
                print(f"   [WARN] Warnings: {', '.join(risk_metrics.risk_warnings)}")

            print()

    except ImportError:
        print("[WARN] Risk management module not available")
        print("   Install risk_module to enable risk management features")


async def demo_backtesting():
    """Demonstrate backtesting integration."""
    print("=== BACKTESTING DEMO ===")

    try:
        import pandas as pd
        from backtesting_module.backtest_engine import BacktestEngine

        # Generate sample historical data
        dates = pd.date_range('2024-01-01', periods=100, freq='15min')
        np.random.seed(42)

        base_price = 23000
        prices = []
        current_price = base_price

        for date in dates:
            change = np.random.normal(0, 15)
            current_price += change

            prices.append({
                'timestamp': date,
                'open': current_price,
                'high': current_price + abs(np.random.normal(0, 5)),
                'low': current_price - abs(np.random.normal(0, 5)),
                'close': current_price,
                'volume': int(np.random.normal(20000000, 5000000))
            })

        df = pd.DataFrame(prices)
        df.set_index('timestamp', inplace=True)

        print(f"Generated {len(df)} data points for backtesting")

        # Initialize backtest engine
        backtest_engine = BacktestEngine(initial_capital=100000)

        # Use default orchestrator config
        orchestrator_config = {
            'symbol': 'NIFTY50',
            'min_confidence_threshold': 0.6,
        }

        # Run backtest
        results = await backtest_engine.run_backtest(df, orchestrator_config)

        print("\n[TARGET] BACKTEST RESULTS")
        print("-" * 30)
        print(f"Total Trades: {results.total_trades}")
        print(f"Win Rate: {results.win_rate:.1f}%")
        print(f"Profit Factor: {results.profit_factor:.2f}")
        print(f"Total P&L: INR{results.total_pnl:,.0f}")
        print(f"Max Drawdown: {results.max_drawdown_pct:.1f}%")
        print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
    except ImportError:
        print("[WARN] Backtesting module not available")
        print("   Install backtesting_module to enable backtesting features")


async def demo_integration_with_existing():
    """Demonstrate integration with existing automatic trading service."""
    print("=== INTEGRATION WITH EXISTING SYSTEM ===")

    try:
        from engine_module.enhanced_api import get_enhanced_trading_signal

        print("Getting enhanced trading signal...")
        print("(This would integrate with your existing automatic_trading_service.py)")

        # Get enhanced signal
        signal = await get_enhanced_trading_signal("NIFTY50", {
            'min_confidence_threshold': 0.6,
            'account_size': 100000
        })

        if signal:
            print("[ALERT] ENHANCED SIGNAL GENERATED:")
            print(f"   Action: {signal['action']}")
            print(f"   Symbol: {signal['symbol']}")
            print(f"   Entry: INR{signal['entry_price']:,.0f}")
            print(f"   Stop Loss: INR{signal['stop_loss']:,.0f}")
            print(f"   Take Profit: INR{signal['take_profit']:,.0f}")
            print(f"   Quantity: {signal['quantity']}")
            print(f"   Confidence: {signal['confidence']:.0%}")
            print(f"   Risk Assessed: {signal['risk_assessed']}")
            print(f"   Risk Checks Passed: {signal['risk_checks_passed']}")
        else:
            print("[PAUSE] No actionable enhanced signal at this time")

    except ImportError as e:
        print(f"[WARN] Integration not available: {e}")


async def main():
    """Run the complete integration demo."""
    print("=" * 80)
    print("ENHANCED TRADING SYSTEM - MODULAR INTEGRATION DEMO")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Run all demos
    await demo_enhanced_agents()
    print()

    await demo_enhanced_orchestrator()
    print()

    await demo_risk_management()
    print()

    await demo_backtesting()
    print()

    await demo_integration_with_existing()

    print()
    print("=" * 80)
    print("[SUCCESS] INTEGRATION DEMO COMPLETED")
    print("=" * 80)
    print()
    print("Your enhanced 15-minute cycle trading system is now properly integrated")
    print("within your existing modular architecture!")
    print()
    print("Key integration points:")
    print("• Enhanced agents in engine_module/src/engine_module/agents/")
    print("• Risk management in risk_module/")
    print("• Backtesting in backtesting_module/")
    print("• Orchestrator in engine_module/src/engine_module/")
    print("• API integration in engine_module/src/engine_module/enhanced_api.py")
    print()
    print("Use your existing automatic_trading_service.py with enhanced signals!")


if __name__ == "__main__":
    # Import numpy for demo
    import numpy as np

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Demo interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()

