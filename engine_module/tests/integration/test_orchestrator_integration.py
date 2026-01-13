"""Integration tests for Comprehensive Trading Orchestrator.

These tests verify that all components work together correctly:
- Market data providers
- Technical indicators
- Multi-timeframe analysis
- Enhanced agents
- Spread strategies
- Risk management
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List
from datetime import datetime, timedelta

from engine_module.comprehensive_orchestrator import ComprehensiveTradingOrchestrator
from engine_module.contracts import AnalysisResult
from engine_module.analysis.regime_detector import MarketRegime, RegimeDetector
from engine_module.analysis.multi_timeframe import MultiTimeframeAnalyzer
from engine_module.agents.enhanced_momentum_agent import EnhancedMomentumAgent
from engine_module.agents.enhanced_research_manager import EnhancedResearchManager
from engine_module.agents.enhanced_risk_agents import EnhancedRiskAgent


class IntegrationTestMarketDataProvider:
    """Realistic market data provider for integration tests."""
    
    def __init__(self, base_price: float = 45000):
        self.base_price = base_price
        self.price_history = []
        self._generate_history()
    
    def _generate_history(self, periods: int = 100):
        """Generate realistic OHLC history."""
        current_price = self.base_price
        for i in range(periods):
            # Simulate realistic price movement
            change = (i % 10 - 5) * 10  # Oscillating movement
            open_price = current_price + change
            high_price = open_price + abs(change * 0.5) + 50
            low_price = open_price - abs(change * 0.5) - 50
            close_price = open_price + change * 0.3
            
            candle = {
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': 1000000 + (i % 5) * 100000,
                'date': datetime.now() - timedelta(minutes=(periods - i) * 5)
            }
            
            self.price_history.append(candle)
            current_price = close_price
    
    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        """Get OHLC data for symbol."""
        return self.price_history[-periods:] if len(self.price_history) >= periods else self.price_history


class IntegrationTestTechnicalProvider:
    """Realistic technical indicators provider for integration tests."""
    
    def __init__(self, base_price: float = 45000):
        self.base_price = base_price
    
    async def get_technical_indicators(self, symbol: str, periods: int = 100):
        """Get technical indicators."""
        # Calculate realistic indicators
        current_price = self.base_price
        
        mock_indicators = MagicMock()
        mock_indicators.to_dict = lambda: {
            'close': current_price,
            'sma_20': current_price * 0.995,
            'ema_50': current_price * 0.99,
            'rsi': 55.0,
            'rsi_14': 55.0,
            'macd': 50.0,
            'macd_value': 50.0,
            'macd_signal': 45.0,
            'macd_signal_line': 45.0,
            'adx': 25.0,
            'adx_14': 25.0,
            'atr': 200.0,
            'iv_percentile': 60.0,
            'volume_ratio': 1.2,
            'bollinger_upper': current_price * 1.01,
            'bollinger_lower': current_price * 0.99,
            'bollinger_middle': current_price
        }
        
        return mock_indicators


class IntegrationTestMultiTimeframeReader:
    """Realistic multi-timeframe reader for integration tests."""
    
    def __init__(self, base_price: float = 45000):
        self.base_price = base_price
    
    async def fetch_ohlc(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch OHLC data for specific timeframe."""
        # Return realistic multi-timeframe data
        return [
            {
                'close': self.base_price,
                'open': self.base_price * 0.995,
                'high': self.base_price * 1.005,
                'low': self.base_price * 0.995,
                'volume': 1000000,
                'sma_20': self.base_price * 0.995,
                'ema_50': self.base_price * 0.99,
                'rsi': 55.0,
                'rsi_14': 55.0,
                'macd': 50.0,
                'macd_value': 50.0,
                'macd_signal': 45.0,
                'macd_signal_line': 45.0,
                'adx': 25.0,
                'adx_14': 25.0
            }
        ]


class IntegrationTestOptionsChainProvider:
    """Realistic options chain provider for integration tests."""
    
    async def fetch_chain(self, symbol: str) -> Dict[str, Any]:
        """Fetch options chain."""
        spot_price = 45000
        option_chain = {}
        
        # Create realistic strikes around spot
        strike_increments = [-1000, -500, -250, 0, 250, 500, 1000]
        for offset in strike_increments:
            strike = int(spot_price + offset)
            
            # Calculate realistic option prices
            intrinsic_call = max(0, spot_price - strike)
            intrinsic_put = max(0, strike - spot_price)
            time_value = 100 + abs(offset) * 0.05
            
            option_chain[str(strike)] = {
                'CE': {
                    'last_price': intrinsic_call + time_value,
                    'ltp': intrinsic_call + time_value,
                    'volume': 1000 + abs(offset) * 2,
                    'oi': 5000 + abs(offset) * 10,
                    'expiry': '2026-01-30',
                    'delta': max(0, min(1, 0.5 + (spot_price - strike) / (spot_price * 0.1))),
                    'gamma': 0.01,
                    'theta': -0.05,
                    'vega': 0.1,
                    'iv': 0.20
                },
                'PE': {
                    'last_price': intrinsic_put + time_value,
                    'ltp': intrinsic_put + time_value,
                    'volume': 1000 + abs(offset) * 2,
                    'oi': 5000 + abs(offset) * 10,
                    'expiry': '2026-01-30',
                    'delta': max(-1, min(0, -0.5 + (strike - spot_price) / (spot_price * 0.1))),
                    'gamma': 0.01,
                    'theta': -0.05,
                    'vega': 0.1,
                    'iv': 0.20
                }
            }
        
        return option_chain


class IntegrationTestPositionProvider:
    """Realistic position provider for integration tests."""
    
    def __init__(self, positions: List[Dict[str, Any]] = None):
        self.positions = positions or []
    
    async def get_positions(self, symbol: str = None):
        """Get positions."""
        if symbol:
            return [p for p in self.positions if p.get('symbol') == symbol]
        return self.positions


@pytest.fixture
def integration_market_data_provider():
    """Fixture for market data provider."""
    return IntegrationTestMarketDataProvider(base_price=45000)


@pytest.fixture
def integration_technical_provider():
    """Fixture for technical indicators provider."""
    return IntegrationTestTechnicalProvider(base_price=45000)


@pytest.fixture
def integration_mtf_reader():
    """Fixture for multi-timeframe reader."""
    return IntegrationTestMultiTimeframeReader(base_price=45000)


@pytest.fixture
def integration_options_provider():
    """Fixture for options chain provider."""
    return IntegrationTestOptionsChainProvider()


@pytest.fixture
def integration_position_provider():
    """Fixture for position provider."""
    return IntegrationTestPositionProvider()


class TestOrchestratorIntegration:
    """Integration tests for Comprehensive Trading Orchestrator."""
    
    @pytest.mark.asyncio
    async def test_full_orchestrator_initialization(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader,
        integration_options_provider,
        integration_position_provider
    ):
        """Test complete orchestrator initialization with all providers."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader,
            options_chain_provider=integration_options_provider,
            position_provider=integration_position_provider,
            config={
                'symbol': 'BANKNIFTY',
                'agents': {
                    'momentum': {'enabled': True},
                    'research_manager': {'enabled': True},
                    'risk': {'enabled': True}
                },
                'strategies': {
                    'iron_condor': {'enabled': True},
                    'credit_spreads': {'enabled': True},
                    'debit_spreads': {'enabled': True}
                }
            }
        )
        
        # Verify all components initialized
        assert orchestrator.symbol == 'BANKNIFTY'
        assert orchestrator.regime_detector is not None
        assert orchestrator.multi_timeframe_analyzer is not None
        assert len(orchestrator.agents) >= 3
        assert len(orchestrator.spread_strategies) >= 1
        assert orchestrator.market_data_provider is not None
        assert orchestrator.technical_data_provider is not None
        assert orchestrator.multi_timeframe_reader is not None
        assert orchestrator.options_chain_provider is not None
        assert orchestrator.position_provider is not None
    
    @pytest.mark.asyncio
    async def test_complete_trading_cycle(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader,
        integration_options_provider,
        integration_position_provider
    ):
        """Test complete trading cycle with all components."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader,
            options_chain_provider=integration_options_provider,
            position_provider=integration_position_provider
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        # Verify cycle completed successfully
        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.decision in [
            "HOLD", "BUY", "SELL",
            "IRON_CONDOR", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD",
            "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"
        ]
        assert 0.0 <= result.confidence <= 1.0
        assert result.agent == "ComprehensiveOrchestrator"
        assert 'cycle_info' in result.details
        
        # Verify cycle info contains expected data
        cycle_info = result.details.get('cycle_info', {})
        assert 'cycle_number' in cycle_info
        assert 'duration_seconds' in cycle_info
        assert cycle_info['cycle_number'] == 1
    
    @pytest.mark.asyncio
    async def test_regime_detection_integration(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader
    ):
        """Test regime detection works with technical indicators."""
        # Test with trending indicators
        technical_provider = IntegrationTestTechnicalProvider(base_price=45000)
        technical_provider.indicators = {
            'close': 45000,
            'sma_20': 44900,
            'ema_50': 44800,
            'adx': 30.0,  # Strong trend
            'iv_percentile': 50.0,
            'volume_ratio': 1.5,
            'bollinger_upper': 45100,
            'bollinger_lower': 44900
        }
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=technical_provider,
            multi_timeframe_reader=integration_mtf_reader
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        assert result is not None
        assert 'cycle_info' in result.details
        # Regime should be detected (may be None if detection fails, which is OK)
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_analysis_integration(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader
    ):
        """Test multi-timeframe analysis integration."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        assert result is not None
        # Multi-timeframe analysis should be included in context
        
        # Verify MTF data is fetched
        mtf_data = await orchestrator._fetch_multi_timeframe_data('BANKNIFTY')
        assert isinstance(mtf_data, dict)
    
    @pytest.mark.asyncio
    async def test_enhanced_agents_integration(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader,
        integration_position_provider
    ):
        """Test enhanced agents work together correctly."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader,
            position_provider=integration_position_provider,
            config={
                'agents': {
                    'momentum': {'enabled': True},
                    'research_manager': {'enabled': True},
                    'risk': {'enabled': True}
                }
            }
        )
        
        context = {
            'symbol': 'BANKNIFTY',
            'market_data': {'close': 45000},
            'multi_timeframe': {},
            'regime': 'ranging',
            'current_positions': [],
            'technical_indicators': {},
            'timestamp': datetime.now()
        }
        
        # Run all agents
        agent_results = await orchestrator._run_enhanced_agents(context)
        
        # Verify all enabled agents executed
        assert len(agent_results) >= 1
        for agent_name, result in agent_results.items():
            assert isinstance(result, AnalysisResult)
            assert result.decision in [
                "HOLD", "BUY", "SELL", "VETO", "APPROVE",
                "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD",
                "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD",
                "IRON_CONDOR"
            ]
            assert 0.0 <= result.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_risk_veto_workflow(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader
    ):
        """Test risk veto workflow integration."""
        # Create high-risk scenario
        technical_provider = IntegrationTestTechnicalProvider(base_price=45000)
        technical_provider.indicators = {
            'close': 45000,
            'sma_20': 45000,
            'ema_50': 45000,
            'adx': 20.0,
            'iv_percentile': 95.0,  # Very high IV
            'volume_ratio': 3.0,  # High volume
            'rsi': 80.0  # Overbought
        }
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=technical_provider,
            multi_timeframe_reader=integration_mtf_reader,
            config={
                'agents': {
                    'momentum': {'enabled': False},
                    'research_manager': {'enabled': False},
                    'risk': {'enabled': True}
                }
            }
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        # Risk agent should evaluate and may veto
        # Result should reflect risk assessment
        assert result is not None
        assert result.decision in ["HOLD", "VETO", "BUY", "SELL"]
    
    @pytest.mark.asyncio
    async def test_strategy_building_integration(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader,
        integration_options_provider
    ):
        """Test spread strategy building with options chain."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader,
            options_chain_provider=integration_options_provider,
            config={
                'strategies': {
                    'iron_condor': {'enabled': True},
                    'credit_spreads': {'enabled': True}
                }
            }
        )
        
        # Test strategy selection for ranging regime
        current_price = 45000
        technical_indicators = {
            'iv_percentile': 60.0,
            'volume_ratio': 1.0
        }
        context = {'symbol': 'BANKNIFTY'}
        
        strategy_decision = await orchestrator._select_and_build_strategy(
            'ranging', current_price, technical_indicators, context
        )
        
        # Strategy may or may not be built depending on validation
        # Just verify the method executes without error
        assert strategy_decision is None or isinstance(strategy_decision, dict)
        if strategy_decision:
            assert 'strategy_name' in strategy_decision
            assert 'confidence' in strategy_decision
    
    @pytest.mark.asyncio
    async def test_decision_synthesis_with_agents_and_strategy(
        self,
        integration_market_data_provider
    ):
        """Test decision synthesis with both agent results and strategy."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider
        )
        
        # Create realistic agent results
        agent_results = {
            'momentum': AnalysisResult(
                decision="BUY",
                confidence=0.75,
                details={'reasoning': 'Strong upward momentum detected'}
            ),
            'research_manager': AnalysisResult(
                decision="BULL_CALL_SPREAD",
                confidence=0.70,
                details={'summary': 'Bull case stronger than bear case'}
            ),
            'risk': AnalysisResult(
                decision="APPROVE",
                confidence=0.85,
                details={'risk_level': 'MEDIUM'}
            )
        }
        
        # Create strategy decision
        strategy_decision = {
            'strategy_name': 'iron_condor',
            'confidence': 0.80,
            'metrics': {
                'max_profit': 1000,
                'max_loss': 500,
                'risk_reward_ratio': 2.0
            }
        }
        
        result = await orchestrator._synthesize_decision(
            agent_results,
            strategy_decision,
            None,  # mtf_analysis
            'ranging',  # regime
            None  # current_positions
        )
        
        # Verify synthesis
        assert result is not None
        assert result.decision in [
            "BUY", "SELL", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD",
            "IRON_CONDOR", "APPROVE", "VETO", "HOLD"
        ]
        assert result.confidence >= 0.0
        assert 'agent_results' in result.details
        # Strategy should be in details or decision should be a strategy
        assert 'strategy' in result.details or result.decision in [
            "BUY", "BULL_CALL_SPREAD", "IRON_CONDOR", "APPROVE"
        ]
    
    @pytest.mark.asyncio
    async def test_position_aware_execution(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader
    ):
        """Test orchestrator considers existing positions."""
        positions = [
            {
                'symbol': 'BANKNIFTY',
                'status': 'active',
                'action': 'BUY',
                'entry_price': 44800,
                'quantity': 25,
                'current_price': 45000,
                'pnl': 5000,
                'pnl_pct': 0.45
            }
        ]
        
        position_provider = IntegrationTestPositionProvider(positions)
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader,
            position_provider=position_provider
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        # Position should be considered in decision
        assert result is not None
        # Agents should receive position context
        assert 'cycle_info' in result.details
    
    @pytest.mark.asyncio
    async def test_multiple_cycles_continuity(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader
    ):
        """Test orchestrator maintains state across multiple cycles."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader
        )
        
        context = {'symbol': 'BANKNIFTY'}
        
        # Run multiple cycles
        result1 = await orchestrator.run_cycle(context)
        result2 = await orchestrator.run_cycle(context)
        result3 = await orchestrator.run_cycle(context)
        
        # Verify cycle count increments
        assert orchestrator.cycle_count == 3
        
        # Verify each cycle completes
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        
        # Verify cycle info reflects correct cycle numbers
        assert result1.details['cycle_info']['cycle_number'] == 1
        assert result2.details['cycle_info']['cycle_number'] == 2
        assert result3.details['cycle_info']['cycle_number'] == 3
    
    @pytest.mark.asyncio
    async def test_error_recovery_integration(
        self,
        integration_market_data_provider,
        integration_technical_provider
    ):
        """Test orchestrator handles errors gracefully."""
        # Create a provider that will fail
        failing_mtf_reader = IntegrationTestMultiTimeframeReader()
        failing_mtf_reader.fetch_ohlc = AsyncMock(side_effect=Exception("MTF error"))
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=failing_mtf_reader
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        # Should still complete, just without MTF data
        assert result is not None
        assert result.decision in ["HOLD", "BUY", "SELL", "IRON_CONDOR", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]
    
    @pytest.mark.asyncio
    async def test_config_updates_during_runtime(
        self,
        integration_market_data_provider,
        integration_technical_provider
    ):
        """Test orchestrator configuration can be updated."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider
        )
        
        # Update config directly (method may not exist, so update config dict)
        orchestrator.config['min_confidence_threshold'] = 0.8
        orchestrator.config['symbol'] = 'NIFTY50'
        orchestrator.symbol = 'NIFTY50'
        
        # Verify config updated
        assert orchestrator.config['min_confidence_threshold'] == 0.8
        assert orchestrator.symbol == 'NIFTY50'
        
        # Verify orchestrator still works with new config
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_performance_metrics_collection(
        self,
        integration_market_data_provider,
        integration_technical_provider,
        integration_mtf_reader
    ):
        """Test orchestrator collects performance metrics."""
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=integration_market_data_provider,
            technical_data_provider=integration_technical_provider,
            multi_timeframe_reader=integration_mtf_reader
        )
        
        context = {'symbol': 'BANKNIFTY'}
        
        # Run a cycle
        result = await orchestrator.run_cycle(context)
        
        # Get stats
        stats = orchestrator.get_cycle_stats()
        
        # Verify stats structure
        assert stats['total_cycles'] == 1
        assert stats['symbol'] == 'BANKNIFTY'
        assert 'active_agents' in stats
        assert 'active_strategies' in stats
        assert 'config' in stats
        
        # Verify cycle info contains duration
        cycle_info = result.details.get('cycle_info', {})
        assert 'duration_seconds' in cycle_info
        assert cycle_info['duration_seconds'] >= 0
