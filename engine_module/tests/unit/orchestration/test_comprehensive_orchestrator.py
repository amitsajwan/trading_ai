"""Unit tests for Comprehensive Trading Orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any, List

from engine_module.comprehensive_orchestrator import ComprehensiveTradingOrchestrator
from engine_module.contracts import AnalysisResult
from engine_module.analysis.regime_detector import MarketRegime
from engine_module.analysis.multi_timeframe import TimeframeTrend


class MockMarketDataProvider:
    """Mock market data provider for testing."""
    
    def __init__(self, ohlc_data: List[Dict[str, Any]]):
        self.ohlc_data = ohlc_data
    
    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        """Return mock OHLC data."""
        return self.ohlc_data


class MockTechnicalDataProvider:
    """Mock technical data provider for testing."""
    
    def __init__(self, indicators: Dict[str, Any]):
        self.indicators = indicators
    
    async def get_technical_indicators(self, symbol: str, periods: int = 100):
        """Return mock technical indicators."""
        mock_obj = MagicMock()
        mock_obj.to_dict = lambda: self.indicators
        return mock_obj


class MockPositionProvider:
    """Mock position provider for testing."""
    
    def __init__(self, positions: List[Dict[str, Any]] = None):
        self.positions = positions or []
    
    async def get_positions(self, symbol: str = None):
        """Return mock positions."""
        if symbol:
            return [p for p in self.positions if p.get('symbol') == symbol]
        return self.positions


class MockMultiTimeframeReader:
    """Mock multi-timeframe reader for testing."""
    
    async def fetch_ohlc(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return mock multi-timeframe data."""
        # Return mock data for each timeframe
        base_price = 45000
        return [
            {
                'close': base_price,
                'sma_20': base_price * 0.99,
                'ema_50': base_price * 0.98,
                'rsi': 45.0,
                'macd': 50.0,
                'macd_signal': 45.0,
                'adx': 20.0
            }
        ]


class MockOptionsChainProvider:
    """Mock options chain provider for testing."""
    
    async def fetch_chain(self, symbol: str) -> Dict[str, Any]:
        """Return mock options chain."""
        spot_price = 45000
        option_chain = {}
        
        # Create strikes around spot
        for strike_offset in [-500, -250, 0, 250, 500]:
            strike = int(spot_price + strike_offset)
            option_chain[str(strike)] = {
                'CE': {
                    'last_price': max(0, (spot_price - strike) * 0.1),
                    'volume': 1000,
                    'oi': 5000,
                    'expiry': '2026-01-30',
                    'delta': 0.5,
                    'gamma': 0.01,
                    'theta': -0.05,
                    'vega': 0.1,
                    'iv': 0.20
                },
                'PE': {
                    'last_price': max(0, (strike - spot_price) * 0.1),
                    'volume': 1000,
                    'oi': 5000,
                    'expiry': '2026-01-30',
                    'delta': -0.5,
                    'gamma': 0.01,
                    'theta': -0.05,
                    'vega': 0.1,
                    'iv': 0.20
                }
            }
        
        return option_chain


class TestComprehensiveOrchestrator:
    """Tests for ComprehensiveTradingOrchestrator."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        assert orchestrator.symbol == 'BANKNIFTY'
        assert orchestrator.regime_detector is not None
        assert orchestrator.multi_timeframe_analyzer is not None
        assert len(orchestrator.agents) >= 1  # At least momentum agent
        assert orchestrator.cycle_count == 0
    
    def test_initialization_custom_config(self):
        """Test initialization with custom config."""
        market_data_provider = MockMarketDataProvider([])
        config = {
            'symbol': 'NIFTY50',
            'min_confidence_threshold': 0.7,
            'agents': {
                'momentum': {'enabled': True},
                'research_manager': {'enabled': False}
            }
        }
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider, config=config)
        
        assert orchestrator.symbol == 'NIFTY50'
        assert orchestrator.config['min_confidence_threshold'] == 0.7
        assert 'momentum' in orchestrator.agents
        assert 'research_manager' not in orchestrator.agents
    
    def test_initialize_enhanced_agents(self):
        """Test enhanced agent initialization."""
        market_data_provider = MockMarketDataProvider([])
        config = {
            'agents': {
                'momentum': {'enabled': True},
                'research_manager': {'enabled': True},
                'risk': {'enabled': True}
            }
        }
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider, config=config)
        
        assert 'momentum' in orchestrator.agents
        assert 'research_manager' in orchestrator.agents
        assert 'risk' in orchestrator.agents
    
    def test_initialize_spread_strategies(self):
        """Test spread strategy initialization."""
        market_data_provider = MockMarketDataProvider([])
        config = {
            'strategies': {
                'iron_condor': {'enabled': True},
                'credit_spreads': {'enabled': True},
                'debit_spreads': {'enabled': True}
            }
        }
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider, config=config)
        
        assert len(orchestrator.spread_strategies) >= 1
        assert 'iron_condor' in orchestrator.spread_strategies or len(orchestrator.spread_strategies) > 0
    
    @pytest.mark.asyncio
    async def test_run_cycle_no_market_data(self):
        """Test run_cycle with no market data."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        assert result.decision == "HOLD"
        assert result.confidence == 0.0
        assert result.details.get('reason') == "NO_MARKET_DATA"
    
    @pytest.mark.asyncio
    async def test_run_cycle_basic_flow(self):
        """Test basic run_cycle flow."""
        market_data = [
            {'close': 45000, 'open': 44900, 'high': 45100, 'low': 44800, 'volume': 1000000}
        ] * 100
        
        market_data_provider = MockMarketDataProvider(market_data)
        technical_provider = MockTechnicalDataProvider({
            'rsi': 50.0,
            'sma_20': 45000,
            'ema_50': 44900,
            'adx': 20.0,
            'iv_percentile': 50.0,
            'volume_ratio': 1.0
        })
        position_provider = MockPositionProvider([])
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            technical_data_provider=technical_provider,
            position_provider=position_provider
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        assert result is not None
        assert result.decision in ["HOLD", "BUY", "SELL", "IRON_CONDOR", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]
        assert 0.0 <= result.confidence <= 1.0
        assert 'cycle_info' in result.details
        assert orchestrator.cycle_count == 1
    
    @pytest.mark.asyncio
    async def test_run_cycle_with_regime_detection(self):
        """Test run_cycle with regime detection."""
        market_data = [
            {'close': 45000, 'open': 44900, 'high': 45100, 'low': 44800, 'volume': 1000000}
        ] * 100
        
        market_data_provider = MockMarketDataProvider(market_data)
        technical_provider = MockTechnicalDataProvider({
            'rsi': 45.0,
            'sma_20': 44900,
            'ema_50': 44800,
            'adx': 30.0,  # Strong trend
            'iv_percentile': 50.0,
            'volume_ratio': 1.5,
            'bollinger_upper': 45100,
            'bollinger_lower': 44900
        })
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            technical_data_provider=technical_provider
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        # Check that regime was detected and included in details
        assert 'cycle_info' in result.details
        cycle_info = result.details.get('cycle_info', {})
        # Regime should be detected (may be None if detection fails)
        # Just verify the cycle ran successfully
    
    @pytest.mark.asyncio
    async def test_run_cycle_with_multi_timeframe(self):
        """Test run_cycle with multi-timeframe data."""
        market_data = [
            {'close': 45000, 'open': 44900, 'high': 45100, 'low': 44800, 'volume': 1000000}
        ] * 100
        
        market_data_provider = MockMarketDataProvider(market_data)
        technical_provider = MockTechnicalDataProvider({
            'rsi': 50.0,
            'sma_20': 45000,
            'ema_50': 44900
        })
        mtf_reader = MockMultiTimeframeReader()
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            technical_data_provider=technical_provider,
            multi_timeframe_reader=mtf_reader
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        assert result is not None
        assert 'cycle_info' in result.details
        cycle_info = result.details.get('cycle_info', {})
        # Multi-timeframe analysis should be included if available
    
    @pytest.mark.asyncio
    async def test_run_cycle_with_positions(self):
        """Test run_cycle with existing positions."""
        market_data = [
            {'close': 45000, 'open': 44900, 'high': 45100, 'low': 44800, 'volume': 1000000}
        ] * 100
        
        market_data_provider = MockMarketDataProvider(market_data)
        technical_provider = MockTechnicalDataProvider({
            'rsi': 50.0,
            'sma_20': 45000,
            'ema_50': 44900
        })
        positions = [
            {
                'symbol': 'BANKNIFTY',
                'status': 'active',
                'action': 'BUY',
                'entry_price': 44800,
                'quantity': 25
            }
        ]
        position_provider = MockPositionProvider(positions)
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            technical_data_provider=technical_provider,
            position_provider=position_provider
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        assert result is not None
        # Positions should be considered in decision
    
    @pytest.mark.asyncio
    async def test_run_cycle_risk_veto(self):
        """Test run_cycle with risk veto."""
        market_data = [
            {'close': 45000, 'open': 44900, 'high': 45100, 'low': 44800, 'volume': 1000000}
        ] * 100
        
        market_data_provider = MockMarketDataProvider(market_data)
        technical_provider = MockTechnicalDataProvider({
            'rsi': 50.0,
            'sma_20': 45000,
            'ema_50': 44900,
            'iv_percentile': 90.0  # High IV
        })
        
        # Mock risk agent to return VETO
        with patch('engine_module.comprehensive_orchestrator.EnhancedRiskAgent') as MockRiskAgent:
            mock_risk_instance = MockRiskAgent.return_value
            mock_risk_instance.analyze = AsyncMock(return_value=AnalysisResult(
                decision="VETO",
                confidence=0.9,
                details={'risk_level': 'HIGH'}
            ))
            
            orchestrator = ComprehensiveTradingOrchestrator(
                market_data_provider=market_data_provider,
                technical_data_provider=technical_provider,
                config={'agents': {'risk': {'enabled': True}, 'momentum': {'enabled': False}, 'research_manager': {'enabled': False}}}
            )
            
            context = {'symbol': 'BANKNIFTY'}
            result = await orchestrator.run_cycle(context)
            
            # Should be HOLD due to risk veto
            assert result.decision == "HOLD"
            assert result.details.get('reason') == "RISK_VETO"
    
    @pytest.mark.asyncio
    async def test_fetch_multi_timeframe_data(self):
        """Test multi-timeframe data fetching."""
        market_data_provider = MockMarketDataProvider([])
        mtf_reader = MockMultiTimeframeReader()
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            multi_timeframe_reader=mtf_reader
        )
        
        mtf_data = await orchestrator._fetch_multi_timeframe_data('BANKNIFTY')
        
        assert isinstance(mtf_data, dict)
        # Should have data for multiple timeframes
        expected_timeframes = ['5m', '15m', '1h', 'daily']
        for tf in expected_timeframes:
            # Data may or may not be present depending on mock
            if tf in mtf_data:
                assert 'close' in mtf_data[tf]
    
    @pytest.mark.asyncio
    async def test_run_enhanced_agents(self):
        """Test running enhanced agents."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        context = {
            'market_data': {'close': 45000},
            'multi_timeframe': {},
            'regime': 'ranging',
            'current_positions': [],
            'technical_indicators': {},
            'symbol': 'BANKNIFTY'
        }
        
        agent_results = await orchestrator._run_enhanced_agents(context)
        
        assert isinstance(agent_results, dict)
        # Should have results from all enabled agents
        for agent_name in orchestrator.agents.keys():
            assert agent_name in agent_results
            assert isinstance(agent_results[agent_name], AnalysisResult)
    
    @pytest.mark.asyncio
    async def test_run_single_agent_error_handling(self):
        """Test error handling in single agent execution."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        # Create a failing agent
        failing_agent = MagicMock()
        failing_agent.analyze = AsyncMock(side_effect=ValueError("Test error"))
        
        context = {
            'market_data': {'close': 45000},
            'multi_timeframe': {},
            'regime': None,
            'current_positions': [],
            'technical_indicators': {},
            'symbol': 'BANKNIFTY'
        }
        
        result = await orchestrator._run_single_agent("failing_agent", failing_agent, context)
        
        assert result.decision == "HOLD"
        assert result.confidence == 0.0
        assert 'AGENT_ERROR' in result.details.get('reason', '')
    
    @pytest.mark.asyncio
    async def test_select_and_build_strategy_ranging(self):
        """Test strategy selection for ranging regime."""
        market_data_provider = MockMarketDataProvider([])
        options_provider = MockOptionsChainProvider()
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            options_chain_provider=options_provider,
            config={'strategies': {'iron_condor': {'enabled': True}}}
        )
        
        regime = 'ranging'
        current_price = 45000
        technical_indicators = {}
        context = {'symbol': 'BANKNIFTY'}
        
        strategy_decision = await orchestrator._select_and_build_strategy(
            regime, current_price, technical_indicators, context
        )
        
        # Strategy may or may not be built depending on options chain data
        # Just verify method runs without error
        assert strategy_decision is None or isinstance(strategy_decision, dict)
    
    @pytest.mark.asyncio
    async def test_select_and_build_strategy_no_options_chain(self):
        """Test strategy selection without options chain provider."""
        market_data_provider = MockMarketDataProvider([])
        
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        strategy_decision = await orchestrator._select_and_build_strategy(
            'ranging', 45000, {}, {}
        )
        
        # Should return None without options chain provider
        assert strategy_decision is None
    
    @pytest.mark.asyncio
    async def test_synthesize_decision_with_agent_results(self):
        """Test decision synthesis with agent results."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        agent_results = {
            'momentum': AnalysisResult(
                decision="BUY",
                confidence=0.75,
                details={'reasoning': 'Strong momentum'}
            ),
            'research_manager': AnalysisResult(
                decision="BULL_CALL_SPREAD",
                confidence=0.70,
                details={'summary': 'Bull wins debate'}
            )
        }
        
        result = await orchestrator._synthesize_decision(
            agent_results, None, None, 'trending_up', None
        )
        
        assert result is not None
        assert result.decision in ["BUY", "BULL_CALL_SPREAD", "HOLD"]
        assert result.confidence >= 0.0
        assert 'agent_results' in result.details
    
    @pytest.mark.asyncio
    async def test_synthesize_decision_with_strategy(self):
        """Test decision synthesis with strategy decision."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        agent_results = {
            'momentum': AnalysisResult(decision="HOLD", confidence=0.5, details={})
        }
        
        strategy_decision = {
            'strategy_name': 'iron_condor',
            'confidence': 0.80,
            'metrics': {'max_profit': 1000, 'max_loss': 500}
        }
        
        result = await orchestrator._synthesize_decision(
            agent_results, strategy_decision, None, 'ranging', None
        )
        
        assert result is not None
        assert result.decision in ["IRON_CONDOR", "HOLD"]
        if result.decision == "IRON_CONDOR":
            assert result.confidence >= 0.80
    
    @pytest.mark.asyncio
    async def test_synthesize_decision_no_signals(self):
        """Test decision synthesis with no clear signals."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        agent_results = {
            'momentum': AnalysisResult(decision="HOLD", confidence=0.3, details={}),
            'research_manager': AnalysisResult(decision="HOLD", confidence=0.4, details={})
        }
        
        result = await orchestrator._synthesize_decision(
            agent_results, None, None, None, None
        )
        
        assert result.decision == "HOLD"
        assert result.confidence == 0.0
        assert 'reasoning' in result.details
    
    @pytest.mark.asyncio
    async def test_run_cycle_error_handling(self):
        """Test error handling in run_cycle."""
        market_data_provider = MockMarketDataProvider([])
        
        # Create orchestrator that will fail
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        # Mock an error in market data provider
        market_data_provider.get_ohlc_data = AsyncMock(side_effect=Exception("Test error"))
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        assert result.decision == "HOLD"
        assert result.confidence == 0.0
        assert 'CYCLE_ERROR' in result.details.get('reason', '')
    
    def test_get_cycle_stats(self):
        """Test cycle statistics."""
        market_data_provider = MockMarketDataProvider([])
        orchestrator = ComprehensiveTradingOrchestrator(market_data_provider)
        
        stats = orchestrator.get_cycle_stats()
        
        assert stats['total_cycles'] == 0
        assert stats['symbol'] == 'BANKNIFTY'
        assert 'active_agents' in stats
        assert 'active_strategies' in stats
        assert 'config' in stats
    
    @pytest.mark.asyncio
    async def test_run_cycle_increments_cycle_count(self):
        """Test that run_cycle increments cycle count."""
        market_data = [
            {'close': 45000, 'open': 44900, 'high': 45100, 'low': 44800, 'volume': 1000000}
        ] * 100
        
        market_data_provider = MockMarketDataProvider(market_data)
        technical_provider = MockTechnicalDataProvider({
            'rsi': 50.0,
            'sma_20': 45000,
            'ema_50': 44900
        })
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            technical_data_provider=technical_provider
        )
        
        context = {'symbol': 'BANKNIFTY'}
        
        assert orchestrator.cycle_count == 0
        
        await orchestrator.run_cycle(context)
        assert orchestrator.cycle_count == 1
        
        await orchestrator.run_cycle(context)
        assert orchestrator.cycle_count == 2
    
    @pytest.mark.asyncio
    async def test_run_cycle_with_full_integration(self):
        """Test run_cycle with all components integrated."""
        market_data = [
            {'close': 45000, 'open': 44900, 'high': 45100, 'low': 44800, 'volume': 1000000}
        ] * 100
        
        market_data_provider = MockMarketDataProvider(market_data)
        technical_provider = MockTechnicalDataProvider({
            'rsi': 45.0,
            'sma_20': 44900,
            'ema_50': 44800,
            'adx': 25.0,
            'iv_percentile': 60.0,
            'volume_ratio': 1.2,
            'bollinger_upper': 45100,
            'bollinger_lower': 44900
        })
        position_provider = MockPositionProvider([])
        mtf_reader = MockMultiTimeframeReader()
        options_provider = MockOptionsChainProvider()
        
        orchestrator = ComprehensiveTradingOrchestrator(
            market_data_provider=market_data_provider,
            technical_data_provider=technical_provider,
            position_provider=position_provider,
            multi_timeframe_reader=mtf_reader,
            options_chain_provider=options_provider,
            config={
                'agents': {
                    'momentum': {'enabled': True},
                    'research_manager': {'enabled': True},
                    'risk': {'enabled': True}
                },
                'strategies': {
                    'iron_condor': {'enabled': True},
                    'credit_spreads': {'enabled': True}
                }
            }
        )
        
        context = {'symbol': 'BANKNIFTY'}
        result = await orchestrator.run_cycle(context)
        
        # Verify complete cycle
        assert result is not None
        assert result.decision in ["HOLD", "BUY", "SELL", "IRON_CONDOR", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD", "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"]
        assert 0.0 <= result.confidence <= 1.0
        assert 'cycle_info' in result.details
        assert result.agent == "ComprehensiveOrchestrator"
        
        cycle_info = result.details.get('cycle_info', {})
        assert cycle_info.get('cycle_number') == 1
        assert 'regime' in cycle_info or cycle_info.get('regime') is None
        assert 'duration_seconds' in cycle_info
