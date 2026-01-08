"""Lightweight contracts for NIFTY/BANKNIFTY data handling."""
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Protocol


@dataclass
class MarketInstrument:
    """Normalized instrument identifier."""

    symbol: str
    exchange: Optional[str] = None


@dataclass
class MarketTick:
    """Simple tick payload for the latest price.

    `original_timestamp` is optional and set when ingesting historical ticks that
    are rebased to the current time so the original event time is preserved.
    """

    instrument: str
    timestamp: datetime
    last_price: float
    volume: Optional[int] = None
    original_timestamp: Optional[datetime] = None


@dataclass
class OHLCBar:
    """Aggregated OHLC bar for a timeframe."""

    instrument: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int]
    start_at: datetime


class MarketStore(Protocol):
    """Storage contract for ticks and OHLC bars."""

    def store_tick(self, tick: MarketTick) -> None:
        ...

    def get_latest_tick(self, instrument: str) -> Optional[MarketTick]:
        ...

    def store_ohlc(self, bar: OHLCBar) -> None:
        ...

    def get_ohlc(self, instrument: str, timeframe: str, limit: int = 100) -> Iterable[OHLCBar]:
        ...


class MarketIngestion(Protocol):
    """Lifecycle for ingestion adapters (e.g., Zerodha WS, REST polling)."""

    def bind_store(self, store: MarketStore) -> None:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


class OptionsData(Protocol):
    """Options chain access (e.g., Zerodha)."""

    async def initialize(self) -> None:
        ...

    async def fetch_options_chain(self, strikes: Optional[list[int]] = None) -> dict:
        ...
