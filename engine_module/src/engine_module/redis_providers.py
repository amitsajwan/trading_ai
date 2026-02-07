"""Redis-based data providers for engine_module.

Direct Redis access implementations of MarketDataProvider and TechnicalDataProvider
protocols, bypassing API calls for better performance.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Use absolute import to avoid relative import issues when run via python -c
from engine_module.contracts import TechnicalIndicators

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

        Reads from individual keys: ohlc:{symbol}:{timeframe}:{timestamp}
        Used by historical data collection and backtesting.
        """
        if not self._available:
            return []

        try:
            # Read from individual OHLC keys (same format as market data API)
            ohlc_pattern = f"ohlc:{symbol}:1min:*"
            ohlc_keys = self.redis.keys(ohlc_pattern)

            if not ohlc_keys:
                logger.warning(f"No OHLC keys found for {symbol}")
                return []

            logger.info(f"Found {len(ohlc_keys)} 1min bars for {symbol}")

            # Get OHLC data from Redis keys (newest first, then reverse for chronological order)
            ohlc_data = []
            sorted_keys = sorted(ohlc_keys, reverse=True)[:periods]  # Get latest N

            for key in sorted_keys:
                ohlc_raw = self.redis.get(key)
                if ohlc_raw:
                    try:
                        data = json.loads(ohlc_raw)
                        ohlc_data.append({
                            "instrument": data.get("instrument", symbol),
                            "timeframe": "1min",
                            "open": float(data.get("open", 0)),
                            "high": float(data.get("high", 0)),
                            "low": float(data.get("low", 0)),
                            "close": float(data.get("close", 0)),
                            "volume": int(data.get("volume", 0)),
                            "start_at": data.get("start_at", datetime.now().isoformat())
                        })
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse OHLC data from {key}: {e}")
                        continue

            # Sort by timestamp (oldest first for analysis)
            ohlc_data.sort(key=lambda x: x.get('start_at', ''))

            logger.info(f"Returning {len(ohlc_data)} parsed OHLC bars for {symbol}")
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

    async def get_technical_indicators(self, symbol: str, periods: int = 100) -> Optional[TechnicalIndicators]:
        """Get technical indicators for symbol from Redis.

        Reads from indicators:{symbol}:{indicator_name} keys created by market_data TechnicalIndicatorsService.
        Returns a TechnicalIndicators dataclass instance.

        For derivatives/futures, automatically uses core instrument volume data for accurate technical analysis.
        """
        if not self._available:
            return None

        # Determine volume source for this instrument
        volume_source = await self._get_volume_source(symbol)
        volume_symbol = await self._get_volume_symbol(symbol, volume_source)

        logger.debug(f"Fetching technical indicators for {symbol} using volume from {volume_symbol} ({volume_source})")

        try:
            # Get all indicator keys for this symbol
            pattern = f"indicators:{symbol}:*"
            keys = self.redis.keys(pattern)

            if not keys:
                logger.debug(f"No technical indicators found in Redis for {symbol}")
                return None

            # Read all indicator values from Redis
            indicator_values = {}
            for key in keys:
                try:
                    # Extract indicator name from key
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    indicator_name = key_str.split(f"indicators:{symbol}:", 1)[1]

                    # Get value
                    value_str = self.redis.get(key)
                    if value_str:
                        value = value_str.decode('utf-8') if isinstance(value_str, bytes) else value_str
                        # Try to convert to appropriate type (float for most indicators)
                        try:
                            # Try float first (most indicators are floats)
                            indicator_values[indicator_name] = float(value)
                        except ValueError:
                            # Try int
                            try:
                                indicator_values[indicator_name] = int(value)
                            except ValueError:
                                # Keep as string for non-numeric indicators
                                indicator_values[indicator_name] = value
                except Exception as e:
                    logger.debug(f"Failed to parse indicator {key}: {e}")
                    continue

            if not indicator_values:
                logger.debug(f"No valid indicator values found for {symbol}")
                return None

            # Get current price and volume from appropriate sources
            # For futures, use futures price but core instrument volume
            price_key = self.redis.get(f"price:{symbol}:latest")
            current_price = None
            if price_key:
                try:
                    price_str = price_key.decode('utf-8') if isinstance(price_key, bytes) else price_key
                    current_price = float(price_str)
                except (ValueError, TypeError):
                    pass

            # Get volume from the appropriate source
            volume_key = self.redis.get(f"volume:{volume_symbol}:latest")
            current_volume = None
            if volume_key:
                try:
                    volume_str = volume_key.decode('utf-8') if isinstance(volume_key, bytes) else volume_key
                    current_volume = int(float(volume_str))
                except (ValueError, TypeError):
                    pass

            # Map Redis keys to TechnicalIndicators fields using market_data constants
            # market_data stores indicators with standardized names like rsi_14, adx_14, etc.
            indicators = TechnicalIndicators(
                # Core indicators that should always be available
                rsi_14=indicator_values.get('rsi_14'),
                adx_14=indicator_values.get('adx_14'),
                macd_value=indicator_values.get('macd_value'),
                macd_signal=indicator_values.get('macd_signal'),
                macd_histogram=indicator_values.get('macd_histogram'),
                current_price=current_price,

                # Moving averages
                sma_10=indicator_values.get('sma_10'),
                sma_20=indicator_values.get('sma_20'),
                sma_50=indicator_values.get('sma_50'),
                ema_10=indicator_values.get('ema_10'),
                ema_12=indicator_values.get('ema_12'),
                ema_20=indicator_values.get('ema_20'),
                ema_26=indicator_values.get('ema_26'),
                ema_50=indicator_values.get('ema_50'),
                wma_20=indicator_values.get('wma_20'),

                # Momentum and oscillators
                rsi_9=indicator_values.get('rsi_9'),
                rsi_status=indicator_values.get('rsi_status'),
                stoch_k=indicator_values.get('stoch_k'),
                stoch_d=indicator_values.get('stoch_d'),
                williams_r=indicator_values.get('williams_r'),

                # Volatility
                bb_upper=indicator_values.get('bollinger_upper'),
                bb_middle=indicator_values.get('bollinger_middle'),
                bb_lower=indicator_values.get('bollinger_lower'),
                bb_width=indicator_values.get('bollinger_width'),
                bb_percent_b=indicator_values.get('bollinger_percent_b'),
                atr_14=indicator_values.get('atr_14'),
                atr_20=indicator_values.get('atr_20'),

                # Trend strength
                di_plus=indicator_values.get('di_plus'),
                di_minus=indicator_values.get('di_minus'),

                # Volume
                obv=indicator_values.get('obv'),
                volume_sma_20=indicator_values.get('volume_sma_20'),
                volume_rsi_14=indicator_values.get('volume_rsi_14'),
                cmf_20=indicator_values.get('cmf_20'),

                # Oscillators
                cci_20=indicator_values.get('cci_20'),
                mfi_14=indicator_values.get('mfi_14'),
                roc_12=indicator_values.get('roc_12'),
                momentum_10=indicator_values.get('momentum_10'),

                # Support/Resistance
                pivot_point=indicator_values.get('pivot_point'),
                pivot_r1=indicator_values.get('pivot_r1'),
                pivot_r2=indicator_values.get('pivot_r2'),
                pivot_s1=indicator_values.get('pivot_s1'),
                pivot_s2=indicator_values.get('pivot_s2'),

                # Price action
                high_20=indicator_values.get('high_20'),
                low_20=indicator_values.get('low_20'),
                range_20=indicator_values.get('range_20'),

                # Derived signals
                trend_direction=indicator_values.get('trend_direction'),
                trend_strength=indicator_values.get('trend_strength'),
                signal_strength=indicator_values.get('signal_strength'),
                volatility_level=indicator_values.get('volatility_level'),

                # Price metrics
                price_change_pct=indicator_values.get('price_change_pct'),

                # Metadata
                timestamp=indicator_values.get('timestamp', datetime.now().isoformat()),
                instrument=symbol,
                timeframe=indicator_values.get('timeframe', '1min')
            )

            logger.debug(f"Loaded {len([v for v in indicator_values.values() if v is not None])} technical indicators for {symbol} from Redis")
            return indicators

        except Exception as e:
            logger.warning(f"Failed to fetch technical indicators for {symbol}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    async def get_indicators(self, instrument: str) -> Dict[str, Any]:
        """Get technical indicators for instrument (orchestrator interface).

        Returns a dictionary of indicator values for compatibility with the orchestrator.
        """
        indicators_obj = await self.get_technical_indicators(instrument)
        if indicators_obj:
            return indicators_obj.to_dict()
        return {}

    async def _get_volume_source(self, symbol: str) -> str:
        """Determine where to get volume data for this instrument."""
        # Core instrument mapping for derivatives
        core_mapping = {
            'BANKNIFTY26JANFUT': 'BANKNIFTY',
            'BANKNIFTY27JANFUT': 'BANKNIFTY',
            'NIFTY26JANFUT': 'NIFTY',
            'NIFTY27JANFUT': 'NIFTY',
        }

        # Check if we have explicit metadata in Redis
        volume_source_key = f"instrument:{symbol}:volume_source"
        volume_source = self.redis.get(volume_source_key)
        if volume_source:
            source_str = volume_source.decode('utf-8') if isinstance(volume_source, bytes) else volume_source
            return source_str

        # Fallback to mapping logic
        if symbol.upper() in core_mapping:
            return "core"
        elif "FUT" in symbol.upper() or "CE" in symbol.upper() or "PE" in symbol.upper():
            return "core"  # Derivatives use core instrument volume
        else:
            return "direct"  # Stocks use their own volume

    async def _get_volume_symbol(self, symbol: str, volume_source: str) -> str:
        """Get the symbol to use for volume data."""
        if volume_source == "core":
            # Get core instrument from Redis metadata or mapping
            core_key = f"instrument:{symbol}:core_instrument"
            core_instrument = self.redis.get(core_key)
            if core_instrument:
                return core_instrument.decode('utf-8') if isinstance(core_instrument, bytes) else core_instrument

            # Fallback to mapping
            core_mapping = {
                'BANKNIFTY26JANFUT': 'BANKNIFTY',
                'BANKNIFTY27JANFUT': 'BANKNIFTY',
                'NIFTY26JANFUT': 'NIFTY',
                'NIFTY27JANFUT': 'NIFTY',
            }
            return core_mapping.get(symbol.upper(), symbol.upper())

        return symbol.upper()


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


class RedisNewsDataProvider:
    """Redis-based news data provider.

    Fetches news and sentiment data from Redis keys set by news_module.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:
            logger.warning("Redis unavailable for news data: %s", exc)

    async def get_latest_news(self, instrument: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest news for instrument from Redis.

        Reads from news:{instrument}:latest keys set by news_module.
        """
        if not self._available:
            return []

        try:
            # Get latest news for instrument
            news_key = f"news:{instrument}:latest"
            news_data = self.redis.get(news_key)

            if not news_data:
                logger.debug(f"No news found in Redis for {instrument}")
                return []

            # Parse JSON data
            import json
            try:
                news_list = json.loads(news_data)
                if isinstance(news_list, list):
                    return news_list[:limit]
                return []
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse news JSON for {instrument}: {e}")
                return []

        except Exception as e:
            logger.warning(f"Failed to fetch news for {instrument}: {e}")
            return []

    async def get_sentiment_score(self, instrument: str) -> float:
        """Get aggregate sentiment score for instrument from Redis.

        Reads from news:{instrument}:sentiment keys set by news_module.
        """
        if not self._available:
            return 0.0

        try:
            sentiment_key = f"news:{instrument}:sentiment"
            sentiment_data = self.redis.get(sentiment_key)

            if not sentiment_data:
                logger.debug(f"No sentiment data found in Redis for {instrument}")
                return 0.0

            # Parse sentiment score
            try:
                return float(sentiment_data.decode('utf-8') if isinstance(sentiment_data, bytes) else sentiment_data)
            except (ValueError, TypeError):
                logger.warning(f"Invalid sentiment data format for {instrument}")
                return 0.0

        except Exception as e:
            logger.warning(f"Failed to fetch sentiment for {instrument}: {e}")
            return 0.0

    async def get_news_data(self, instrument: str) -> Dict[str, Any]:
        """Get combined news and sentiment data for engine module."""
        latest_news = await self.get_latest_news(instrument)
        sentiment_score = await self.get_sentiment_score(instrument)

        return {
            "latest_news": latest_news,
            "sentiment_score": sentiment_score
        }


def build_redis_news_data_provider(redis_client) -> RedisNewsDataProvider:
    """Build Redis-based news data provider."""
    return RedisNewsDataProvider(redis_client)


class RedisFundamentalDataProvider:
    """Redis-based fundamental data provider.

    Stores and retrieves fundamental analysis data (earnings, valuation metrics, etc.)
    for instruments.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:
            logger.warning("Redis unavailable for fundamental data: %s", exc)

    async def get_fundamental_data(self, instrument: str) -> Dict[str, Any]:
        """Get fundamental data for instrument from Redis.

        Reads from fundamentals:{instrument} keys containing valuation and financial metrics.
        """
        if not self._available:
            return {}

        try:
            fundamentals_key = f"fundamentals:{instrument}"
            fundamentals_data = self.redis.get(fundamentals_key)

            if not fundamentals_data:
                logger.debug(f"No fundamental data found in Redis for {instrument}")
                return {}

            # Parse JSON data
            import json
            try:
                return json.loads(fundamentals_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse fundamental data JSON for {instrument}: {e}")
                return {}

        except Exception as e:
            logger.warning(f"Failed to fetch fundamental data for {instrument}: {e}")
            return {}


def build_redis_fundamental_data_provider(redis_client) -> RedisFundamentalDataProvider:
    """Build Redis-based fundamental data provider."""
    return RedisFundamentalDataProvider(redis_client)


class RedisMacroDataProvider:
    """Redis-based macro data provider.

    Stores and retrieves macroeconomic indicators and policy data.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:
            logger.warning("Redis unavailable for macro data: %s", exc)

    async def get_macro_data(self) -> Dict[str, Any]:
        """Get macroeconomic data from Redis.

        Reads from macro:* keys containing economic indicators.
        """
        if not self._available:
            return {}

        try:
            # Get all macro keys
            macro_keys = self.redis.keys("macro:*")

            macro_data = {}
            for key in macro_keys:
                try:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    indicator_name = key_str.split("macro:", 1)[1]

                    value_str = self.redis.get(key)
                    if value_str:
                        value = value_str.decode('utf-8') if isinstance(value_str, bytes) else value_str
                        # Try to convert to appropriate type
                        try:
                            macro_data[indicator_name] = float(value)
                        except ValueError:
                            macro_data[indicator_name] = value
                except Exception as e:
                    logger.debug(f"Failed to parse macro indicator {key}: {e}")
                    continue

            return macro_data

        except Exception as e:
            logger.warning(f"Failed to fetch macro data: {e}")
            return {}


def build_redis_macro_data_provider(redis_client) -> RedisMacroDataProvider:
    """Build Redis-based macro data provider."""
    return RedisMacroDataProvider(redis_client)