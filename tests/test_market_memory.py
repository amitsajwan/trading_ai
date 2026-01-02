"""Tests for MarketMemory (Redis wrapper)."""

import pytest
from unittest.mock import Mock, patch
from data.market_memory import MarketMemory


@patch('data.market_memory.redis.Redis')
def test_market_memory_initialization(mock_redis):
    """Test MarketMemory initialization."""
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_redis.return_value = mock_client
    
    memory = MarketMemory()
    
    assert memory.redis_client is not None
    mock_client.ping.assert_called_once()


@patch('data.market_memory.redis.Redis')
def test_store_and_get_ohlc(mock_redis):
    """Test storing and retrieving OHLC data."""
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_client.setex.return_value = None
    mock_client.zadd.return_value = None
    mock_client.zrange.return_value = ['{"timestamp": "2026-01-01T10:00:00", "close": 45000}']
    mock_redis.return_value = mock_client
    
    memory = MarketMemory(redis_client=mock_client)
    
    ohlc_data = {
        "timestamp": "2026-01-01T10:00:00",
        "open": 44900,
        "high": 45100,
        "low": 44800,
        "close": 45000,
        "volume": 1000
    }
    
    memory.store_ohlc("BANKNIFTY", "5min", ohlc_data)
    
    # Verify setex was called
    assert mock_client.setex.called
    
    # Test retrieval
    result = memory.get_recent_ohlc("BANKNIFTY", "5min", 1)
    assert len(result) == 1

