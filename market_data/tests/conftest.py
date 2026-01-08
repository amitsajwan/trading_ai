"""Test fixtures and mock data providers for data_niftybank tests."""
import sys
import os
from pathlib import Path

# Add repository root to sys.path so top-level packages (providers, schemas, config) are importable
REPO_ROOT = Path(__file__).resolve().parents[1].parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Setup Python path to import market_data module
MODULE_ROOT = Path(__file__).resolve().parents[1]
SRC = MODULE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Also ensure news_module src path is available for adapter imports
NEWS_SRC = Path(__file__).resolve().parents[2] / "news_module" / "src"
if str(NEWS_SRC) not in sys.path:
    sys.path.insert(0, str(NEWS_SRC))

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from market_data.contracts import MarketTick, OHLCBar


@pytest.fixture
def mock_kite():
    """Mock KiteConnect instance for testing."""
    kite = Mock()
    kite.instruments.return_value = [
        {
            "tradingsymbol": "NIFTY BANK",
            "instrument_token": 260105,
            "exchange": "NSE",
            "segment": "INDICES"
        }
    ]
    kite.ltp.return_value = {
        "260105": {
            "instrument_token": 260105,
            "last_price": 45000.0
        }
    }
    kite.quote.return_value = {
        "260105": {
            "instrument_token": 260105,
            "last_price": 45000.0,
            "ohlc": {
                "open": 44800.0,
                "high": 45100.0,
                "low": 44700.0,
                "close": 45000.0
            },
            "volume": 1500000
        }
    }
    return kite


@pytest.fixture
def mock_market_memory():
    """Mock MarketMemory instance for testing."""
    memory = Mock()
    memory.get_latest_price.return_value = 45000.0
    memory.store_tick = Mock()
    memory.get_ohlc_data.return_value = []
    return memory


@pytest.fixture
def sample_market_ticks():
    """Sample market tick data for testing."""
    base_time = datetime.now()
    return [
        MarketTick(
            instrument="NIFTY",
            timestamp=base_time - timedelta(minutes=i),
            last_price=22000.0 + (i * 10),
            volume=1000 + (i * 100)
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_ohlc_bars():
    """Sample OHLC bar data for testing."""
    base_time = datetime.now().replace(second=0, microsecond=0)
    bars = []
    for i in range(5):
        bar_time = base_time - timedelta(minutes=5*i)
        base_price = 22000.0 + (i * 50)
        bars.append(OHLCBar(
            instrument="NIFTY",
            timeframe="5min",
            open=base_price,
            high=base_price + 25,
            low=base_price - 15,
            close=base_price + 10,
            volume=5000 + (i * 500),
            start_at=bar_time
        ))
    return bars


@pytest.fixture
def mock_options_chain():
    """Mock options chain data."""
    return {
        "BANKNIFTY": {
            "calls": [
                {
                    "strike": 44000,
                    "last_price": 1200.0,
                    "open_interest": 15000,
                    "volume": 5000
                },
                {
                    "strike": 44500,
                    "last_price": 800.0,
                    "open_interest": 22000,
                    "volume": 8000
                }
            ],
            "puts": [
                {
                    "strike": 44000,
                    "last_price": 800.0,
                    "open_interest": 18000,
                    "volume": 6000
                },
                {
                    "strike": 44500,
                    "last_price": 1200.0,
                    "open_interest": 25000,
                    "volume": 9000
                }
            ]
        }
    }


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    redis_client = Mock()
    redis_client.ping.return_value = True
    redis_client.get.return_value = None
    redis_client.set.return_value = True
    redis_client.zadd.return_value = True
    redis_client.zrange.return_value = []
    return redis_client


class MockDataIngestionService:
    """Mock data ingestion service for testing."""

    def __init__(self, kite, market_memory):
        self.kite = kite
        self.market_memory = market_memory
        self.running = False

    def start(self):
        """Start mock ingestion."""
        self.running = True

    def stop(self):
        """Stop mock ingestion."""
        self.running = False


class MockNewsCollector:
    """Mock news collector for testing."""

    def __init__(self, market_memory):
        self.market_memory = market_memory

    async def get_news(self, instrument, limit=10):
        """Get mock news data."""
        return [
            {
                "title": f"Mock news for {instrument}",
                "content": "Mock content",
                "source": "Mock Source",
                "published_at": datetime.now(),
                "sentiment_score": 0.5,
                "relevance_score": 0.8
            }
        ]
