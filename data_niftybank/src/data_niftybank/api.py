"""Public API factories for data_niftybank module.

This is the stable import surface for consumers (Engine, UI, etc).
"""
from typing import Optional

from .contracts import MarketStore, OptionsData, MarketIngestion, NewsData, MacroData
from .store import InMemoryMarketStore
from .adapters.redis_store import RedisMarketStore
from .adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
from .adapters.zerodha_ingestion import ZerodhaIngestionAdapter
from .adapters.news_adapter import NewsDataAdapter
from .adapters.macro_adapter import MacroDataAdapter
from .adapters.historical_replay import HistoricalDataReplay, LTPDataAdapter


def build_store(redis_client=None) -> MarketStore:
    """Build MarketStore (Redis-backed if client provided, else in-memory).
    
    Args:
        redis_client: Optional Redis client instance (e.g., redis.Redis())
    
    Returns:
        MarketStore instance
    
    Example:
        # In-memory for tests
        store = build_store()
        
        # Redis-backed for production
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        store = build_store(redis_client=r)
    """
    if redis_client is not None:
        return RedisMarketStore(redis_client)
    return InMemoryMarketStore()


def build_options_client(kite, fetcher) -> OptionsData:
    """Build OptionsData client (wraps Zerodha OptionsChainFetcher).
    
    Args:
        kite: KiteConnect instance
        fetcher: OptionsChainFetcher instance (from legacy data/options_chain_fetcher.py)
    
    Returns:
        OptionsData instance
    
    Example:
        from kiteconnect import KiteConnect
        from data.options_chain_fetcher import OptionsChainFetcher
        from data.market_memory import MarketMemory
        
        kite = KiteConnect(api_key="...")
        kite.set_access_token("...")
        mm = MarketMemory()
        fetcher = OptionsChainFetcher(kite, mm, "NIFTY BANK")
        
        options = build_options_client(kite, fetcher)
        await options.initialize()
        chain = await options.fetch_options_chain()
    """
    # Instrument normalization is handled by the adapter
    return ZerodhaOptionsChainAdapter(fetcher)


def build_ingestion(kite, market_memory) -> MarketIngestion:
    """Build MarketIngestion adapter (wraps legacy DataIngestionService).

    Args:
        kite: KiteConnect instance with valid access token
        market_memory: MarketMemory instance for caching

    Returns:
        MarketIngestion instance for real-time data ingestion

    Example:
        from kiteconnect import KiteConnect
        from data.market_memory import MarketMemory
        from data_niftybank.api import build_store, build_ingestion

        kite = KiteConnect(api_key="...")
        kite.set_access_token("...")
        market_memory = MarketMemory()

        store = build_store()  # or build_store(redis_client=redis_client)
        ingestion = build_ingestion(kite, market_memory)
        ingestion.bind_store(store)

        ingestion.start()  # Start WebSocket data ingestion
        # ... run trading logic ...
        ingestion.stop()   # Stop when done
    """
    ingestion = ZerodhaIngestionAdapter(kite, market_memory)
    return ingestion


def build_news_client(market_memory) -> NewsData:
    """Build NewsData client (wraps legacy NewsCollector).

    Args:
        market_memory: MarketMemory instance for caching

    Returns:
        NewsData instance for news and sentiment access

    Example:
        from data.market_memory import MarketMemory
        from data_niftybank.api import build_news_client

        market_memory = MarketMemory()
        news_client = build_news_client(market_memory)

        # Get latest news
        news = await news_client.get_latest_news("NIFTY", limit=5)

        # Get sentiment summary
        sentiment = await news_client.get_sentiment_summary("NIFTY", hours=24)
    """
    return NewsDataAdapter(market_memory)


def build_macro_client() -> MacroData:
    """Build MacroData client (wraps legacy macro data fetchers).

    Returns:
        MacroData instance for macroeconomic data access

    Example:
        from data_niftybank.api import build_macro_client

        macro_client = build_macro_client()

        # Get inflation data
        inflation = await macro_client.get_inflation_data(months=12)

        # Get RBI repo rate
        repo_rate = await macro_client.get_rbi_data("repo_rate", days=30)
    """
    return MacroDataAdapter()


def build_historical_replay(store: MarketStore, data_source: str = "synthetic") -> MarketIngestion:
    """Build historical data replay for testing.

    Args:
        store: MarketStore to write replayed data to
        data_source: "synthetic" for generated data, or path to JSON file

    Returns:
        MarketIngestion instance that replays historical data

    Example:
        from data_niftybank.api import build_store, build_historical_replay

        store = build_store()
        replay = build_historical_replay(store, data_source="synthetic")

        replay.bind_store(store)
        replay.start()  # Starts replaying synthetic market data

        # ... run tests ...

        replay.stop()
    """
    return HistoricalDataReplay(store, data_source)


def build_ltp_collector(kite, market_memory) -> MarketIngestion:
    """Build LTP data collector adapter (REST API based).

    Args:
        kite: KiteConnect instance with valid access token
        market_memory: MarketMemory instance for caching

    Returns:
        MarketIngestion instance for LTP-based data collection

    Example:
        from kiteconnect import KiteConnect
        from data.market_memory import MarketMemory
        from data_niftybank.api import build_ltp_collector

        kite = KiteConnect(api_key="...")
        kite.set_access_token("...")
        market_memory = MarketMemory()

        ltp_collector = build_ltp_collector(kite, market_memory)
        # LTP collector works on scheduled intervals, not continuous
    """
    return LTPDataAdapter(kite, market_memory)
