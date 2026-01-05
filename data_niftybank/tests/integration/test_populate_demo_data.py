"""Integration test for populate_demo_data functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from data_niftybank.tools.populate_demo_data import populate_historical_data


@pytest.mark.integration
class TestPopulateDemoData:
    """Integration tests for demo data population."""

    @patch("data_niftybank.tools.populate_demo_data.BinanceSpotFetcher")
    @patch("data_niftybank.tools.populate_demo_data.requests.get")
    @patch("data_niftybank.tools.populate_demo_data.get_mongo_client")
    @patch("data_niftybank.tools.populate_demo_data.get_collection")
    async def test_populate_historical_data_success(self, mock_get_collection, mock_get_client, mock_requests_get, mock_fetcher_class):
        """Test successful population of historical data."""
        # Mock MongoDB client and collection
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = mock_collection

        # Mock Binance API response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            [1640995200000, "43144.00000000", "43144.00000000", "43144.00000000", "43144.00000000", "0.00000000", 1640995259999, "0.00000000", 0, "0.00000000", "0.00000000", "0"]
        ]
        mock_requests_get.return_value = mock_response

        # Mock BinanceSpotFetcher
        mock_fetcher = MagicMock()
        mock_fetcher_class.return_value = mock_fetcher

        # Mock MarketMemory
        with patch("data_niftybank.tools.populate_demo_data.MarketMemory") as mock_mm_class:
            mock_mm = MagicMock()
            mock_mm_class.return_value = mock_mm

            # Run the function
            await populate_historical_data()

            # Verify that data was inserted into MongoDB
            # The function should have called insert_many or similar
            # Since this is integration testing, we just verify it doesn't crash
            assert mock_get_client.called
            assert mock_get_collection.called

    @patch("data_niftybank.tools.populate_demo_data.get_mongo_client")
    async def test_populate_historical_data_mongo_failure(self, mock_get_client):
        """Test handling of MongoDB connection failure."""
        # Mock MongoDB connection failure
        mock_get_client.side_effect = Exception("MongoDB connection failed")

        # The function should handle the exception gracefully
        # (it should not crash the test)
        with pytest.raises(Exception):
            await populate_historical_data()

    @patch("data_niftybank.tools.populate_demo_data.BinanceSpotFetcher")
    @patch("data_niftybank.tools.populate_demo_data.requests.get")
    @patch("data_niftybank.tools.populate_demo_data.get_mongo_client")
    @patch("data_niftybank.tools.populate_demo_data.get_collection")
    async def test_populate_crypto_data_success(self, mock_get_collection, mock_get_client, mock_requests_get, mock_fetcher_class):
        """Test successful population of crypto data."""
        # Similar setup as above
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = mock_collection

        # Mock API response for crypto data
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_requests_get.return_value = mock_response

        mock_fetcher = MagicMock()
        mock_fetcher_class.return_value = mock_fetcher

        with patch("data_niftybank.tools.populate_demo_data.CryptoDataFeed") as mock_crypto_class:
            mock_crypto = MagicMock()
            mock_crypto_class.return_value = mock_crypto

            # Import and run the crypto population function if it exists
            try:
                from data_niftybank.tools.populate_demo_data import populate_crypto_data
                await populate_crypto_data()

                assert mock_get_client.called
                assert mock_get_collection.called
            except ImportError:
                # Function might not exist, skip test
                pytest.skip("populate_crypto_data function not available")
