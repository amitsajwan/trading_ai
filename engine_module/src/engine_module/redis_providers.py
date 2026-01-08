"""Redis-based data providers for engine_module.

Direct Redis access implementations of MarketDataProvider and TechnicalDataProvider
protocols, bypassing API calls for better performance.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RedisMarketDataProvider:
    """Redis-based market data provider that reads OHLC data directly from Redis.

    This provider implements the MarketDataProvider protocol by reading from
    the Redis keys used by market_data collectors.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:
            logger.warning("Redis unavailable for market data: %s", exc)

    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        """Get OHLC data for symbol from Redis.

        Reads from the sorted set: ohlc_sorted:{symbol}:{timeframe}
        Tries 15min first, then falls back to 5min, then 1min
        """
        if not self._available:
            return []

        try:
            # Try different timeframes in order of preference
            timeframes = ['15min', '5min', '1min']
            ohlc_data = []

            for timeframe in timeframes:
                sorted_key = f"ohlc_sorted:{symbol}:{timeframe}"
                results = self.redis.zrange(sorted_key, -periods, -1) if periods > 0 else self.redis.zrange(sorted_key, 0, -1)

                if results:
                    logger.info(f"Found {len(results)} {timeframe} bars for {symbol}")
                    for payload in results:
                        try:
                            data = json.loads(payload)
                            ohlc_data.append({
                                "instrument": data.get("instrument", symbol),
                                "timeframe": data.get("timeframe", timeframe),
                                "open": float(data.get("open", 0)),
                                "high": float(data.get("high", 0)),
                                "low": float(data.get("low", 0)),
                                "close": float(data.get("close", 0)),
                                "volume": int(data.get("volume", 0)),
                                "start_at": data.get("start_at", datetime.now().isoformat())
                            })
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(f"Failed to parse OHLC data: {e}")
                            continue

                    # If we found data, use this timeframe
                    if ohlc_data:
                        break

            return ohlc_data

        except Exception as e:
            logger.warning(f"Failed to fetch OHLC data for {symbol}: {e}")
            return []


class RedisTechnicalDataProvider:
    """Redis-based technical indicators provider.

    Reads technical indicators directly from Redis keys set by the
    TechnicalIndicatorsService.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:
            logger.warning("Redis unavailable for technical data: %s", exc)

    async def get_technical_indicators(self, symbol: str, periods: int = 100) -> Optional[Dict[str, Any]]:
        """Get technical indicators for symbol from Redis.

        Reads from indicators:{symbol}:{indicator_name} keys
        """
        if not self._available:
            return None

        try:
            # Get all indicator keys for this symbol
            pattern = f"indicators:{symbol}:*"
            keys = self.redis.keys(pattern)

            if not keys:
                return None

            indicators = {}
            for key in keys:
                try:
                    # Extract indicator name from key
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    indicator_name = key_str.split(f"indicators:{symbol}:", 1)[1]

                    # Get value
                    value_str = self.redis.get(key)
                    if value_str:
                        value = value_str.decode('utf-8') if isinstance(value_str, bytes) else value_str
                        # Try to convert to appropriate type
                        try:
                            # Try float first
                            indicators[indicator_name] = float(value)
                        except ValueError:
                            # Try int
                            try:
                                indicators[indicator_name] = int(value)
                            except ValueError:
                                # Keep as string
                                indicators[indicator_name] = value
                except Exception as e:
                    logger.warning(f"Failed to parse indicator {key}: {e}")
                    continue

            # Add metadata
            indicators.update({
                "timestamp": datetime.now().isoformat(),
                "instrument": symbol,
                "current_price": indicators.get("current_price", 0),
                "timeframe": "1min"
            })

            return indicators

        except Exception as e:
            logger.warning(f"Failed to fetch technical indicators for {symbol}: {e}")
            return None


class RedisOptionsDataProvider:
    """Redis-based options data provider.

    This is a placeholder - options data might need API calls to Zerodha
    since it's not typically stored in Redis long-term.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def fetch_chain(self, instrument: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        """Fetch options chain - placeholder implementation.

        For now, returns empty data. In production, this might need to call
        Zerodha API or read from a cached options store.
        """
        logger.warning(f"RedisOptionsDataProvider not fully implemented for {instrument}")
        return {
            "instrument": instrument,
            "expiries": [],
            "calls": [],
            "puts": [],
            "underlying_price": 0,
            "pcr": 0.0,
            "max_pain": 0
        }


# Factory functions for easy integration
def build_redis_market_data_provider(redis_client) -> RedisMarketDataProvider:
    """Build Redis-based market data provider."""
    return RedisMarketDataProvider(redis_client)


def build_redis_technical_data_provider(redis_client) -> RedisTechnicalDataProvider:
    """Build Redis-based technical data provider."""
    return RedisTechnicalDataProvider(redis_client)


def build_redis_options_data_provider(redis_client) -> RedisOptionsDataProvider:
    """Build Redis-based options data provider."""
    return RedisOptionsDataProvider(redis_client)