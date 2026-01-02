"""Tests for TradingGraph."""

import pytest
from unittest.mock import Mock, patch
from agents.state import AgentState
import sys
import os
# Add parent directory to path to avoid import conflicts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_orchestration.trading_graph import TradingGraph


@patch('langgraph.trading_graph.MarketMemory')
@patch('langgraph.trading_graph.KiteConnect')
def test_trading_graph_initialization(mock_kite, mock_memory):
    """Test TradingGraph initialization."""
    mock_kite_instance = Mock()
    mock_kite.return_value = mock_kite_instance
    mock_memory_instance = Mock()
    mock_memory.return_value = mock_memory_instance
    
    graph = TradingGraph(kite=mock_kite_instance, market_memory=mock_memory_instance)
    
    assert graph.technical_agent is not None
    assert graph.fundamental_agent is not None
    assert graph.portfolio_manager is not None
    assert graph.graph is not None


@patch('langgraph.trading_graph.MarketMemory')
@patch('langgraph.trading_graph.KiteConnect')
def test_trading_graph_run(mock_kite, mock_memory):
    """Test running the trading graph."""
    mock_kite_instance = Mock()
    mock_kite.return_value = mock_kite_instance
    mock_memory_instance = Mock()
    mock_memory.return_value = mock_memory_instance
    
    # Mock state manager
    with patch('langgraph.trading_graph.StateManager') as mock_state_mgr:
        mock_state_mgr_instance = Mock()
        mock_state_mgr.return_value = mock_state_mgr_instance
        mock_state_mgr_instance.initialize_state.return_value = AgentState()
        
        graph = TradingGraph(kite=mock_kite_instance, market_memory=mock_memory_instance)
        
        # Mock the compiled graph
        mock_compiled_graph = Mock()
        mock_compiled_graph.invoke.return_value = AgentState()
        graph.graph = mock_compiled_graph
        
        result = graph.run()
        
        assert result is not None
        mock_compiled_graph.invoke.assert_called_once()

