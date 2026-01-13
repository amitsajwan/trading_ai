"""Unit tests for MultiTimeframeReader."""

import pytest
from datetime import datetime, timedelta
from typing import List

from market_data.contracts import MarketStore, OHLCBar
from market_data.ohlc.multi_timeframe_reader import (
    MultiTimeframeReader,
    TimeframeData
)


class MockMarketStore(MarketStore):
    """Mock MarketStore for testing."""
    
    def __init__(self):
        self._ohlc_data: dict = {}
    
    def store_tick(self, tick):
        pass
    
    def get_latest_tick(self, instrument: str):
        return None
    
    def store_ohlc(self, bar: OHLCBar):
        instrument = bar.instrument
        timeframe = bar.timeframe
        if instrument not in self._ohlc_data:
            self._ohlc_data[instrument] = {}
        if timeframe not in self._ohlc_data[instrument]:
            self._ohlc_data[instrument][timeframe] = []
        self._ohlc_data[instrument][timeframe].append(bar)
    
    def get_ohlc(self, instrument: str, timeframe: str, limit: int = 100):
        if instrument not in self._ohlc_data:
            return []
        if timeframe not in self._ohlc_data[instrument]:
            return []
        bars = self._ohlc_data[instrument][timeframe]
        return bars[-limit:] if limit > 0 else bars


def create_sample_bar(instrument: str, timeframe: str, offset_minutes: int = 0) -> OHLCBar:
    """Create a sample OHLC bar."""
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


class TestTimeframeData:
    """Tests for TimeframeData dataclass."""
    
    def test_timeframe_data_creation(self):
        """Test creating TimeframeData."""
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(5)]
        data = TimeframeData(
            timeframe="5m",
            bars=bars,
            count=5,
            latest_timestamp=bars[-1].start_at,
            cached_at=datetime.now()
        )
        
        assert data.timeframe == "5m"
        assert data.count == 5
        assert len(data.bars) == 5
        assert data.latest_timestamp == bars[-1].start_at
    
    def test_timeframe_data_to_dict(self):
        """Test TimeframeData serialization."""
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(3)]
        data = TimeframeData(
            timeframe="5m",
            bars=bars,
            count=3,
            latest_timestamp=bars[-1].start_at,
            cached_at=datetime.now()
        )
        
        result = data.to_dict()
        
        assert result["timeframe"] == "5m"
        assert result["count"] == 3
        assert len(result["bars"]) == 3
        assert result["latest_timestamp"] is not None


class TestMultiTimeframeReader:
    """Tests for MultiTimeframeReader."""
    
    def test_initialization(self):
        """Test reader initialization."""
        store = MockMarketStore()
        reader = MultiTimeframeReader(store, cache_ttl_seconds=60)
        
        assert reader.market_store == store
        assert reader.cache_ttl == 60
        assert reader.max_cache_size == 1000
    
    def test_fetch_single_timeframe(self):
        """Test fetching single timeframe."""
        store = MockMarketStore()
        
        # Add some data
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(10)]
        for bar in bars:
            store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(store)
        result = reader.fetch_timeframe("BANKNIFTY", "5m", limit=10)
        
        assert result.timeframe == "5m"
        assert result.count == 10
        assert len(result.bars) == 10
    
    def test_fetch_all_timeframes(self):
        """Test fetching multiple timeframes."""
        store = MockMarketStore()
        
        # Add data for different timeframes
        for timeframe in ["5m", "15m", "1h"]:
            for i in range(5):
                bar = create_sample_bar("BANKNIFTY", timeframe, i)
                store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(store)
        result = reader.fetch_all_timeframes("BANKNIFTY", ["5m", "15m", "1h"])
        
        assert "5m" in result
        assert "15m" in result
        assert "1h" in result
        assert result["5m"].count == 5
        assert result["15m"].count == 5
        assert result["1h"].count == 5
    
    def test_cache_functionality(self):
        """Test caching mechanism."""
        store = MockMarketStore()
        
        # Add data
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(5)]
        for bar in bars:
            store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(store, cache_ttl_seconds=60)
        
        # First fetch - should hit store
        result1 = reader.fetch_timeframe("BANKNIFTY", "5m", use_cache=True)
        
        # Second fetch - should hit cache
        result2 = reader.fetch_timeframe("BANKNIFTY", "5m", use_cache=True)
        
        # Results should be same
        assert result1.count == result2.count
        assert len(result1.bars) == len(result2.bars)
    
    def test_cache_expiry(self):
        """Test cache expiry."""
        store = MockMarketStore()
        
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(5)]
        for bar in bars:
            store.store_ohlc(bar)
        
        # Very short cache TTL
        reader = MultiTimeframeReader(store, cache_ttl_seconds=1)
        
        # First fetch
        result1 = reader.fetch_timeframe("BANKNIFTY", "5m")
        
        # Wait for cache to expire
        import time
        time.sleep(1.1)
        
        # Second fetch should hit store again (cache expired)
        result2 = reader.fetch_timeframe("BANKNIFTY", "5m")
        
        # Results should still be same (same data in store)
        assert result1.count == result2.count
    
    def test_cache_clearing(self):
        """Test cache clearing."""
        store = MockMarketStore()
        
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(5)]
        for bar in bars:
            store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(store)
        
        # Fetch to populate cache
        reader.fetch_timeframe("BANKNIFTY", "5m")
        
        assert len(reader._cache) > 0
        
        # Clear cache for instrument
        reader.clear_cache("BANKNIFTY")
        
        assert "BANKNIFTY" not in reader._cache
        
        # Clear all cache
        reader.fetch_timeframe("BANKNIFTY", "5m")
        reader.clear_cache()
        
        assert len(reader._cache) == 0
    
    def test_unsupported_timeframe(self):
        """Test error handling for unsupported timeframe."""
        store = MockMarketStore()
        reader = MultiTimeframeReader(store)
        
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            reader.fetch_timeframe("BANKNIFTY", "invalid_tf")
    
    def test_limit_parameter(self):
        """Test limit parameter."""
        store = MockMarketStore()
        
        # Add more bars than limit
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(20)]
        for bar in bars:
            store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(store)
        result = reader.fetch_timeframe("BANKNIFTY", "5m", limit=10)
        
        assert result.count == 10
        assert len(result.bars) == 10
    
    def test_cache_stats(self):
        """Test cache statistics."""
        store = MockMarketStore()
        reader = MultiTimeframeReader(store)
        
        # Fetch some data
        bars = [create_sample_bar("BANKNIFTY", "5m", i) for i in range(5)]
        for bar in bars:
            store.store_ohlc(bar)
        
        reader.fetch_timeframe("BANKNIFTY", "5m")
        
        stats = reader.get_cache_stats()
        
        assert stats["total_instruments"] >= 1
        assert stats["total_entries"] >= 1
        assert stats["cache_ttl_seconds"] > 0
        assert "BANKNIFTY" in stats["cached_instruments"]
    
    def test_fetch_all_default_timeframes(self):
        """Test fetching all default timeframes."""
        store = MockMarketStore()
        
        # Add data for all supported timeframes
        for timeframe in MultiTimeframeReader.SUPPORTED_TIMEFRAMES:
            for i in range(3):
                bar = create_sample_bar("BANKNIFTY", timeframe, i)
                store.store_ohlc(bar)
        
        reader = MultiTimeframeReader(store)
        result = reader.fetch_all_timeframes("BANKNIFTY")
        
        # Should have all supported timeframes
        assert len(result) == len(MultiTimeframeReader.SUPPORTED_TIMEFRAMES)
        for tf in MultiTimeframeReader.SUPPORTED_TIMEFRAMES:
            assert tf in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
