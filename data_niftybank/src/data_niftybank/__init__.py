"""NIFTY/BANKNIFTY-focused data module (standalone)."""

from .aliases import normalize_instrument, canonical_instruments
from .contracts import (
    MarketInstrument, MarketTick, OHLCBar, MarketStore, MarketIngestion, OptionsData,
    NewsData, MacroData, NewsItem, MacroIndicator
)
from .store import InMemoryMarketStore
from .adapters.redis_store import RedisMarketStore
from .adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
from .adapters.zerodha_ingestion import ZerodhaIngestionAdapter
from .adapters.news_adapter import NewsDataAdapter
from .adapters.macro_adapter import MacroDataAdapter
from .adapters.historical_replay import HistoricalDataReplay, LTPDataAdapter

__all__ = [
    "normalize_instrument",
    "canonical_instruments",
    "MarketInstrument",
    "MarketTick",
    "OHLCBar",
    "MarketStore",
    "MarketIngestion",
    "OptionsData",
    "NewsData",
    "MacroData",
    "NewsItem",
    "MacroIndicator",
    "InMemoryMarketStore",
    "RedisMarketStore",
    "ZerodhaOptionsChainAdapter",
    "ZerodhaIngestionAdapter",
    "NewsDataAdapter",
    "MacroDataAdapter",
    "HistoricalDataReplay",
    "LTPDataAdapter",
]
