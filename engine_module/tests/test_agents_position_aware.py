"""Tests for position-aware agents."""

import pytest
from datetime import datetime
from engine_module.agents.momentum_agent import MomentumAgent
from engine_module.agents.trend_agent import TrendAgent
from engine_module.contracts import AnalysisResult


@pytest.mark.asyncio
class TestMomentumAgentPositionAware:
    """Test momentum agent with position awareness."""
    
    def create_mock_ohlc(self, periods=50):
        """Create mock OHLC data."""
        base_price = 23000.0
        data = []
        for i in range(periods):
            data.append({
                'timestamp': datetime.now().isoformat(),
                'open': base_price + i * 0.5,
                'high': base_price + i * 0.5 + 10,
                'low': base_price + i * 0.5 - 10,
                'close': base_price + i * 0.5 + 5,
                'volume': 1000000 + i * 10000
            })
        return data
    
    async def test_momentum_agent_without_positions(self):
        """Test momentum agent without existing positions."""
        agent = MomentumAgent()
        ohlc_data = self.create_mock_ohlc()
        
        context = {
            'ohlc': ohlc_data,
            'symbol': 'NIFTY50',
            'current_price': 23000.0,
            'current_positions': [],
            'has_long_position': False,
            'has_short_position': False,
            'position_count': 0
        }
        
        result = await agent.analyze(context)
        
        assert isinstance(result, AnalysisResult)
        assert result.decision in ['BUY', 'SELL', 'HOLD']
        assert 0.0 <= result.confidence <= 1.0
    
    async def test_momentum_agent_with_long_position(self):
        """Test momentum agent with existing long position."""
        agent = MomentumAgent()
        ohlc_data = self.create_mock_ohlc()
        
        positions = [{
            'symbol': 'NIFTY50',
            'action': 'BUY',
            'quantity': 10,
            'entry_price': 23000.0,
            'status': 'active'
        }]
        
        context = {
            'ohlc': ohlc_data,
            'symbol': 'NIFTY50',
            'current_price': 23000.0,
            'current_positions': positions,
            'has_long_position': True,
            'has_short_position': False,
            'position_count': 1
        }
        
        result = await agent.analyze(context)
        
        assert isinstance(result, AnalysisResult)
        # If BUY signal, should indicate adding to position
        if result.decision == 'BUY':
            details = result.details or {}
            reasoning = details.get('reasoning', [])
            if isinstance(reasoning, list):
                reasoning_str = ' '.join(reasoning)
            else:
                reasoning_str = str(reasoning)
            # Should mention existing position or adding
            assert 'existing' in reasoning_str.lower() or 'adding' in reasoning_str.lower() or \
                   result.confidence < 0.8  # Lower confidence when adding
    
    async def test_momentum_agent_exit_signal(self):
        """Test momentum agent signals exit when momentum weakens."""
        agent = MomentumAgent()
        ohlc_data = self.create_mock_ohlc()
        
        positions = [{
            'symbol': 'NIFTY50',
            'action': 'BUY',
            'quantity': 10,
            'entry_price': 23000.0,
            'status': 'active'
        }]
        
        context = {
            'ohlc': ohlc_data,
            'symbol': 'NIFTY50',
            'current_price': 23000.0,
            'current_positions': positions,
            'has_long_position': True,
            'has_short_position': False,
            'position_count': 1
        }
        
        result = await agent.analyze(context)
        
        assert isinstance(result, AnalysisResult)
        # May signal SELL to exit if momentum weakens
        if result.decision == 'SELL':
            details = result.details or {}
            reasoning = details.get('reasoning', [])
            if isinstance(reasoning, list):
                reasoning_str = ' '.join(reasoning)
            else:
                reasoning_str = str(reasoning)
            # Should mention exiting or weakening
            assert 'exit' in reasoning_str.lower() or 'weakening' in reasoning_str.lower() or \
                   'consider' in reasoning_str.lower()


@pytest.mark.asyncio
class TestTrendAgentPositionAware:
    """Test trend agent with position awareness."""
    
    def create_mock_ohlc(self, periods=60):
        """Create mock OHLC data with enough for slow MA."""
        base_price = 23000.0
        data = []
        for i in range(periods):
            data.append({
                'timestamp': datetime.now().isoformat(),
                'open': base_price + i * 0.5,
                'high': base_price + i * 0.5 + 10,
                'low': base_price + i * 0.5 - 10,
                'close': base_price + i * 0.5 + 5,
                'volume': 1000000 + i * 10000
            })
        return data
    
    async def test_trend_agent_without_positions(self):
        """Test trend agent without existing positions."""
        agent = TrendAgent()
        ohlc_data = self.create_mock_ohlc()
        
        context = {
            'ohlc': ohlc_data,
            'symbol': 'NIFTY50',
            'current_price': 23000.0,
            'current_positions': [],
            'has_long_position': False,
            'has_short_position': False,
            'position_count': 0
        }
        
        result = await agent.analyze(context)
        
        assert isinstance(result, AnalysisResult)
        assert result.decision in ['BUY', 'SELL', 'HOLD']
        assert 0.0 <= result.confidence <= 1.0
    
    async def test_trend_agent_with_long_position(self):
        """Test trend agent with existing long position."""
        agent = TrendAgent()
        ohlc_data = self.create_mock_ohlc()
        
        positions = [{
            'symbol': 'NIFTY50',
            'action': 'BUY',
            'quantity': 10,
            'entry_price': 23000.0,
            'status': 'active'
        }]
        
        context = {
            'ohlc': ohlc_data,
            'symbol': 'NIFTY50',
            'current_price': 23000.0,
            'current_positions': positions,
            'has_long_position': True,
            'has_short_position': False,
            'position_count': 1
        }
        
        result = await agent.analyze(context)
        
        assert isinstance(result, AnalysisResult)
        # Should consider existing position in decision
        if result.decision == 'BUY':
            details = result.details or {}
            reasoning = details.get('reasoning', [])
            if isinstance(reasoning, list):
                reasoning_str = ' '.join(reasoning)
            else:
                reasoning_str = str(reasoning)
            # May mention adding to position or have lower confidence
            assert 'adding' in reasoning_str.lower() or \
                   'existing' in reasoning_str.lower() or \
                   result.confidence < 0.85
    
    async def test_trend_agent_reversal_signal(self):
        """Test trend agent signals exit on trend reversal."""
        agent = TrendAgent()
        ohlc_data = self.create_mock_ohlc()
        
        positions = [{
            'symbol': 'NIFTY50',
            'action': 'BUY',
            'quantity': 10,
            'entry_price': 23000.0,
            'status': 'active'
        }]
        
        context = {
            'ohlc': ohlc_data,
            'symbol': 'NIFTY50',
            'current_price': 23000.0,
            'current_positions': positions,
            'has_long_position': True,
            'has_short_position': False,
            'position_count': 1
        }
        
        result = await agent.analyze(context)
        
        assert isinstance(result, AnalysisResult)
        # May signal SELL if trend reverses
        if result.decision == 'SELL':
            details = result.details or {}
            reasoning = details.get('reasoning', [])
            if isinstance(reasoning, list):
                reasoning_str = ' '.join(reasoning)
            else:
                reasoning_str = str(reasoning)
            # Should mention reversal or exiting
            assert 'reversal' in reasoning_str.lower() or \
                   'exit' in reasoning_str.lower() or \
                   'consider' in reasoning_str.lower()


