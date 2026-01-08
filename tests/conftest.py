"""Pytest configuration and fixtures.

This file injects local package `src` directories onto `sys.path` so that
running `pytest` from the repository root works without setting PYTHONPATH.
"""

import sys
from pathlib import Path

# Make any `*/src` directories importable during tests (convenience for devs/CI)
_root = Path(__file__).resolve().parents[1]
for child in _root.iterdir():
    src = child / "src"
    if src.is_dir():
        p = str(src)
        if p not in sys.path:
            sys.path.insert(0, p)
# Ensure repository root is also importable
_root_str = str(_root)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

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


