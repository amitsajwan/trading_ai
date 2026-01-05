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
    """Simple tick payload for the latest price."""

    instrument: str
    timestamp: datetime
    last_price: float
    volume: Optional[int] = None


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


@dataclass
class NewsItem:
    """News article with sentiment analysis."""

    title: str
    content: str
    source: str
    published_at: datetime
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None


class NewsData(Protocol):
    """News and sentiment data access."""

    async def get_latest_news(self, instrument: str, limit: int = 10) -> list[NewsItem]:
        ...

    async def get_sentiment_summary(self, instrument: str, hours: int = 24) -> dict:
        ...


@dataclass
class MacroIndicator:
    """Macroeconomic indicator data."""

    name: str
    value: float
    unit: str
    timestamp: datetime
    source: str


class MacroData(Protocol):
    """Macroeconomic data access (RBI, inflation, etc.)."""

    async def get_inflation_data(self, months: int = 12) -> list[MacroIndicator]:
        ...

    async def get_rbi_data(self, indicator: str, days: int = 30) -> list[MacroIndicator]:
        ...