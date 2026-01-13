"""Integration tests for MultiTimeframeReader with Redis."""

import pytest
import redis
from datetime import datetime, timedelta
import os

from market_data.adapters.redis_store import RedisMarketStore
from market_data.contracts import OHLCBar
from market_data.ohlc.multi_timeframe_reader import MultiTimeframeReader


def get_redis_client():
    """Get Redis client for testing."""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=False)


@pytest.fixture
def redis_client():
    """Redis client fixture."""
    client = get_redis_client()
    try:
        client.ping()
        yield client
    except redis.ConnectionError:
        pytest.skip("Redis not available for integration tests")
    finally:
        # Cleanup: remove test data
        try:
            keys = client.keys("ohlc_sorted:*TEST*")
            if keys:
                client.delete(*keys)
        except Exception:
            pass


@pytest.fixture
def market_store(redis_client):
    """Market store fixture."""
    return RedisMarketStore(redis_client, enable_candle_building=False)


def create_test_bar(instrument: str, timeframe: str, offset_minutes: int = 0) -> OHLCBar:
    """Create a test OHLC bar."""
    base_time = datetime.now() - timedelta(minutes=offset_minutes)
    return OHLCBar(
        instrument=instrument,
        timeframe=timeframe,
        open=100.0 + offset_minutes * 0.1,
        high=101.0 + offset_minutes * 0.1,
        low=99.0 + offset_minutes * 0.1,
        close=100.5 + offset_minutes * 0.1,
        volume=1000,
        start_at=base_time
    )


class TestMultiTimeframeIntegration:
    """Integration tests for MultiTimeframeReader with Redis."""
    
    def test_fetch_from_redis_store(self, market_store):
        """Test fetching data from Redis store."""
        # Add test data
        instrument = "BANKNIFTY_TEST"
        bars = [create_test_bar(instrument, "5m", i) for i in range(10)]
        for bar in bars:
            market_store.store_ohlc(bar)
        
        # Create reader
        reader = MultiTimeframeReader(market_store)
        
        # Fetch data
        result = reader.fetch_timeframe(instrument, "5m", limit=10)
        
        assert result.timeframe == "5m"
        assert result.count == 10
        assert len(result.bars) == 10
    
    def test_multiple_timeframes_redis(self, market_store):
        """Test fetching multiple timeframes from Redis."""
        instrument = "BANKNIFTY_TEST"
        
        # Add data for multiple timeframes
        for timeframe in ["5m", "15m", "1h"]:
            for i in range(5):
                bar = create_test_bar(instrument, timeframe, i)
                market_store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(market_store)
        result = reader.fetch_all_timeframes(instrument, ["5m", "15m", "1h"])
        
        assert "5m" in result
        assert "15m" in result
        assert "1h" in result
        assert result["5m"].count == 5
        assert result["15m"].count == 5
        assert result["1h"].count == 5
    
    def test_cache_with_redis(self, market_store):
        """Test caching with Redis backend."""
        instrument = "BANKNIFTY_TEST"
        
        # Add data
        bars = [create_test_bar(instrument, "5m", i) for i in range(5)]
        for bar in bars:
            market_store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(market_store, cache_ttl_seconds=60)
        
        # First fetch
        result1 = reader.fetch_timeframe(instrument, "5m")
        
        # Second fetch should use cache
        result2 = reader.fetch_timeframe(instrument, "5m")
        
        # Results should match
        assert result1.count == result2.count
        assert len(result1.bars) == len(result2.bars)
    
    def test_empty_timeframe(self, market_store):
        """Test handling of empty timeframes."""
        instrument = "BANKNIFTY_TEST_EMPTY"
        
        reader = MultiTimeframeReader(market_store)
        result = reader.fetch_timeframe(instrument, "5m")
        
        # Should return empty data, not error
        assert result.timeframe == "5m"
        assert result.count == 0
        assert len(result.bars) == 0
    
    def test_different_instruments(self, market_store):
        """Test fetching data for different instruments."""
        instruments = ["BANKNIFTY_TEST_1", "BANKNIFTY_TEST_2"]
        
        for instrument in instruments:
            bars = [create_test_bar(instrument, "5m", i) for i in range(3)]
            for bar in bars:
                market_store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(market_store)
        
        for instrument in instruments:
            result = reader.fetch_timeframe(instrument, "5m")
            assert result.count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
