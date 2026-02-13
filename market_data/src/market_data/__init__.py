"""NIFTY/BANKNIFTY-focused data module (standalone)."""

from .aliases import normalize_instrument, canonical_instruments
from .contracts import (
    MarketInstrument, MarketTick, OHLCBar, MarketStore, MarketIngestion, OptionsData,
    MacroIndicator, MacroData
)
from .store import InMemoryMarketStore
from .adapters.redis_store import RedisMarketStore
try:
    from .adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
except (ImportError, KeyboardInterrupt) as e:
    if isinstance(e, KeyboardInterrupt):
        raise
    print(f"WARNING: Zerodha options chain adapter not available: {e}")
    ZerodhaOptionsChainAdapter = None
except Exception as e:
    print(f"WARNING: Zerodha options chain adapter not available: {e}")
    ZerodhaOptionsChainAdapter = None
from .adapters.historical_tick_replayer import HistoricalTickReplayer
from .adapters.unified_replayer import UnifiedHistoricalReplayer
try:
    from news_module.adapters.macro_adapter import MacroDataAdapter
except ImportError:
    # Fallback if news_module is not available
    MacroDataAdapter = None
try:
    from .technical_indicators_service import (
        TechnicalIndicators,
        TechnicalIndicatorsService,
        get_technical_service,
    )
except (ImportError, KeyboardInterrupt) as e:
    if isinstance(e, KeyboardInterrupt):
        raise
    print(f"WARNING: Technical indicators service not available: {e}")
    TechnicalIndicators = None
    TechnicalIndicatorsService = None
    get_technical_service = None
except Exception as e:
    print(f"WARNING: Technical indicators service not available: {e}")
    TechnicalIndicators = None
    TechnicalIndicatorsService = None
    get_technical_service = None
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
    "UnifiedHistoricalReplayer",
    "MacroDataAdapter",
    "TechnicalIndicators",
    "TechnicalIndicatorsService",
    "get_technical_service",
]

