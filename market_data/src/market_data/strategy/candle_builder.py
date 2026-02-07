from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import redis

logger = logging.getLogger(__name__)


class CandleBuilder:
    """Aggregates ticks into 1-minute candles and calls strategy with indicators."""

    def __init__(self, on_candle: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], None], redis_client: Optional[Any] = None):
        self.on_candle = on_candle
        self.redis_client = redis_client
        self.current: Optional[Dict[str, Any]] = None

    def process_tick(self, tick: Dict[str, Any]) -> None:
        ts: datetime = tick.get("timestamp")
        if not ts:
            return

        minute = ts.replace(second=0, microsecond=0)
        price = tick.get("last_price")
        volume = tick.get("volume", 0) or 0
        instrument = tick.get("instrument")

        if self.current is None or self.current["minute"] != minute:
            # close previous with indicators
            if self.current:
                candle_data = {
                    "timestamp": self.current["minute"],
                    "open": self.current["open"],
                    "high": self.current["high"],
                    "low": self.current["low"],
                    "close": self.current["close"],
                    "volume": self.current["volume"],
                    "instrument": self.current["instrument"],
                }
                indicators = self._fetch_indicators(self.current["instrument"])
                self.on_candle(candle_data, indicators)

            # start new
            self.current = {
                "minute": minute,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "instrument": instrument,
            }
        else:
            # update current
            self.current["high"] = max(self.current["high"], price)
            self.current["low"] = min(self.current["low"], price)
            self.current["close"] = price
            self.current["volume"] = (self.current.get("volume", 0) or 0) + volume

    def flush(self) -> None:
        """Force close the current candle (use at shutdown)."""
        if self.current:
            candle_data = {
                "timestamp": self.current["minute"],
                "open": self.current["open"],
                "high": self.current["high"],
                "low": self.current["low"],
                "close": self.current["close"],
                "volume": self.current["volume"],
                "instrument": self.current["instrument"],
            }
            indicators = self._fetch_indicators(self.current["instrument"])
            self.on_candle(candle_data, indicators)
            self.current = None
    
    def _fetch_indicators(self, instrument: str) -> Optional[Dict[str, Any]]:
        """Fetch latest technical indicators from Redis."""
        if not self.redis_client or not instrument:
            return None
        
        try:
            key_prefix = f"indicators:{instrument.upper()}:"
            indicators = {}
            
            # Scan for all indicator keys
            for key in self.redis_client.scan_iter(match=f"{key_prefix}*"):
                indicator_name = key.decode('utf-8') if isinstance(key, bytes) else key
                indicator_name = indicator_name.replace(key_prefix, '')
                value = self.redis_client.get(key)
                if value:
                    try:
                        indicators[indicator_name] = float(value)
                    except (ValueError, TypeError):
                        indicators[indicator_name] = value.decode('utf-8') if isinstance(value, bytes) else value
            
            return indicators if indicators else None
        except Exception as e:
            logger.debug(f"Could not fetch indicators for {instrument}: {e}")
            return None
