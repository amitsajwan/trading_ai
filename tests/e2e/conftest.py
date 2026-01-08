"""Pytest configuration and fixtures for end-to-end tests."""

import pytest
import pytest_asyncio
import os
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, date, timedelta
import json
import tempfile
import shutil

# Test database and Redis configuration
TEST_MONGODB_URI = os.getenv("TEST_MONGODB_URI", "mongodb://localhost:27017/")
TEST_REDIS_HOST = os.getenv("TEST_REDIS_HOST", "localhost")
TEST_REDIS_PORT = int(os.getenv("TEST_REDIS_PORT", "6379"))
TEST_DB_PREFIX = "zerodha_test_"


# Remove custom event_loop fixture - use pytest-asyncio's default


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("KITE_API_KEY", "test_key")
    monkeypatch.setenv("KITE_API_SECRET", "test_secret")
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("MONGODB_URI", TEST_MONGODB_URI)
    monkeypatch.setenv("REDIS_HOST", TEST_REDIS_HOST)
    monkeypatch.setenv("REDIS_PORT", str(TEST_REDIS_PORT))
    monkeypatch.setenv("PAPER_TRADING_MODE", "true")


@pytest.fixture
def mock_kite():
    """Mock KiteConnect instance with realistic responses."""
    kite = Mock()
    kite.api_key = "test_key"
    kite.access_token = "test_token"
    
    # Mock common API methods
    kite.ltp = Mock(return_value={
        "NSE:NIFTY BANK": {
            "last_price": 45000.0,
            "volume": 1500000
        }
    })
    
    kite.margins = Mock(return_value={
        "equity": {
            "enabled": True,
            "net": 1000000.0,
            "available": {
                "cash": 1000000.0,
                "live_balance": 1000000.0
            }
        }
    })
    
    kite.profile = Mock(return_value={
        "user_id": "test_user",
        "user_name": "Test User",
        "email": "test@example.com"
    })
    
    kite.positions = Mock(return_value={"net": [], "day": []})
    
    kite.orders = Mock(return_value=[])
    
    kite.instruments = Mock(return_value=[
        {
            "instrument_token": 26009,
            "tradingsymbol": "NIFTY BANK",
            "exchange": "NSE",
            "name": "NIFTY BANK",
            "instrument_type": "EQ"
        }
    ])
    
    kite.historical_data = Mock(return_value=[
        {
            "date": datetime.now() - timedelta(minutes=i),
            "open": 45000.0 + i * 10,
            "high": 45100.0 + i * 10,
            "low": 44900.0 + i * 10,
            "close": 45050.0 + i * 10,
            "volume": 1000000
        }
        for i in range(100, 0, -1)
    ])
    
    kite.place_order = Mock(return_value={"order_id": "test_order_123"})
    
    return kite


@pytest.fixture
def test_db_name():
    """Generate unique test database name."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{TEST_DB_PREFIX}{timestamp}"


@pytest_asyncio.fixture
async def test_mongo_client(test_db_name):
    """Create MongoDB client for testing."""
    try:
        from pymongo import MongoClient
        client = MongoClient(TEST_MONGODB_URI)
        db = client[test_db_name]
        yield db
        
        # Cleanup: drop test database
        client.drop_database(test_db_name)
        client.close()
    except Exception as e:
        pytest.skip(f"MongoDB not available: {e}")


@pytest_asyncio.fixture
async def test_redis_client():
    """Create Redis client for testing."""
    try:
        import redis.asyncio as redis
        client = redis.Redis(
            host=TEST_REDIS_HOST,
            port=TEST_REDIS_PORT,
            db=1,  # Use db=1 for tests
            decode_responses=True
        )
        # Test connection
        await client.ping()
        
        # Clear test database
        await client.flushdb()
        
        yield client
        
        # Cleanup
        await client.flushdb()
        await client.close()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture
def paper_broker():
    """Create paper broker instance for testing."""
    from market_data.adapters.paper_broker import PaperBroker
    return PaperBroker(initial_capital=1000000.0)


@pytest.fixture
def mock_market_store():
    """Create mock market store."""
    from market_data.store import InMemoryMarketStore
    return InMemoryMarketStore()


@pytest.fixture
def sample_market_tick():
    """Sample market tick data."""
    from market_data.contracts import MarketTick
    return MarketTick(
        instrument="NIFTY BANK",
        timestamp=datetime.now(),
        last_price=45000.0,
        volume=1500000
    )


@pytest.fixture
def sample_ohlc_bar():
    """Sample OHLC bar data."""
    from market_data.contracts import OHLCBar
    return OHLCBar(
        instrument="NIFTY BANK",
        timeframe="1min",
        open=45000.0,
        high=45100.0,
        low=44900.0,
        close=45050.0,
        volume=1000000,
        start_at=datetime.now()
    )


@pytest.fixture
def sample_trading_signal():
    """Sample trading signal."""
    return {
        "id": "test_signal_001",
        "symbol": "NIFTY BANK",
        "action": "BUY",
        "agent_name": "momentum_agent",
        "confidence": 0.75,
        "entry_price": 45000.0,
        "stop_loss": 44800.0,
        "take_profit": 45300.0,
        "quantity": 25,
        "status": "pending",
        "execution_type": "conditional",
        "conditions": {
            "rsi_14": {"operator": ">", "threshold": 32.0},
            "volume_ratio": {"operator": ">", "threshold": 1.2}
        },
        "created_at": datetime.now().isoformat()
    }


@pytest.fixture
def api_client():
    """Create FastAPI test client."""
    try:
        from fastapi.testclient import TestClient
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
        from dashboard.app import app
        return TestClient(app)
    except Exception as e:
        pytest.skip(f"Cannot create API client: {e}")


@pytest_asyncio.fixture
async def async_api_client():
    """Create async FastAPI test client."""
    try:
        from httpx import AsyncClient, ASGITransport
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
        from dashboard.app import app
        
        transport = ASGITransport(app=app)
        client = AsyncClient(transport=transport, base_url="http://test")
        yield client
        await client.aclose()
    except Exception as e:
        pytest.skip(f"Cannot create async API client: {e}")


@pytest.fixture
def historical_data_generator():
    """Generate historical market data for testing."""
    def _generate(start_date: date, end_date: date, interval: str = "minute"):
        """Generate historical data between dates."""
        data = []
        current = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
        
        base_price = 45000.0
        while current <= end:
            data.append({
                "date": current,
                "open": base_price,
                "high": base_price + 100,
                "low": base_price - 100,
                "close": base_price + 50,
                "volume": 1000000
            })
            base_price += 10  # Slight upward trend
            current += timedelta(minutes=1 if interval == "minute" else 60)
        
        return data
    return _generate


@pytest.fixture
def mode_manager():
    """Create mode manager for testing."""
    try:
        from dashboard.core.mode import ModeManager
        return ModeManager()
    except Exception as e:
        pytest.skip(f"Cannot create mode manager: {e}")


@pytest.fixture
def signal_validator():
    """Create signal validator utility."""
    def _validate_signal(signal: dict) -> tuple[bool, list[str]]:
        """Validate signal structure and return (is_valid, errors)."""
        errors = []
        required_fields = ["id", "symbol", "action", "status"]
        for field in required_fields:
            if field not in signal:
                errors.append(f"Missing required field: {field}")
        
        if signal.get("action") not in ["BUY", "SELL", "HOLD"]:
            errors.append(f"Invalid action: {signal.get('action')}")
        
        if signal.get("status") not in ["pending", "executed", "rejected", "expired"]:
            errors.append(f"Invalid status: {signal.get('status')}")
        
        return len(errors) == 0, errors
    
    return _validate_signal


@pytest.fixture
def trade_validator():
    """Create trade validator utility."""
    def _validate_trade(trade: dict) -> tuple[bool, list[str]]:
        """Validate trade structure and return (is_valid, errors)."""
        errors = []
        required_fields = ["symbol", "action", "quantity", "price"]
        for field in required_fields:
            if field not in trade:
                errors.append(f"Missing required field: {field}")
        
        if trade.get("quantity", 0) <= 0:
            errors.append("Quantity must be positive")
        
        if trade.get("price", 0) <= 0:
            errors.append("Price must be positive")
        
        return len(errors) == 0, errors
    
    return _validate_trade


