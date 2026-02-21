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
from .env_settings import redis_config, resolve_instrument_symbol


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


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
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )
        store = build_store(redis_client=r)
    """
    if redis_client is not None:
        return RedisMarketStore(redis_client)

    # Use environment variables for Redis connection when available.
    # For isolated tests/dev where Redis is not running, gracefully fall back
    # to in-memory storage.
    try:
        import redis
        r = redis.Redis(**redis_config(decode_responses=True))
        r.ping()
        return RedisMarketStore(r)
    except Exception:
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
    if data_source == "zerodha" and not kite:
        raise ValueError(
            "Zerodha historical replay requested but no KiteConnect instance was provided. "
            "This is a real-only mode: install kiteconnect and provide valid credentials/token."
        )

    use_virtual_time = _env_bool("USE_VIRTUAL_TIME", False)
    default_rebase_to_now = (data_source in ("synthetic", "local"))
    rebase_to_now = _env_bool("HISTORICAL_REBASE_TO_NOW", default_rebase_to_now)

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
            instrument_symbol=instrument_symbol or resolve_instrument_symbol(),  # Use configured instrument
            from_date=from_date,
            to_date=to_date,
            interval="minute",
            rebase=(rebase_to_now and not use_virtual_time),
            speed=speed  # Use provided speed parameter
        )
        return replayer
    else:
        # Preserve provided data_source (may be 'synthetic' or a path to a file)
        if data_source == "synthetic":
            replay_speed = 1.0 if speed is None else float(speed)
            should_rebase = (rebase_to_now and not use_virtual_time)
            # When rebasing, keep replay target at "now" while allowing start_date
            # to remain a data anchor (used by the synthetic generator seed).
            rebase_target = datetime.now() if should_rebase else (start_date or datetime.now())
            return UnifiedHistoricalReplayer(
                store=store,
                data_source="synthetic",
                instrument_symbol=instrument_symbol or resolve_instrument_symbol(),
                rebase=should_rebase,
                rebase_to=rebase_target,
                start_date=start_date,
                speed=replay_speed
            )
        else:
            # Treat as a file path or explicit data source
            replay_speed = (1.0 if data_source == "local" else 10.0) if speed is None else float(speed)
            return UnifiedHistoricalReplayer(
                store=store,
                data_source=data_source,
                instrument_symbol=instrument_symbol or resolve_instrument_symbol(),
                rebase=(rebase_to_now and not use_virtual_time),
                rebase_to=start_date or datetime.now(),
                speed=replay_speed,
                start_date=start_date,
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

