from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date
from typing import Optional, Any

import redis

try:
    from kiteconnect import KiteConnect
except ImportError:  # pragma: no cover - optional in some environments
    KiteConnect = None

from market_data.api import build_store
from market_data.adapters.historical_tick_replayer import HistoricalTickReplayer
from market_data.strategy.base import Strategy

logger = logging.getLogger(__name__)


def _load_kite_credentials() -> tuple[Optional[str], Optional[str]]:
    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")

    if api_key and access_token:
        return api_key, access_token

    cred_paths = [
        os.path.join(os.getcwd(), "credentials.json"),
        os.path.join(os.getcwd(), "credentials.example.json"),
    ]
    for path in cred_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("api_key"), data.get("access_token")
            except Exception as e:  # pragma: no cover
                logger.warning(f"Failed reading credentials from {path}: {e}")
    return None, None


def _build_kite() -> Any:  # Returns KiteConnect instance or None
    if KiteConnect is None:
        logger.warning("kiteconnect not installed; live/historical Zerodha fetch will be unavailable")
        return None
    api_key, access_token = _load_kite_credentials()
    if not api_key or not access_token:
        logger.warning("Kite credentials not found; set KITE_API_KEY and KITE_ACCESS_TOKEN")
        return None
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


class StrategyRunner:
    """Run a Strategy in backtest/replay/live modes with the existing infra."""

    def __init__(self, redis_host: str | None = None, redis_port: int | None = None):
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(redis_port or os.getenv("REDIS_PORT", "6379"))

    async def run_backtest(
        self,
        strategy: Strategy,
        instrument: str,
        backtest_date: date,
        interval: str = "minute",
        data_source: str = "zerodha",
        speed: float = 0.0,
    ) -> None:
        """Run a backtest/replay for a single date using HistoricalTickReplayer.
        
        Technical indicators are automatically calculated by TechnicalIndicatorsService
        and passed to strategy.on_new_candle().
        """

        r = redis.Redis(host=self.redis_host, port=self.redis_port, db=0, decode_responses=True)
        store = build_store(redis_client=r)

        kite = _build_kite() if data_source == "zerodha" else None

        # Create wrapper that passes indicators to strategy
        def candle_callback_with_indicators(candle, indicators=None):
            strategy.on_new_candle(candle, indicators)

        replayer = HistoricalTickReplayer(
            store=store,
            data_source=data_source,
            speed=speed,
            on_tick_callback=getattr(strategy, "on_tick", None),
            on_candle_callback=candle_callback_with_indicators,
            kite=kite,
            instrument_symbol=instrument,
            from_date=backtest_date,
            to_date=backtest_date,
            interval=interval,
        )

        replayer.start()
        if replayer.task:
            try:
                await replayer.task
            finally:
                replayer.stop()

    def run_backtest_sync(
        self,
        strategy: Strategy,
        instrument: str,
        backtest_date: date,
        interval: str = "minute",
        data_source: str = "zerodha",
        speed: float = 0.0,
    ) -> None:
        """Sync helper for quick runs."""

        asyncio.run(
            self.run_backtest(
                strategy=strategy,
                instrument=instrument,
                backtest_date=backtest_date,
                interval=interval,
                data_source=data_source,
                speed=speed,
            )
        )

    # Placeholder for future live-mode wiring using Redis/WebSocket feed
    async def run_live(self, strategy: Strategy, instrument: str):  # pragma: no cover
        raise NotImplementedError("Live runner will subscribe to Redis/WebSocket candles")
