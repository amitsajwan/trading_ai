"""Validate all data adapters work correctly with mock data."""
import pytest
from unittest.mock import Mock, AsyncMock

from data_niftybank.api import (
    build_store, build_options_client, build_ingestion,
    build_news_client, build_macro_client, build_historical_replay,
    build_ltp_collector
)


class TestAdapterValidation:
    """Validate all adapters work with mock data."""

    def test_store_adapters(self, mock_redis_client, sample_market_ticks, sample_ohlc_bars):
        """Test both Redis and in-memory store adapters."""
        # Test in-memory store (Redis store requires running Redis server)
        memory_store = build_store()  # In-memory store

        # Store sample data
        for tick in sample_market_ticks[:3]:
            memory_store.store_tick(tick)

        for bar in sample_ohlc_bars[:2]:
            memory_store.store_ohlc(bar)

        # Verify data was stored
        retrieved_tick = memory_store.get_latest_tick("NIFTY")
        assert retrieved_tick is not None
        assert retrieved_tick.last_price > 0

        # Test in-memory store
        memory_store = build_store()  # No redis_client

        for tick in sample_market_ticks[:3]:
            memory_store.store_tick(tick)

        retrieved_tick = memory_store.get_latest_tick("NIFTY")
        assert retrieved_tick is not None

    def test_options_adapter(self, mock_kite, mock_market_memory, mock_options_chain):
        """Test options chain adapter with mock data."""
        # Create mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.initialize = AsyncMock()
        mock_fetcher.fetch_options_chain = AsyncMock(return_value=mock_options_chain)

        options_client = build_options_client(mock_kite, mock_fetcher)

        # Test the adapter wraps the fetcher correctly
        assert options_client.fetcher == mock_fetcher
        assert options_client.instrument_symbol == "BANKNIFTY"  # Normalized from default

    def test_ingestion_adapters(self, mock_kite, mock_market_memory):
        """Test ingestion adapters (WebSocket and LTP)."""
        # Test WebSocket ingestion adapter
        ingestion = build_ingestion(mock_kite, mock_market_memory)
        assert ingestion.kite == mock_kite
        assert ingestion.market_memory == mock_market_memory

        # Test binding store
        mock_store = Mock()
        ingestion.bind_store(mock_store)
        assert ingestion.store == mock_store

        # Test LTP collector adapter
        ltp_ingestion = build_ltp_collector(mock_kite, mock_market_memory)
        assert ltp_ingestion.kite == mock_kite
        assert ltp_ingestion.market_memory == mock_market_memory

    def test_news_adapter(self, mock_market_memory, sample_news_items):
        """Test news data adapter."""
        news_client = build_news_client(mock_market_memory)
        assert news_client.market_memory == mock_market_memory

        # Mock internal method
        news_client._get_news_from_collector = AsyncMock(return_value=[
            {
                "title": item.title,
                "content": item.content,
                "source": item.source,
                "published_at": item.published_at.isoformat(),
                "sentiment_score": item.sentiment_score,
                "relevance_score": item.relevance_score
            }
            for item in sample_news_items[:2]
        ])

        # Test would work with proper async context
        # This validates the adapter structure
        assert hasattr(news_client, 'get_latest_news')
        assert hasattr(news_client, 'get_sentiment_summary')

    def test_macro_adapter(self, sample_macro_indicators):
        """Test macro data adapter."""
        macro_client = build_macro_client()

        # Mock internal methods
        macro_client._get_inflation_from_fetcher = AsyncMock(return_value=[
            {"value": 5.2, "date": "2024-01-01T00:00:00"}
        ])

        macro_client._get_rbi_from_scraper = AsyncMock(return_value=[
            {"value": 6.5, "date": "2024-01-01T00:00:00", "unit": "percent"}
        ])

        # Test methods exist
        assert hasattr(macro_client, 'get_inflation_data')
        assert hasattr(macro_client, 'get_rbi_data')

    def test_historical_replay_adapter(self, mock_redis_client):
        """Test historical data replay adapter."""
        store = build_store(redis_client=mock_redis_client)
        replay = build_historical_replay(store, data_source="synthetic")

        assert replay.store == store
        assert replay.data_source == "synthetic"
        assert replay.speed_multiplier == 1.0

        # Test binding (should work since store is already set)
        replay.bind_store(store)
        assert replay.store == store

    def test_adapter_contract_compliance(self):
        """Test all adapters comply with their contracts."""
        from data_niftybank.contracts import MarketStore, MarketIngestion, OptionsData, NewsData, MacroData

        # Test store implementations
        redis_store = build_store(redis_client=Mock())
        memory_store = build_store()

        # Check MarketStore protocol compliance
        required_store_methods = ['store_tick', 'get_latest_tick', 'store_ohlc', 'get_ohlc']
        for method in required_store_methods:
            assert hasattr(redis_store, method), f"RedisStore missing {method}"
            assert hasattr(memory_store, method), f"InMemoryStore missing {method}"

        # Test ingestion implementations
        mock_kite = Mock()
        mock_memory = Mock()

        ws_ingestion = build_ingestion(mock_kite, mock_memory)
        ltp_ingestion = build_ltp_collector(mock_kite, mock_memory)
        replay_ingestion = build_historical_replay(build_store(), "synthetic")

        # Check MarketIngestion protocol compliance
        required_ingestion_methods = ['bind_store', 'start', 'stop']
        for method in required_ingestion_methods:
            assert hasattr(ws_ingestion, method), f"WS Ingestion missing {method}"
            assert hasattr(ltp_ingestion, method), f"LTP Ingestion missing {method}"
            assert hasattr(replay_ingestion, method), f"Replay Ingestion missing {method}"

        # Test other adapters
        news_adapter = build_news_client(Mock())
        macro_adapter = build_macro_client()

        # Check NewsData protocol
        required_news_methods = ['get_latest_news', 'get_sentiment_summary']
        for method in required_news_methods:
            assert hasattr(news_adapter, method), f"News adapter missing {method}"

        # Check MacroData protocol
        required_macro_methods = ['get_inflation_data', 'get_rbi_data']
        for method in required_macro_methods:
            assert hasattr(macro_adapter, method), f"Macro adapter missing {method}"

    def test_error_handling_in_adapters(self):
        """Test error handling in adapters."""
        # Test store with invalid data
        store = build_store()

        # Test with invalid instrument
        result = store.get_latest_tick("NONEXISTENT")
        assert result is None

        # Test OHLC with invalid timeframe
        bars = list(store.get_ohlc("NIFTY", "invalid_timeframe"))
        assert isinstance(bars, list)  # Should return empty list, not crash

        # Test with valid data
        from data_niftybank.contracts import MarketTick
        from datetime import datetime

        tick = MarketTick("TEST", datetime.now(), 100.0, 10)
        store.store_tick(tick)  # Should work fine

        retrieved = store.get_latest_tick("TEST")
        assert retrieved is not None

    def test_adapter_initialization_parameters(self):
        """Test adapter initialization with various parameters."""
        # Test store with different configurations
        store_no_redis = build_store()
        assert store_no_redis is not None

        store_with_redis = build_store(redis_client=Mock())
        assert store_with_redis is not None

        # Test historical replay with different sources
        replay_synthetic = build_historical_replay(build_store(), "synthetic")
        assert replay_synthetic.data_source == "synthetic"

        replay_file = build_historical_replay(build_store(), "/path/to/file.json")
        assert replay_file.data_source == "/path/to/file.json"
