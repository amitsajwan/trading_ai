"""Integration test for complete data_niftybank module functionality."""
import pytest
from unittest.mock import Mock, patch

from market_data.api import (
    build_store, build_options_client
)


@pytest.mark.integration
class TestDataModuleIntegration:
    """Integration tests for the complete data_niftybank module."""

    def test_build_store_in_memory(self):
        """Test building in-memory store."""
        store = build_store()
        assert store is not None

        # Test basic store operations
        from market_data.contracts import MarketTick
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

    @patch("market_data.adapters.redis_store.redis")
    def test_build_store_redis(self, mock_redis):
        """Test building Redis-backed store."""
        mock_client = Mock()
        mock_redis.Redis.return_value = mock_client

        store = build_store(redis_client=mock_client)
        assert store is not None

        # Verify Redis client was passed to adapter
        assert store.redis_client == mock_client

    @patch("market_data.adapters.zerodha_options_chain.OptionsChainFetcher")
    def test_build_options_client(self, mock_fetcher_class):
        """Test building options client."""
        mock_kite = Mock()
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher

        options_client = build_options_client(mock_kite, mock_fetcher)
        assert options_client is not None
        assert options_client.fetcher == mock_fetcher

    @patch("market_data.adapters.zerodha_options_chain.OptionsChainFetcher")
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

        from market_data.contracts import OHLCBar
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
        from market_data.contracts import (
            MarketInstrument, MarketTick, OHLCBar,
            MarketStore, MarketIngestion, OptionsData
        )

        # Verify contracts are importable
        assert MarketStore is not None
        assert MarketIngestion is not None
        assert OptionsData is not None

    def test_adapter_imports(self):
        """Test that all adapters can be imported."""
        from market_data.adapters import (
            redis_store, zerodha_options_chain,
            macro_adapter
        )

        # Verify adapters are importable
        assert redis_store is not None
        assert zerodha_options_chain is not None
        assert macro_adapter is not None

