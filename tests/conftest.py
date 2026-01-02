"""Pytest configuration and fixtures."""

import pytest
import os
from unittest.mock import Mock, patch


@pytest.fixture
def mock_kite():
    """Mock KiteConnect instance."""
    kite = Mock()
    kite.api_key = "test_key"
    kite.access_token = "test_token"
    return kite


@pytest.fixture
def mock_market_memory():
    """Mock MarketMemory instance."""
    memory = Mock()
    memory.get_current_price.return_value = 45000.0
    memory.get_recent_ohlc.return_value = []
    memory.get_latest_sentiment.return_value = 0.5
    return memory


@pytest.fixture
def sample_agent_state():
    """Sample AgentState for testing."""
    from agents.state import AgentState
    from datetime import datetime
    
    return AgentState(
        current_price=45000.0,
        current_time=datetime.now(),
        sentiment_score=0.5
    )


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("KITE_API_KEY", "test_key")
    monkeypatch.setenv("KITE_API_SECRET", "test_secret")
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("PAPER_TRADING_MODE", "true")

