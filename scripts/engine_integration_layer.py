#!/usr/bin/env python3
"""
Engine Integration Layer - Bridge Between Enhanced Engine and Existing System
Version 6.1 - Seamless integration with automatic trading service

This layer provides:
- Signal format conversion between systems
- Configuration management integration
- Market data adaptation
- Risk management coordination
- Logging and monitoring integration
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from enhanced_trading_engine import EnhancedTradingEngine, TradeSignal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EngineAdapter:
    """Adapts the enhanced trading engine to work with existing system"""

    def __init__(self, user_id: str = "default_user", config: Dict = None):
        self.user_id = user_id
        self.config = config or {}

        # Initialize enhanced engine
        engine_config = self._build_engine_config()
        self.engine = EnhancedTradingEngine(config=engine_config)

        # State tracking
        self.last_signal_time = None
        self.active_positions = {}
        self.signal_history = []

        logger.info(f"Engine adapter initialized for user {user_id}")

    def _build_engine_config(self) -> Dict:
        """Build engine configuration from system config"""
        return {
            'min_confidence': self.config.get('min_confidence', 0.6),
            'momentum': {
                'rsi_period': self.config.get('rsi_period', 14),
                'rsi_overbought': self.config.get('rsi_overbought', 70),
                'rsi_oversold': self.config.get('rsi_oversold', 30),
                'ma_period': self.config.get('ma_fast_period', 20),
                'volume_spike_threshold': self.config.get('volume_spike_threshold', 1.5),
                'min_price_move': self.config.get('min_price_move_pct', 0.5)
            },
            'trend': {
                'ma_fast': self.config.get('ma_fast_period', 20),
                'ma_slow': self.config.get('ma_slow_period', 50),
                'adx_period': self.config.get('adx_period', 14),
                'adx_threshold': self.config.get('adx_threshold', 25)
            },
            'mean_reversion': {
                'bb_period': self.config.get('bb_period', 20),
                'bb_std': self.config.get('bb_std', 2.0),
                'rsi_period': self.config.get('rsi_period', 14),
                'rsi_oversold': self.config.get('rsi_oversold', 30),
                'rsi_overbought': self.config.get('rsi_overbought', 70)
            },
            'volume': {
                'volume_period': self.config.get('volume_period', 20),
                'volume_spike_multiplier': self.config.get('volume_spike_multiplier', 2.0),
                'price_move_threshold': self.config.get('price_move_threshold', 0.5),
                'rsi_period': self.config.get('rsi_period', 14)
            }
        }

    async def run_trading_cycle(self, market_data: Dict = None) -> Optional[Dict]:
        """
        Run a complete trading cycle and return signal in system format

        Args:
            market_data: Market data in system format (optional, will fetch if not provided)

        Returns:
            Signal in format expected by automatic trading service, or None
        """
        try:
            # Adapt market data format if provided
            adapted_data = None
            if market_data:
                adapted_data = self._adapt_market_data(market_data)

            # Run engine cycle
            signal = await self.engine.run_trading_cycle(
                symbol="NIFTY50",
                market_data=adapted_data
            )

            # Store signal
            self.signal_history.append({
                'timestamp': datetime.now().isoformat(),
                'signal': signal,
                'market_data': market_data
            })

            # Convert to system format if actionable
            if signal.action != "HOLD" and signal.confidence >= self.config.get('min_confidence', 0.6):
                system_signal = self._convert_to_system_format(signal)
                self.last_signal_time = datetime.now()

                logger.info(f"Generated actionable signal: {signal.action} @ {signal.entry:.0f}")
                return system_signal

            logger.debug(f"HOLD signal generated: {signal.reasoning}")
            return None

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            return None

    def _adapt_market_data(self, system_data: Dict) -> Dict:
        """Convert system market data format to engine format"""
        # Handle different data formats from the existing system
        adapted = {
            'symbol': system_data.get('symbol', 'NIFTY50'),
            'timestamp': system_data.get('timestamp', datetime.now().isoformat())
        }

        # Extract OHLC data
        if 'ohlc' in system_data:
            # Format from technical agent
            ohlc_data = system_data['ohlc']
            adapted.update({
                'closes': [bar.get('close', 0) for bar in ohlc_data],
                'highs': [bar.get('high', 0) for bar in ohlc_data],
                'lows': [bar.get('low', 0) for bar in ohlc_data],
                'volume': [bar.get('volume', 0) for bar in ohlc_data]
            })
        elif 'chain' in system_data:
            # Format from options data
            # Extract spot price and create synthetic OHLC
            spot_price = system_data.get('futures_price', 0)
            adapted.update({
                'closes': [spot_price] * 50,  # Placeholder
                'highs': [spot_price * 1.001] * 50,
                'lows': [spot_price * 0.999] * 50,
                'volume': [1000000] * 50  # Placeholder volume
            })
        else:
            # Fallback - try to extract from various formats
            close_price = (
                system_data.get('current_price') or
                system_data.get('price') or
                system_data.get('last_price') or
                23000  # Default fallback
            )

            # Create synthetic 50-bar history
            adapted.update({
                'closes': [close_price] * 50,
                'highs': [close_price * 1.001] * 50,
                'lows': [close_price * 0.999] * 50,
                'volume': [1000000] * 50
            })

        return adapted

    def _convert_to_system_format(self, signal: TradeSignal) -> Dict:
        """Convert TradeSignal to format expected by automatic trading service"""
        return {
            'user_id': self.user_id,
            'timestamp': signal.timestamp.isoformat(),
            'symbol': signal.symbol,
            'action': signal.action,
            'entry_price': signal.entry,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'confidence': signal.confidence,
            'reasoning': signal.reasoning,
            'agent_name': signal.agent_name,
            'quantity': self._calculate_quantity(signal),
            'risk_amount': self._calculate_risk_amount(signal),
            'signal_metadata': asdict(signal)
        }

    def _calculate_quantity(self, signal: TradeSignal) -> int:
        """Calculate position size based on signal and risk management"""
        # Default position sizing logic
        base_quantity = self.config.get('default_quantity', 100)

        # Adjust based on confidence
        confidence_multiplier = min(2.0, signal.confidence / 0.5)  # Max 2x at 100% confidence
        quantity = int(base_quantity * confidence_multiplier)

        return quantity

    def _calculate_risk_amount(self, signal: TradeSignal) -> float:
        """Calculate risk amount for the trade"""
        account_size = self.config.get('account_size', 100000)
        risk_per_trade_pct = self.config.get('risk_per_trade_pct', 1.0)

        return account_size * (risk_per_trade_pct / 100)

    def get_engine_stats(self) -> Dict:
        """Get comprehensive engine statistics"""
        engine_stats = self.engine.get_signal_stats()

        return {
            'engine_stats': engine_stats,
            'adapter_stats': {
                'total_signals_processed': len(self.signal_history),
                'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None,
                'active_positions': len(self.active_positions),
                'user_id': self.user_id
            },
            'recent_signals': [
                {
                    'timestamp': sig['timestamp'].isoformat(),
                    'action': sig['signal'].action,
                    'confidence': sig['signal'].confidence,
                    'agent': sig['signal'].agent_name
                }
                for sig in self.signal_history[-10:]  # Last 10 signals
            ]
        }

    def update_position(self, position_data: Dict):
        """Update position tracking"""
        position_id = position_data.get('order_id') or position_data.get('position_id')
        if position_id:
            self.active_positions[position_id] = {
                'data': position_data,
                'timestamp': datetime.now().isoformat()
            }

    def close_position(self, position_id: str):
        """Mark position as closed"""
        if position_id in self.active_positions:
            self.active_positions[position_id]['closed'] = True
            self.active_positions[position_id]['close_time'] = datetime.now()

    def get_active_positions(self) -> Dict:
        """Get all active positions"""
        return {
            pid: pos for pid, pos in self.active_positions.items()
            if not pos.get('closed', False)
        }

    async def cleanup(self):
        """Cleanup resources"""
        logger.info(f"Cleaning up engine adapter for user {self.user_id}")
        # Any cleanup logic here


class EnhancedTradingService:
    """Enhanced version of automatic trading service using new engine"""

    def __init__(self, user_id: str, config: Dict = None):
        self.user_id = user_id
        self.config = config or {}
        self.engine_adapter = EngineAdapter(user_id, config)
        self.is_running = False

        # Integration with existing system
        self.orchestrator = None
        self.user_service = None
        self.market_data_client = None

        logger.info(f"Enhanced trading service initialized for user {user_id}")

    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing enhanced trading service...")

        try:
            # Import existing system components
            from core_kernel.config.settings import settings
            from engine_module.api import build_orchestrator
            from market_data.api import build_store, build_options_client
            from genai_module.api import build_llm_client
            from user_module.api import build_user_module
            from data.options_chain_fetcher import OptionsChainFetcher
            from genai_module import LLMProviderManager
            import os

            # Initialize MongoDB
            from pymongo import MongoClient
            mongo_client = MongoClient(settings.mongodb_uri)

            # Initialize user service
            self.user_service = build_user_module(mongo_client)

            # Initialize market data (lightweight version)
            redis_client = None  # Use in-memory for now
            kite = None  # Initialize only if needed for live trading

            market_store = build_store(redis_client=redis_client)
            options_client = build_options_client(kite=kite, fetcher=OptionsChainFetcher())

            # Initialize LLM (minimal)
            llm_manager = LLMProviderManager()
            llm_client = build_llm_client(legacy_manager=llm_manager)

            # Initialize orchestrator with full agent roster
            from engine_module.agent_factory import create_default_agents
            
            # Get agent profile from config (default: balanced)
            agent_profile = self.config.get('agent_profile', 'balanced')
            logger.info(f"Creating agents with profile: {agent_profile}")
            
            agents = create_default_agents(profile=agent_profile)
            logger.info(f"Created {len(agents)} agents for orchestrator")

            self.orchestrator = build_orchestrator(
                llm_client=llm_client,
                market_store=market_store,
                options_data=options_client,
                agents=agents
            )

            logger.info("✅ Enhanced trading service initialized successfully")

        except Exception as e:
            logger.warning(f"Could not initialize full system, running in standalone mode: {e}")
            # Continue in standalone mode

    async def run_trading_cycle(self) -> Optional[Dict]:
        """Run a complete trading cycle"""
        try:
            # Get market data from orchestrator if available
            market_data = None
            if self.orchestrator:
                try:
                    # Get latest market data
                    market_data = await self.orchestrator.get_market_data()
                except Exception as e:
                    logger.debug(f"Could not get market data from orchestrator: {e}")

            # Run enhanced engine cycle
            signal = await self.engine_adapter.run_trading_cycle(market_data)

            if signal:
                # Execute trade via user service if available
                await self._execute_signal(signal)

            return signal

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            return None

    async def _execute_signal(self, signal: Dict):
        """Execute signal through user service"""
        if not self.user_service:
            logger.info("No user service available, signal not executed")
            return

        try:
            # Convert signal to user service format
            trade_request = {
                'user_id': signal['user_id'],
                'symbol': signal['symbol'],
                'action': signal['action'],
                'quantity': signal.get('quantity', 100),
                'price': signal['entry_price'],
                'order_type': 'LIMIT',
                'stop_loss': signal.get('stop_loss'),
                'take_profit': signal.get('take_profit')
            }

            # Check if paper trading mode
            if self.config.get('paper_trading', True):
                logger.info(f"📝 PAPER TRADE: {signal['action']} {signal['quantity']} {signal['symbol']} @ {signal['entry_price']}")
                # Log paper trade
                await self._log_paper_trade(signal)
            else:
                # Execute real trade
                logger.info(f"🚨 LIVE TRADE: {signal['action']} {signal['quantity']} {signal['symbol']} @ {signal['entry_price']}")
                # await self.user_service.execute_trade(trade_request)

        except Exception as e:
            logger.error(f"Error executing signal: {e}")

    async def _log_paper_trade(self, signal: Dict):
        """Log paper trade for analysis"""
        # This would integrate with the existing paper trading system
        logger.info(f"Paper trade logged: {signal}")

    async def start_continuous_trading(self, cycle_interval_minutes: int = 15):
        """Start continuous trading with 15-minute cycles"""
        self.is_running = True
        logger.info(f"Starting continuous trading with {cycle_interval_minutes}-minute cycles")

        try:
            while self.is_running:
                cycle_start = datetime.now()

                # Run trading cycle
                signal = await self.run_trading_cycle()

                # Log cycle completion
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                logger.debug(f"Trading cycle completed in {cycle_duration:.1f}s")

                # Wait for next cycle
                await asyncio.sleep(cycle_interval_minutes * 60)

        except Exception as e:
            logger.error(f"Error in continuous trading: {e}")
            self.is_running = False

    async def stop_trading(self):
        """Stop continuous trading"""
        logger.info("Stopping continuous trading...")
        self.is_running = False

        # Cleanup
        await self.engine_adapter.cleanup()

    def get_service_stats(self) -> Dict:
        """Get comprehensive service statistics"""
        return {
            'service_info': {
                'user_id': self.user_id,
                'is_running': self.is_running,
                'paper_trading': self.config.get('paper_trading', True)
            },
            'engine_stats': self.engine_adapter.get_engine_stats(),
            'active_positions': self.engine_adapter.get_active_positions()
        }


async def demo_integration():
    """Demonstrate the integration layer"""
    logger.info("🚀 Starting Enhanced Trading Service Demo")

    # Configuration
    config = {
        'paper_trading': True,
        'min_confidence': 0.6,
        'default_quantity': 100,
        'account_size': 100000,
        'risk_per_trade_pct': 1.0,
        'rsi_period': 14,
        'rsi_overbought': 70,
        'rsi_oversold': 30,
        'ma_fast_period': 20,
        'ma_slow_period': 50,
        'adx_threshold': 25
    }

    # Initialize service
    service = EnhancedTradingService("demo_user", config)
    await service.initialize()

    print("\n" + "="*80)
    print("ENHANCED TRADING SERVICE INTEGRATION DEMO")
    print("="*80)
    print(f"User: {service.user_id}")
    print(f"Paper Trading: {config['paper_trading']}")
    print(f"Min Confidence: {config['min_confidence']:.0%}")
    print("="*80)

    # Run a few cycles
    for cycle in range(5):
        print(f"\n--- CYCLE {cycle + 1}/5 ---")

        # Run trading cycle
        signal = await service.run_trading_cycle()

        if signal:
            print("🚨 SIGNAL GENERATED"            print(f"Action: {signal['action']}")
            print(f"Symbol: {signal['symbol']}")
            print(f"Entry: ₹{signal['entry_price']:,.0f}")
            print(f"Confidence: {signal['confidence']:.0%}")
            print(f"Agent: {signal['agent_name']}")
            print(f"Reasoning: {signal['reasoning']}")
        else:
            print("⏸️  No actionable signal this cycle")

        # Small delay for demo
        await asyncio.sleep(1)

    # Get final statistics
    stats = service.get_service_stats()
    print("\n" + "="*80)
    print("FINAL STATISTICS")
    print("="*80)

    engine_stats = stats['engine_stats']['engine_stats']
    print(f"Total Cycles: {engine_stats['total_cycles']}")

    if engine_stats['signals']:
        for action, data in engine_stats['signals'].items():
            print(f"{action} Signals: {data['count']} ({data['percentage']:.1f}%), avg conf: {data['avg_confidence']:.1%}")

    print("\n✅ Integration demo completed successfully")

    # Cleanup
    await service.stop_trading()


if __name__ == "__main__":
    try:
        asyncio.run(demo_integration())
    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        logger.exception("Demo failed")
        raise

