"""Source adapters for market_data ingestion."""

from .websocket import WebSocketSource
from .historical import HistoricalSource
from .mock import MockSource
from .depth import DepthSource

__all__ = ["WebSocketSource", "HistoricalSource", "MockSource", "DepthSource"]
