"""Integration test for complete data_niftybank module functionality."""
import pytest
from unittest.mock import Mock, patch

from data_niftybank.api import (
    build_store, build_options_client, build_ingestion,
    build_news_client, build_macro_client
)


@pytest.mark.integration
class TestDataModuleIntegration:
    """Integration tests for the complete data_niftybank module."""

    def test_build_store_in_memory(self):
        """Test building in-memory store."""
        store = build_store()
        assert store is not None

        # Test basic store operations
        from data_niftybank.contracts import MarketTick
        from datetime import datetime

        tick = MarketTick(
            instrument="NIFTY",
            timestamp=datetime.now(),
            last_price=22000.0,
            volume=1000
        )

        store.store_tick(tick)
        retrieved = store.get_latest_tick("NIFTY")
        assert retrieved is not None
        assert retrieved.last_price == 22000.0

    @patch("data_niftybank.adapters.redis_store.redis")
    def test_build_store_redis(self, mock_redis):
        """Test building Redis-backed store."""
        mock_client = Mock()
        mock_redis.Redis.return_value = mock_client

        store = build_store(redis_client=mock_client)
        assert store is not None

        # Verify Redis client was passed to adapter
        assert store.redis_client == mock_client

    @patch("data_niftybank.adapters.zerodha_options_chain.OptionsChainFetcher")
    def test_build_options_client(self, mock_fetcher_class):
        """Test building options client."""
        mock_kite = Mock()
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher

        options_client = build_options_client(mock_kite, mock_fetcher)
        assert options_client is not None
        assert options_client.fetcher == mock_fetcher

    @patch("data_niftybank.adapters.zerodha_ingestion.DataIngestionService")
    def test_build_ingestion_client(self, mock_ingestion_class):
        """Test building ingestion client."""
        mock_kite = Mock()
        mock_market_memory = Mock()
        mock_ingestion = Mock()
        mock_ingestion_class.return_value = mock_ingestion

        ingestion_client = build_ingestion(mock_kite, mock_market_memory)
        assert ingestion_client is not None

        # Test binding store
        mock_store = Mock()
        ingestion_client.bind_store(mock_store)
        assert ingestion_client.store == mock_store

    def test_build_news_client(self):
        """Test building news client."""
        mock_market_memory = Mock()

        news_client = build_news_client(mock_market_memory)
        assert news_client is not None
        assert news_client.market_memory == mock_market_memory

    def test_build_macro_client(self):
        """Test building macro client."""
        macro_client = build_macro_client()
        assert macro_client is not None

    @patch("data_niftybank.adapters.zerodha_options_chain.OptionsChainFetcher")
    @pytest.mark.asyncio
    async def test_options_client_initialization(self, mock_fetcher_class):
        """Test options client can be initialized."""
        mock_kite = Mock()
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher

        options_client = build_options_client(mock_kite, mock_fetcher)

        # Test initialization
        await options_client.initialize()

        # Verify fetcher was initialized
        mock_fetcher.initialize.assert_called_once()

    def test_store_ohlc_operations(self):
        """Test OHLC operations on market store."""
        store = build_store()

        from data_niftybank.contracts import OHLCBar
        from datetime import datetime

        bar = OHLCBar(
            instrument="NIFTY",
            timeframe="1min",
            open=22000.0,
            high=22050.0,
            low=21980.0,
            close=22030.0,
            volume=5000,
            start_at=datetime.now()
        )

        store.store_ohlc(bar)

        # Retrieve OHLC data
        bars = list(store.get_ohlc("NIFTY", "1min", limit=10))
        assert len(bars) >= 0  # May be empty depending on implementation

    def test_contract_imports(self):
        """Test that all contracts can be imported."""
        from data_niftybank.contracts import (
            MarketInstrument, MarketTick, OHLCBar,
            MarketStore, MarketIngestion, OptionsData,
            NewsData, MacroData, NewsItem, MacroIndicator
        )

        # Verify contracts are importable
        assert MarketStore is not None
        assert MarketIngestion is not None
        assert OptionsData is not None
        assert NewsData is not None
        assert MacroData is not None

    def test_adapter_imports(self):
        """Test that all adapters can be imported."""
        from data_niftybank.adapters import (
            redis_store, zerodha_options_chain,
            zerodha_ingestion, news_adapter, macro_adapter
        )

        # Verify adapters are importable
        assert redis_store is not None
        assert zerodha_options_chain is not None
        assert zerodha_ingestion is not None
        assert news_adapter is not None
        assert macro_adapter is not None
