"""NIFTY/BANKNIFTY-focused data module (standalone)."""

from .aliases import normalize_instrument, canonical_instruments
from .contracts import (
    MarketInstrument, MarketTick, OHLCBar, MarketStore, MarketIngestion, OptionsData
)
from .store import InMemoryMarketStore
from .adapters.redis_store import RedisMarketStore
from .adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
from .adapters.historical_tick_replayer import HistoricalTickReplayer
from .technical_indicators_service import (
    TechnicalIndicators,
    TechnicalIndicatorsService,
    get_technical_service
)
from .technical_indicators_constants import *

__all__ = [
    "normalize_instrument",
    "canonical_instruments",
    "MarketInstrument",
    "MarketTick",
    "OHLCBar",
    "MarketStore",
    "MarketIngestion",
    "OptionsData",
    "MacroData",
    "MacroIndicator",
    "InMemoryMarketStore",
    "RedisMarketStore",
    "ZerodhaOptionsChainAdapter",
    "HistoricalTickReplayer",
    "MacroDataAdapter",
    "TechnicalIndicators",
    "TechnicalIndicatorsService",
    "get_technical_service",
]

