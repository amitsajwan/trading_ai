"""Redis-backed MarketStore implementation.

This adapter is a thin wrapper so we can reuse the existing Redis client
without binding to legacy settings or globals.
"""
import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Iterable, Optional

from ..contracts import MarketStore, MarketTick, OHLCBar

logger = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    # Convert datetime to ISO-8601 with timezone if present
    if dt.tzinfo is None:
        return dt.isoformat()
    return dt.isoformat()


def _serialize_tick(tick: MarketTick) -> dict:
    data = asdict(tick)
    data["timestamp"] = _iso(tick.timestamp)
    return data


def _serialize_ohlc(bar: OHLCBar) -> dict:
    data = asdict(bar)
    data["start_at"] = _iso(bar.start_at)
    return data


def _parse_tick(payload: Optional[str]) -> Optional[MarketTick]:
    if not payload:
        return None
    try:
        data = json.loads(payload)
        ts_raw = data.get("timestamp")
        ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.now()
        return MarketTick(
            instrument=data.get("instrument", ""),
            timestamp=ts,
            last_price=float(data.get("last_price", 0)),
            volume=data.get("volume"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse tick from redis: %s", exc)
        return None


def _parse_ohlc(payload: str) -> Optional[OHLCBar]:
    try:
        data = json.loads(payload)
        ts_raw = data.get("start_at") or data.get("timestamp")
        ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.now()
        return OHLCBar(
            instrument=data.get("instrument", ""),
            timeframe=data.get("timeframe", ""),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=data.get("volume"),
            start_at=ts,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse ohlc from redis: %s", exc)
        return None


class RedisMarketStore(MarketStore):
    """Redis-backed MarketStore (no global config)."""

    def __init__(
        self,
        redis_client,
        *,
        tick_ttl_hours: int = 24,
        price_ttl_seconds: int = 300,
        ohlc_ttl_hours: int = 24,
    ):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable: %s", exc)
        self._tick_ttl = int(timedelta(hours=tick_ttl_hours).total_seconds())
        self._price_ttl = int(price_ttl_seconds)
        self._ohlc_ttl = int(timedelta(hours=ohlc_ttl_hours).total_seconds())

    def store_tick(self, tick: MarketTick) -> None:
        if not self._available:
            return
        payload = _serialize_tick(tick)
        ts_key = _iso(tick.timestamp)
        try:
            self.redis.setex(f"tick:{tick.instrument}:{ts_key}", self._tick_ttl, json.dumps(payload))
            # Also store latest tick blob and price for quick lookup
            self.redis.setex(f"tick:{tick.instrument}:latest", self._tick_ttl, json.dumps(payload))
            self.redis.setex(f"price:{tick.instrument}:latest", self._price_ttl, str(tick.last_price))
            self.redis.setex(f"price:{tick.instrument}:latest_ts", self._price_ttl, ts_key)
            if tick.volume is not None:
                self.redis.setex(f"volume:{tick.instrument}:latest", self._price_ttl, str(tick.volume))
        except Exception as exc:  # noqa: BLE001
            logger.error("Error storing tick: %s", exc, exc_info=True)

    def get_latest_tick(self, instrument: str) -> Optional[MarketTick]:
        if not self._available:
            return None
        try:
            payload = self.redis.get(f"tick:{instrument}:latest")
            return _parse_tick(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error reading latest tick: %s", exc)
            return None

    def store_ohlc(self, bar: OHLCBar) -> None:
        if not self._available:
            return
        payload = _serialize_ohlc(bar)
        key = f"ohlc:{bar.instrument}:{bar.timeframe}:{payload.get('start_at')}"
        try:
            self.redis.setex(key, self._ohlc_ttl, json.dumps(payload))
            sorted_key = f"ohlc_sorted:{bar.instrument}:{bar.timeframe}"
            score = bar.start_at.timestamp()
            self.redis.zadd(sorted_key, {json.dumps(payload): float(score)})
            cutoff = float((datetime.now() - timedelta(seconds=self._ohlc_ttl)).timestamp())
            self.redis.zremrangebyscore(sorted_key, 0, cutoff)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error storing ohlc: %s", exc, exc_info=True)

    def get_ohlc(self, instrument: str, timeframe: str, limit: int = 100) -> Iterable[OHLCBar]:
        if not self._available:
            return []
        sorted_key = f"ohlc_sorted:{instrument}:{timeframe}"
        try:
            results = self.redis.zrange(sorted_key, -limit, -1) if limit > 0 else self.redis.zrange(sorted_key, 0, -1)
            bars = []
            for payload in results:
                bar = _parse_ohlc(payload)
                if bar:
                    bars.append(bar)
            return bars
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error reading ohlc: %s", exc)
            return []
