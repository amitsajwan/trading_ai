"""Enhanced trading API - 15-minute cycle orchestrator integration.

This API provides a clean interface to the enhanced 15-minute cycle trading system,
integrating with the existing modular architecture.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .enhanced_orchestrator import EnhancedTradingOrchestrator
from .agents.momentum_agent import MomentumAgent
from .agents.trend_agent import TrendAgent
from .agents.mean_reversion_agent import MeanReversionAgent
from .agents.volume_agent import VolumeAgent

# Import risk and backtesting modules
try:
    from risk_module.risk_manager import RiskManager
    from backtesting_module.backtest_engine import BacktestEngine
    RISK_MODULE_AVAILABLE = True
except ImportError:
    RISK_MODULE_AVAILABLE = False
    RiskManager = None
    BacktestEngine = None

logger = logging.getLogger(__name__)


class MarketDataAdapter:
    """Adapter for market data sources to work with enhanced orchestrator."""

    def __init__(self, data_source=None):
        """Initialize with data source (could be existing market store)."""
        self.data_source = data_source

    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        """Get OHLC data in format expected by agents."""
        try:
            if self.data_source:
                # Use existing data source
                raw_data = await self.data_source.get_ohlc(symbol, periods)
            else:
                # Generate simulated data for demo
                raw_data = self._generate_simulated_data(symbol, periods)

            # Convert to agent format
            ohlc_list = []
            for item in raw_data[-periods:]:  # Ensure we don't exceed requested periods
                ohlc_list.append({
                    'timestamp': item.get('timestamp', datetime.now().isoformat()),
                    'open': float(item.get('open', item.get('close', 23000))),
                    'high': float(item.get('high', item.get('close', 23000))),
                    'low': float(item.get('low', item.get('close', 23000))),
                    'close': float(item.get('close', 23000)),
                    'volume': int(item.get('volume', 1000000))
                })

            return ohlc_list

        except Exception as e:
            logger.error(f"Error getting OHLC data: {e}")
            return []

    def _generate_simulated_data(self, symbol: str, periods: int) -> List[Dict[str, Any]]:
        """Generate simulated market data for demo purposes."""
        import numpy as np

        base_price = 23000 if "NIFTY" in symbol.upper() else 45000
        data = []

        current_price = base_price
        timestamp = datetime.now()

        for i in range(periods):
            # Generate realistic price movement
            change = np.random.normal(0, 15)
            current_price += change

            # Generate OHLC
            high = current_price + abs(np.random.normal(0, 5))
            low = current_price - abs(np.random.normal(0, 5))
            open_price = current_price + np.random.normal(0, 3)
            volume = int(np.random.normal(20000000, 5000000))

            data.append({
                'timestamp': timestamp.isoformat(),
                'open': open_price,
                'high': high,
                'low': low,
                'close': current_price,
                'volume': volume
            })

            # Move to next 15-minute period
            timestamp = timestamp.replace(minute=(timestamp.minute + 15) % 60)

        return data


class EnhancedTradingAPI:
    """Enhanced Trading API - integrates 15-minute cycle system with existing architecture."""

    def __init__(self, config: Dict[str, Any] = None, position_provider=None):
        """Initialize enhanced trading API.
        
        Args:
            config: Configuration dictionary
            position_provider: Optional position provider implementing PositionProvider protocol
        """
        self.config = config or self._get_default_config()

        # Initialize components
        self.market_data_adapter = MarketDataAdapter()
        self.position_provider = position_provider
        self.orchestrator = None
        self.risk_manager = None
        self.backtest_engine = None

        # State
        self.is_initialized = False

        logger.info("Enhanced Trading API initialized")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default API configuration."""
        return {
            'symbol': 'NIFTY50',
            'cycle_interval_minutes': 15,
            'min_confidence_threshold': 0.6,
            'risk_per_trade_pct': 1.0,
            'position_size_pct': 5.0,
            'account_size': 100000,
            'agents': {
                'momentum': {'enabled': True},
                'trend': {'enabled': True},
                'mean_reversion': {'enabled': True},
                'volume': {'enabled': True}
            }
        }

    async def initialize(self, market_data_source=None) -> bool:
        """Initialize all trading components."""
        try:
            logger.info("Initializing enhanced trading components...")

            # Update market data adapter if source provided
            if market_data_source:
                self.market_data_adapter = MarketDataAdapter(market_data_source)

            # Initialize orchestrator
            orchestrator_config = {
                'symbol': self.config.get('symbol', 'NIFTY50'),
                'min_confidence_threshold': self.config.get('min_confidence_threshold', 0.6),
                'risk_per_trade_pct': self.config.get('risk_per_trade_pct', 1.0),
                'position_size_pct': self.config.get('position_size_pct', 5.0),
                'account_size': self.config.get('account_size', 100000),
                'agents': self.config.get('agents', {
                    'momentum': {'enabled': True},
                    'trend': {'enabled': True},
                    'mean_reversion': {'enabled': True},
                    'volume': {'enabled': True}
                })
            }

            self.orchestrator = EnhancedTradingOrchestrator(
                market_data_provider=self.market_data_adapter,
                position_provider=self.position_provider,
                config=orchestrator_config
            )

            # Initialize risk manager if available
            if RISK_MODULE_AVAILABLE:
                risk_config = {
                    'initial_capital': self.config['account_size'],
                    'max_risk_per_trade_pct': self.config['risk_per_trade_pct'],
                    'max_position_size_pct': self.config['position_size_pct'],
                }
                self.risk_manager = RiskManager(risk_config)

            # Initialize backtest engine if available
            if BacktestEngine:
                self.backtest_engine = BacktestEngine(
                    initial_capital=self.config['account_size']
                )

            self.is_initialized = True
            logger.info("✅ Enhanced trading components initialized successfully")
            return True

        except Exception as e:
            logger.exception(f"Failed to initialize trading components: {e}")
            return False

    async def run_trading_cycle(self, symbol: str = None) -> Dict[str, Any]:
        """Run a single 15-minute trading cycle."""
        if not self.is_initialized:
            return {'error': 'API not initialized'}

        try:
            symbol = symbol or self.config['symbol']
            context = {'symbol': symbol, 'timestamp': datetime.now()}

            # Run orchestrator cycle
            result = await self.orchestrator.run_cycle(context)

            # Convert result to API format
            response = {
                'cycle_completed': True,
                'timestamp': datetime.now().isoformat(),
                'decision': result.decision,
                'confidence': result.confidence,
                'reasoning': result.details.get('reasoning', ''),
                'execution_ready': False,
                'risk_assessed': False
            }

            # Add position details if trade signal
            if result.decision in ['BUY', 'SELL']:
                details = result.details
                response.update({
                    'entry_price': details.get('entry_price'),
                    'stop_loss': details.get('stop_loss'),
                    'take_profit': details.get('take_profit'),
                    'quantity': details.get('quantity', 0),
                    'execution_ready': True
                })

                # Add risk assessment if available
                if self.risk_manager and details.get('entry_price'):
                    signal_data = {
                        'entry_price': details.get('entry_price'),
                        'stop_loss': details.get('stop_loss'),
                        'take_profit': details.get('take_profit'),
                        'confidence': result.confidence
                    }
                    risk_metrics = await self.risk_manager.assess_trade_risk(signal_data)

                    response.update({
                        'risk_assessed': True,
                        'risk_level': risk_metrics.risk_level.value,
                        'risk_checks_passed': risk_metrics.risk_checks_passed,
                        'risk_warnings': risk_metrics.risk_warnings,
                        'position_size': risk_metrics.position_size,
                        'risk_amount': risk_metrics.risk_amount
                    })

            return response

        except Exception as e:
            logger.exception(f"Error in trading cycle: {e}")
            return {
                'cycle_completed': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def run_backtest(self, historical_data_path: str) -> Dict[str, Any]:
        """Run backtest on historical data."""
        if not self.is_initialized or not self.backtest_engine:
            return {'error': 'Backtesting not available'}

        try:
            import pandas as pd

            # Load historical data
            df = pd.read_csv(historical_data_path)

            # Run backtest
            results = await self.backtest_engine.run_backtest(df, self.orchestrator.config)

            return {
                'backtest_completed': True,
                'results': results.to_dict()
            }

        except Exception as e:
            logger.exception(f"Error in backtest: {e}")
            return {
                'backtest_completed': False,
                'error': str(e)
            }

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            'initialized': self.is_initialized,
            'config': self.config,
            'orchestrator_stats': self.orchestrator.get_cycle_stats() if self.orchestrator else None,
            'risk_status': self.risk_manager.get_risk_report() if self.risk_manager else None,
            'modules_available': {
                'risk_management': RISK_MODULE_AVAILABLE,
                'backtesting': BacktestEngine is not None
            }
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update API configuration."""
        self.config.update(new_config)

        # Update orchestrator if it exists
        if self.orchestrator:
            self.orchestrator.update_config(new_config)

        logger.info(f"API configuration updated: {list(new_config.keys())}")


def build_enhanced_trading_api(config: Dict[str, Any] = None) -> EnhancedTradingAPI:
    """Factory function to build enhanced trading API."""
    return EnhancedTradingAPI(config)


async def run_enhanced_cycle(api: EnhancedTradingAPI, symbol: str = "NIFTY50") -> Dict[str, Any]:
    """Helper function to run a trading cycle."""
    if not api.is_initialized:
        initialized = await api.initialize()
        if not initialized:
            return {'error': 'Failed to initialize API'}

    return await api.run_trading_cycle(symbol)


# Integration function for existing automatic_trading_service.py
async def get_enhanced_trading_signal(symbol: str = "NIFTY50",
                                    config: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """Get enhanced trading signal - can be called from existing trading service."""
    try:
        api = build_enhanced_trading_api(config)
        await api.initialize()

        result = await api.run_trading_cycle(symbol)

        if result.get('execution_ready', False):
            # Return in format expected by existing execution logic
            return {
                'action': result['decision'],
                'symbol': symbol,
                'entry_price': result['entry_price'],
                'stop_loss': result['stop_loss'],
                'take_profit': result['take_profit'],
                'quantity': result['quantity'],
                'confidence': result['confidence'],
                'reasoning': result['reasoning'],
                'risk_assessed': result.get('risk_assessed', False),
                'risk_checks_passed': result.get('risk_checks_passed', True),
                'enhanced_signal': True  # Flag to identify enhanced signals
            }

        return None  # No actionable signal

    except Exception as e:
        logger.error(f"Error getting enhanced trading signal: {e}")
        return None

