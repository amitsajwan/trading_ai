"""Public API factories for market_data module.

This is the stable import surface for consumers (Engine, UI, etc).
"""
from typing import Optional
from datetime import datetime

from .contracts import MarketStore, OptionsData, MarketIngestion
from .store import InMemoryMarketStore
from .adapters.redis_store import RedisMarketStore
from .adapters.historical_tick_replayer import HistoricalTickReplayer


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


def build_historical_replay(store: MarketStore, data_source: str = "synthetic", start_date: Optional[datetime] = None, kite=None) -> MarketIngestion:
    """Build historical data replay for testing/backtesting.

    Args:
        store: MarketStore to write replayed data to
        data_source: "synthetic" for generated data, "zerodha" for real historical data
        start_date: datetime to start replay from (defaults to 9:15 AM IST)
        kite: KiteConnect instance (required for zerodha data_source)

    Returns:
        MarketIngestion instance that replays historical data in real-time

    Example:
        from market_data.api import build_store, build_historical_replay
        from datetime import datetime, date

        store = build_store()
        # Historical replay from specific date
        start = datetime.combine(date.today(), datetime.min.time().replace(hour=9, minute=15))
        replay = build_historical_replay(store, data_source="zerodha", start_date=start, kite=kite)

        replay.start()  # Starts replaying from 9:15, appears real-time
        # ... run backtesting ...

        replay.stop()
    """
    if data_source == "zerodha" and kite:
        # Use real Zerodha historical data
        if start_date:
            # User specified a specific date - fetch data for that date only
            to_date = start_date.date()
            from_date = to_date  # Same day
        else:
            # No specific date - fallback to last 7 days
            from dateutil.relativedelta import relativedelta
            to_date = datetime.now().date()
            from_date = to_date - relativedelta(days=7)

        replayer = HistoricalTickReplayer(
            store=store,
            data_source="zerodha",
            kite=kite,
            instrument_symbol="BANKNIFTY",  # Use BANKNIFTY for futures (not "NIFTY BANK" for index)
            from_date=from_date,
            to_date=to_date,
            interval="minute",
            rebase=False,  # Don't rebase historical data - keep original timestamps
            speed=10.0  # Use speed=10.0 to avoid instant replay issues with large datasets
        )
        return replayer
    else:
        # Fallback to synthetic data
        return HistoricalTickReplayer(
            store=store,
            data_source="synthetic",
            rebase=True,
            rebase_to=start_date or datetime.now(),
            speed=1.0
        )


def build_options_client(kite=None, fetcher=None) -> OptionsData:
    """Build OptionsData client for options chain access.
    
    Args:
        kite: KiteConnect instance (optional)
        fetcher: Legacy OptionsChainFetcher instance (optional)
    
    Returns:
        OptionsData instance
    
    Example:
        from kiteconnect import KiteConnect
        from data.options_chain_fetcher import OptionsChainFetcher
        
        kite = KiteConnect(api_key="...")
        fetcher = OptionsChainFetcher()
        options = build_options_client(kite=kite, fetcher=fetcher)
        
        await options.initialize()
        chain = await options.fetch_options_chain()
    """
    from .adapters.mock_options_chain import MockOptionsChainAdapter
    return MockOptionsChainAdapter(kite=kite)

