"""Tests for AgentState model."""

import pytest
from datetime import datetime
from agents.state import AgentState, SignalType


def test_agent_state_creation():
    """Test creating an AgentState instance."""
    state = AgentState(
        current_price=45000.0,
        current_time=datetime.now()
    )
    
    assert state.current_price == 45000.0
    assert state.final_signal == SignalType.HOLD
    assert state.position_size == 0


def test_agent_state_update():
    """Test updating agent state."""
    state = AgentState()
    
    output = {
        "trend_direction": "UP",
        "confidence_score": 0.75
    }
    
    state.update_agent_output("technical", output)
    assert state.technical_analysis == output


def test_agent_state_explanations():
    """Test adding explanations."""
    state = AgentState()
    state.add_explanation("technical", "Trend is bullish")
    
    assert len(state.agent_explanations) == 1
    assert "technical" in state.agent_explanations[0]


def test_agent_state_serialization():
    """Test state serialization to dict."""
    state = AgentState(
        current_price=45000.0,
        current_time=datetime.now()
    )
    
    state_dict = state.to_dict()
    assert "current_price" in state_dict
    assert state_dict["current_price"] == 45000.0

