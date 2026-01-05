"""Zerodha data ingestion adapter using the legacy DataIngestionService.

This adapter provides real-time market data ingestion via Zerodha WebSocket.
"""
import logging
from typing import Optional

from ..contracts import MarketIngestion, MarketStore

logger = logging.getLogger(__name__)


class ZerodhaIngestionAdapter(MarketIngestion):
    """Adapter that wraps DataIngestionService for MarketIngestion protocol.

    Provides real-time market data ingestion from Zerodha Kite WebSocket,
    converting ticks and OHLC data to MarketTick and OHLCBar format.
    """

    def __init__(self, kite, market_memory):
        """Initialize with Zerodha dependencies.

        Args:
            kite: KiteConnect instance with valid access token
            market_memory: MarketMemory instance for caching
        """
        self.kite = kite
        self.market_memory = market_memory
        self.ingestion_service = None
        self.store: Optional[MarketStore] = None

    def bind_store(self, store: MarketStore) -> None:
        """Bind the market store for data persistence.

        Args:
            store: MarketStore instance to write ticks and OHLC data to
        """
        self.store = store

    def start(self) -> None:
        """Start the data ingestion service."""
        if self.ingestion_service is None:
            # Import here to avoid circular imports
            from data.ingestion_service import DataIngestionService
            self.ingestion_service = DataIngestionService(
                self.kite, self.market_memory
            )

        logger.info("Starting Zerodha data ingestion...")
        self.ingestion_service.start()

    def stop(self) -> None:
        """Stop the data ingestion service."""
        if self.ingestion_service:
            logger.info("Stopping Zerodha data ingestion...")
            self.ingestion_service.stop()
        else:
            logger.warning("Ingestion service not started")
