"""Tests for BaseAgent."""

import pytest
from unittest.mock import Mock, patch
from agents.base_agent import BaseAgent
from agents.state import AgentState


class MockTestAgent(BaseAgent):
    """Test agent implementation."""
    
    def _get_default_prompt(self) -> str:
        return "You are a mock test agent."
    
    def process(self, state: AgentState) -> AgentState:
        return state


def test_base_agent_initialization():
    """Test base agent initialization."""
    with patch('agents.base_agent.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        agent = MockTestAgent()
        
        assert agent.agent_name == "mock_test"
        assert agent.system_prompt == "You are a test agent."
        assert agent.llm_client is not None


def test_base_agent_process():
    """Test agent process method."""
    with patch('agents.base_agent.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        agent = MockTestAgent()
        state = AgentState()
        
        result = agent.process(state)
        
        assert result == state

