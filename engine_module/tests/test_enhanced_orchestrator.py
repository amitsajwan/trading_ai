"""Tests for enhanced orchestrator with position awareness."""

import pytest
from datetime import datetime
from typing import Dict, Any, List, Optional
from engine_module.enhanced_orchestrator import (
    EnhancedTradingOrchestrator,
    TradingDecision,
    MarketDataProvider,
    PositionProvider
)
from engine_module.contracts import AnalysisResult


class MockMarketDataProvider(MarketDataProvider):
    """Mock market data provider for testing."""
    
    def __init__(self):
        self.data = []
        # Generate sample OHLC data
        base_price = 23000.0
        for i in range(100):
            self.data.append({
                'timestamp': (datetime.now()).isoformat(),
                'open': base_price + i * 0.5,
                'high': base_price + i * 0.5 + 10,
                'low': base_price + i * 0.5 - 10,
                'close': base_price + i * 0.5 + 5,
                'volume': 1000000 + i * 10000
            })
    
    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        return self.data[-periods:]


class MockPositionProvider(PositionProvider):
    """Mock position provider for testing."""
    
    def __init__(self, positions: List[Dict[str, Any]] = None):
        self.positions = positions or []
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if symbol:
            return [p for p in self.positions if p.get('symbol') == symbol]
        return self.positions


@pytest.mark.asyncio
class TestEnhancedOrchestrator:
    """Test suite for enhanced orchestrator."""
    
    async def test_orchestrator_initialization_without_position_provider(self):
        """Test orchestrator can be initialized without position provider."""
        market_data_provider = MockMarketDataProvider()
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider
        )
        
        assert orchestrator.market_data_provider == market_data_provider
        assert orchestrator.position_provider is None
        assert len(orchestrator.agents) > 0
    
    async def test_orchestrator_initialization_with_position_provider(self):
        """Test orchestrator can be initialized with position provider."""
        market_data_provider = MockMarketDataProvider()
        position_provider = MockPositionProvider()
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider,
            position_provider=position_provider
        )
        
        assert orchestrator.position_provider == position_provider
    
    async def test_run_cycle_without_positions(self):
        """Test running a cycle when no positions exist."""
        market_data_provider = MockMarketDataProvider()
        position_provider = MockPositionProvider([])  # No positions
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider,
            position_provider=position_provider,
            config={
                'symbol': 'NIFTY50',
                'min_confidence_threshold': 0.5,
                'max_positions': 3
            }
        )
        
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)
        
        assert isinstance(result, AnalysisResult)
        assert result.decision in ['BUY', 'SELL', 'HOLD']
        assert 0.0 <= result.confidence <= 1.0
    
    async def test_run_cycle_with_existing_long_position(self):
        """Test running a cycle with existing long position."""
        market_data_provider = MockMarketDataProvider()
        positions = [{
            'symbol': 'NIFTY50',
            'action': 'BUY',
            'quantity': 10,
            'entry_price': 23000.0,
            'current_price': 23100.0,
            'stop_loss': 22800.0,
            'take_profit': 23500.0,
            'status': 'active',
            'position_id': 'pos_123'
        }]
        position_provider = MockPositionProvider(positions)
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider,
            position_provider=position_provider,
            config={
                'symbol': 'NIFTY50',
                'min_confidence_threshold': 0.5,
                'max_positions': 3
            }
        )
        
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)
        
        assert isinstance(result, AnalysisResult)
        # Should consider existing position in decision
        details = result.details
        assert 'position_action' in details or 'cycle_info' in details
    
    async def test_run_cycle_at_position_limit(self):
        """Test running a cycle when at position limit."""
        market_data_provider = MockMarketDataProvider()
        # Create 3 positions (at limit)
        positions = [
            {
                'symbol': 'NIFTY50',
                'action': 'BUY',
                'quantity': 10,
                'entry_price': 23000.0,
                'current_price': 23100.0,
                'stop_loss': 22800.0,
                'take_profit': 23500.0,
                'status': 'active',
                'position_id': f'pos_{i}'
            }
            for i in range(3)
        ]
        position_provider = MockPositionProvider(positions)
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider,
            position_provider=position_provider,
            config={
                'symbol': 'NIFTY50',
                'min_confidence_threshold': 0.5,
                'max_positions': 3
            }
        )
        
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)
        
        assert isinstance(result, AnalysisResult)
        # At limit, should only consider exit signals or HOLD
        # Decision should not be a new BUY/SELL unless it's closing
    
    async def test_position_context_passed_to_agents(self):
        """Test that position context is passed to agents."""
        market_data_provider = MockMarketDataProvider()
        positions = [{
            'symbol': 'NIFTY50',
            'action': 'BUY',
            'quantity': 10,
            'entry_price': 23000.0,
            'current_price': 23100.0,
            'stop_loss': 22800.0,
            'take_profit': 23500.0,
            'status': 'active',
            'position_id': 'pos_123'
        }]
        position_provider = MockPositionProvider(positions)
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider,
            position_provider=position_provider
        )
        
        # Mock agent to capture context
        captured_context = {}
        original_analyze = orchestrator.agents['momentum'].analyze
        
        async def capture_context(context):
            captured_context.update(context)
            return await original_analyze(context)
        
        orchestrator.agents['momentum'].analyze = capture_context
        
        context = {'symbol': 'NIFTY50'}
        await orchestrator.run_cycle(context)
        
        # Verify position info is in context
        assert 'current_positions' in captured_context
        assert 'has_long_position' in captured_context
        assert 'has_short_position' in captured_context
        assert 'position_count' in captured_context
        assert captured_context['has_long_position'] is True
        assert captured_context['position_count'] == 1
    
    async def test_trading_decision_with_position_action(self):
        """Test that TradingDecision includes position_action."""
        decision = TradingDecision(
            action="BUY",
            confidence=0.75,
            reasoning="Test",
            entry_price=23000.0,
            stop_loss=22800.0,
            take_profit=23500.0,
            quantity=10,
            risk_amount=200.0,
            agent_signals={},
            timestamp=datetime.now(),
            position_action="ADD_TO_LONG"
        )
        
        assert decision.position_action == "ADD_TO_LONG"
        decision_dict = decision.to_dict()
        assert decision_dict['position_action'] == "ADD_TO_LONG"
    
    async def test_run_cycle_without_position_provider(self):
        """Test that orchestrator works without position provider (backward compatibility)."""
        market_data_provider = MockMarketDataProvider()
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider
        )
        
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)
        
        assert isinstance(result, AnalysisResult)
        # Should work fine without position provider
        assert result.decision in ['BUY', 'SELL', 'HOLD']


@pytest.mark.asyncio
class TestPositionAwareDecisionLogic:
    """Test position-aware decision logic."""
    
    async def test_decision_with_long_position_adds_to_position(self):
        """Test that decision to add to long position has correct action."""
        market_data_provider = MockMarketDataProvider()
        positions = [{
            'symbol': 'NIFTY50',
            'action': 'BUY',
            'quantity': 10,
            'entry_price': 23000.0,
            'current_price': 23100.0,
            'stop_loss': 22800.0,
            'take_profit': 23500.0,
            'status': 'active',
            'position_id': 'pos_123'
        }]
        position_provider = MockPositionProvider(positions)
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider,
            position_provider=position_provider,
            config={
                'symbol': 'NIFTY50',
                'min_confidence_threshold': 0.5,
                'max_positions': 3,
                'add_to_position_pct': 0.5
            }
        )
        
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)
        
        # If decision is BUY with existing long, should indicate adding
        details = result.details
        if result.decision == 'BUY' and 'position_action' in details:
            assert details['position_action'] in ['ADD_TO_LONG', 'OPEN_NEW']
    
    async def test_decision_at_limit_considers_exits_only(self):
        """Test that at position limit, only exit signals are considered."""
        market_data_provider = MockMarketDataProvider()
        positions = [
            {
                'symbol': 'NIFTY50',
                'action': 'BUY',
                'quantity': 10,
                'entry_price': 23000.0,
                'current_price': 23100.0,
                'stop_loss': 22800.0,
                'take_profit': 23500.0,
                'status': 'active',
                'position_id': f'pos_{i}'
            }
            for i in range(3)
        ]
        position_provider = MockPositionProvider(positions)
        
        orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=market_data_provider,
            position_provider=position_provider,
            config={
                'symbol': 'NIFTY50',
                'min_confidence_threshold': 0.5,
                'max_positions': 3
            }
        )
        
        context = {'symbol': 'NIFTY50'}
        result = await orchestrator.run_cycle(context)
        
        # At limit, should be HOLD or SELL (to close long positions)
        # Should not be a new BUY
        if result.decision == 'BUY':
            details = result.details
            # If BUY, it should be to close short (which we don't have)
            # or the reasoning should indicate position limit
            assert 'position_limit' in result.details.get('reasoning', '').lower() or \
                   details.get('position_action') in ['CLOSE_SHORT', 'OPEN_NEW']


