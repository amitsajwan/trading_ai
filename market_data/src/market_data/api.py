"""Public API factories for market_data module.

This is the stable import surface for consumers (Engine, UI, etc).
"""
import os
from typing import Optional
from datetime import datetime

from .contracts import MarketStore, OptionsData, MarketIngestion
from .store import InMemoryMarketStore
from .adapters.redis_store import RedisMarketStore
from .adapters.unified_replayer import UnifiedHistoricalReplayer


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


def build_historical_replay(store: MarketStore, data_source: str = "synthetic", start_date: Optional[datetime] = None, kite=None, speed: Optional[float] = None, instrument_symbol: Optional[str] = None) -> MarketIngestion:
    """Build historical data replay for testing/backtesting.

    Args:
        store: MarketStore to write replayed data to
        data_source: "synthetic" for generated data, "zerodha" for real historical data
        start_date: datetime to start replay from (defaults to 9:15 AM IST)
        kite: KiteConnect instance (required for zerodha data_source)
        speed: Replay speed multiplier (0.0 = instant, 1.0 = real-time, 10.0 = 10x speed)
        instrument_symbol: Trading instrument symbol (defaults to INSTRUMENT_SYMBOL env var)

    Returns:
        MarketIngestion instance that replays historical data in real-time

    Example:
        from market_data.api import build_store, build_historical_replay
        from datetime import datetime, date

        store = build_store()
        # Historical replay from specific date
        start = datetime.combine(date.today(), datetime.min.time().replace(hour=9, minute=15))
        replay = build_historical_replay(store, data_source="zerodha", start_date=start, kite=kite, speed=10.0)

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

        replayer = UnifiedHistoricalReplayer(
            store=store,
            data_source="zerodha",
            kite=kite,
            instrument_symbol=instrument_symbol or os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26JANFUT"),  # Use configured instrument
            from_date=from_date,
            to_date=to_date,
            interval="minute",
            rebase=False,  # Don't rebase historical data - keep original timestamps
            speed=speed  # Use provided speed parameter
        )
        return replayer
    else:
        # Preserve provided data_source (may be 'synthetic' or a path to a file)
        if data_source == "synthetic":
            replay_speed = 1.0 if speed is None else float(speed)
            return UnifiedHistoricalReplayer(
                store=store,
                data_source="synthetic",
                instrument_symbol=instrument_symbol or os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26JANFUT"),
                rebase=True,
                rebase_to=start_date or datetime.now(),
                speed=replay_speed
            )
        else:
            # Treat as a file path or explicit data source
            replay_speed = 10.0 if speed is None else float(speed)
            return UnifiedHistoricalReplayer(
                store=store,
                data_source=data_source,
                instrument_symbol=instrument_symbol or os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26JANFUT"),
                rebase=False,
                rebase_to=start_date or datetime.now(),
                speed=replay_speed
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
    from .adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
    # If a legacy fetcher is provided (tests or alternate implementation), prefer it
    if fetcher is not None:
        return fetcher

    return ZerodhaOptionsChainAdapter(kite=kite)

