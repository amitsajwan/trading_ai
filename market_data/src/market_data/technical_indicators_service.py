"""Real-time Technical Indicators Service using Pandas.

This service calculates comprehensive technical indicators using pandas and pandas-ta
on historical OHLC data. Provides real-time indicators that traders actually use.

Architecture:
    OHLC Candles → Pandas DataFrame → Technical Calculations → Store in Redis
    Agent Analysis → get_indicators() → Read latest indicators

Indicators calculated:
    - Moving Averages: SMA, EMA, WMA
    - Momentum: RSI, MACD, Stochastic
    - Volatility: Bollinger Bands, ATR
    - Trend: ADX, Ichimoku
    - Volume: OBV, Volume RSI
"""

import logging
import math
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from collections import deque
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
import redis

# Import standardized indicator names
from .technical_indicators_constants import *
from .timestamp_utils import (
    create_canonical_timestamp_payload,
    create_mode_aware_payload,
    get_instrument_channel,
    get_market_time
)

logger = logging.getLogger(__name__)


@dataclass
class TechnicalIndicators:
    """Comprehensive technical indicators used by professional traders."""

    # Metadata
    timestamp: str
    instrument: str
    current_price: float
    timeframe: str = "1min"

    # === TREND INDICATORS ===
    # Moving Averages
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_10: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    wma_20: Optional[float] = None

    # === MOMENTUM INDICATORS ===
    rsi_14: Optional[float] = None
    rsi_9: Optional[float] = None  # Shorter RSI for scalping
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    williams_r: Optional[float] = None

    # MACD
    macd_value: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None

    # === VOLATILITY INDICATORS ===
    # Bollinger Bands
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_width: Optional[float] = None
    bollinger_percent_b: Optional[float] = None

    # ATR (Average True Range)
    atr_14: Optional[float] = None
    atr_20: Optional[float] = None

    # === TREND STRENGTH ===
    adx_14: Optional[float] = None
    di_plus: Optional[float] = None
    di_minus: Optional[float] = None

    # Ichimoku Cloud
    ichimoku_tenkan: Optional[float] = None
    ichimoku_kijun: Optional[float] = None
    ichimoku_senkou_a: Optional[float] = None
    ichimoku_senkou_b: Optional[float] = None

    # === VOLUME INDICATORS ===
    obv: Optional[float] = None
    volume_sma_20: Optional[float] = None
    volume_rsi_14: Optional[float] = None
    cmf_20: Optional[float] = None  # Chaikin Money Flow
    oi: Optional[float] = None
    oi_change: Optional[float] = None
    oi_pct_change: Optional[float] = None
    oi_sma_5: Optional[float] = None
    oi_ema_10: Optional[float] = None
    oi_momentum_5: Optional[float] = None

    # === OSCILLATORS ===
    cci_20: Optional[float] = None  # Commodity Channel Index
    mfi_14: Optional[float] = None  # Money Flow Index
    roc_12: Optional[float] = None  # Rate of Change
    momentum_10: Optional[float] = None

    # === SUPPORT/RESISTANCE ===
    pivot_point: Optional[float] = None
    pivot_r1: Optional[float] = None
    pivot_r2: Optional[float] = None
    pivot_s1: Optional[float] = None
    pivot_s2: Optional[float] = None

    # === PRICE ACTION ===
    high_20: Optional[float] = None  # 20-period high
    low_20: Optional[float] = None   # 20-period low
    range_20: Optional[float] = None # 20-period range

    # === DERIVED SIGNALS ===
    signal_strength: Optional[float] = None  # Composite signal (0-100)
    volume_ratio: Optional[float] = None
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    trend_direction: str = "SIDEWAYS"  # UP, DOWN, SIDEWAYS
    trend_strength: float = 0.0  # 0-100
    rsi_status: str = "NEUTRAL"  # OVERSOLD, OVERBOUGHT, NEUTRAL
    volatility_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json
        return json.dumps(self.to_dict(), default=str)


class TechnicalIndicatorsService:
    """Pandas-based technical indicators calculation service for professional traders.

    This service uses pandas and pandas-ta to calculate comprehensive technical indicators
    on OHLC data. Maintains rolling windows of data for real-time indicator calculation.
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        window_size: int = 200,
        mode: str = "LIVE",
        run_id: Optional[str] = None
    ):
        """Initialize technical indicators service.

        Args:
            redis_client: Redis client for caching indicators
            window_size: Number of candles to maintain for calculations (default 200 for robust indicators)
            mode: Execution mode ("LIVE", "PAPER", "BACKTEST")
            run_id: Run identifier (required for BACKTEST mode)
        """
        self.redis_client = redis_client
        self.window_size = window_size
        self._mode = mode
        self._run_id = run_id

        # Single timeframe data (backward compatibility)
        self._ohlc_data: Dict[str, pd.DataFrame] = {}  # instrument -> OHLC DataFrame
        self._data_windows: Dict[str, deque] = {}  # instrument -> deque of ticks (for tick-based updates)
        self._latest_indicators: Dict[str, TechnicalIndicators] = {}
        # Multi-timeframe data (new)
        self._ohlc_data_mtf: Dict[tuple, pd.DataFrame] = {}  # (instrument, timeframe) -> OHLC DataFrame
        self._indicators_mtf: Dict[tuple, TechnicalIndicators] = {}  # (instrument, timeframe) -> Indicators
        # Deduplication: track last published payload hash to prevent duplicate publishes
        self._last_published_hash: Dict[str, str] = {}  # instrument -> hash of last published payload

    def _json_safe_value(self, value):
        """Convert value to JSON-safe format, handling Infinity and NaN."""
        if isinstance(value, float):
            if math.isinf(value):
                return None  # Convert infinity to null
            if math.isnan(value):
                return None  # Convert NaN to null
        return value

    def _json_safe_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make dictionary JSON-safe by handling special float values."""
        return {key: self._json_safe_value(value) for key, value in data.items()}

    def initialize_with_ohlc_data(self, instrument: str, ohlc_bars: List[Dict[str, Any]]) -> None:
        """Initialize technical indicators with existing OHLC data.
        
        Args:
            instrument: Instrument symbol
            ohlc_bars: List of OHLC bar dictionaries
        """
        if not ohlc_bars:
            return
            
        # Initialize DataFrame if needed
        if instrument not in self._ohlc_data:
            self._ohlc_data[instrument] = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])

        # Add all bars to DataFrame
        for bar in ohlc_bars[-self.window_size:]:  # Keep only recent bars
            new_row = {
                'timestamp': pd.to_datetime(bar.get('start_at') or bar.get('timestamp')),
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar.get('volume', 0),
                'oi': bar.get('oi')
            }
            self._ohlc_data[instrument].loc[len(self._ohlc_data[instrument])] = new_row

        # Calculate indicators with the loaded data
        if len(self._ohlc_data[instrument]) >= 14:  # Minimum for basic indicators
            indicators = self._calculate_all_indicators(instrument)
            self._latest_indicators[instrument] = indicators
            
            # Cache and publish to Redis if available
            if self.redis_client:
                try:
                    indicators_dict = asdict(indicators)
                    # Store using standardized Redis keys
                    for key, value in indicators_dict.items():
                        if value is not None and key in ALL_INDICATORS:
                            redis_key = get_indicator_redis_key(instrument, key, indicators.timeframe)
                            self.redis_client.setex(redis_key, 300, str(value))

                    # Publish full indicator set (including OI metrics) to Redis pub/sub for WS bridge
                    try:
                        import json
                        pub = self._json_safe_dict(indicators_dict)
                        pub = {k: v for k, v in pub.items() if v is not None}

                        # Add canonical timestamps
                        timestamp_payload = create_canonical_timestamp_payload(
                            market_timestamp=get_market_time(),
                            indicator_timestamp=get_market_time()
                        )
                        pub.update(timestamp_payload)

                        # Add mode/run metadata
                        mode_payload = create_mode_aware_payload(
                            mode=self._mode,
                            run_id=self._run_id,
                            instrument=instrument,
                            timeframe=indicators.timeframe,
                        )
                        pub.update(mode_payload)

                        type_specific_channel = get_instrument_channel(instrument, "indicators")
                        self.redis_client.publish(type_specific_channel, json.dumps(pub))
                    except Exception as pub_err:
                        logger.debug(f"Failed to publish indicators to Redis: {pub_err}")
                except Exception as e:
                    logger.warning(f"Failed to cache indicators in Redis: {e}")
        
    def update_tick(self, instrument: str, tick: Dict[str, Any]) -> TechnicalIndicators:
        """Update indicators based on new market tick.

        Now publishes indicators on every tick for real-time UI updates.
        Indicators are calculated using available tick data within the current candle.

        Args:
            instrument: Instrument symbol (e.g., "BANKNIFTY")
            tick: Tick data with last_price, volume, timestamp

        Returns:
            Updated TechnicalIndicators object
        """
        # Initialize window if needed
        if instrument not in self._data_windows:
            self._data_windows[instrument] = deque(maxlen=self.window_size)

        # Add tick to window (will be used for next candle)
        # For real-time, we aggregate ticks into candles
        # For now, assume tick represents a completed candle
        self._data_windows[instrument].append(tick)

        # Calculate indicators
        indicators = self._calculate_all_indicators(instrument)

        # Update timestamp to use tick timestamp
        tick_timestamp = tick.get('timestamp') or tick.get('ts') or datetime.now().isoformat()
        if isinstance(tick_timestamp, str):
            try:
                # Try to parse timestamp, fallback to now if parsing fails
                parsed_ts = pd.to_datetime(tick_timestamp)
                indicators.timestamp = parsed_ts.isoformat()
            except Exception:
                indicators.timestamp = datetime.now().isoformat()
        else:
            indicators.timestamp = tick_timestamp.isoformat() if hasattr(tick_timestamp, 'isoformat') else datetime.now().isoformat()

        # Store latest (for get_indicators() API calls)
        self._latest_indicators[instrument] = indicators

        # Cache and publish to Redis if available (now on every tick for real-time updates)
        if self.redis_client:
            try:
                indicators_dict = asdict(indicators)
                # Store using standardized Redis keys
                for key, value in indicators_dict.items():
                    if value is not None and key in ALL_INDICATORS:
                        redis_key = get_indicator_redis_key(instrument, key, indicators.timeframe)
                        self.redis_client.setex(redis_key, 300, str(value))

                # Publish standardized complete payload (now on every tick for real-time UI)
                try:
                    import json
                    import hashlib

                    # Create complete, standardized payload with all indicators
                    pub = self._json_safe_dict(indicators_dict)
                    # Remove None values
                    pub = {k: v for k, v in pub.items() if v is not None}

                    # Add intrabar flags to distinguish from candle-close updates
                    pub.update({
                        "intrabar": True,        # Indicates this is calculated from ticks within current candle
                        "candle_closed": False,  # False for tick updates, True for candle-close updates
                        "update_type": "tick"    # "tick" or "candle" to distinguish source
                    })

                    # Add canonical timestamps using tick timestamp
                    tick_ts = pd.to_datetime(tick_timestamp) if isinstance(tick_timestamp, str) else tick_timestamp
                    if isinstance(tick_ts, pd.Timestamp):
                        tick_ts = tick_ts.to_pydatetime()

                    # For tick updates, both market and indicator timestamps use tick time
                    timestamp_payload = create_canonical_timestamp_payload(
                        market_timestamp=tick_ts,
                        indicator_timestamp=tick_ts
                    )
                    pub.update(timestamp_payload)

                    # Deduplication with shorter window for tick updates (allow more frequent updates)
                    payload_str = json.dumps(pub, sort_keys=True)
                    payload_hash = hashlib.md5(payload_str.encode()).hexdigest()

                    last_hash = self._last_published_hash.get(instrument)
                    if last_hash == payload_hash:
                        # Identical payload - skip publishing to prevent duplicates
                        logger.debug(f"Skipping duplicate indicator publish for {instrument}")
                        return indicators

                    # Update last published hash
                    self._last_published_hash[instrument] = payload_hash

                    # Add mode-aware payload to ALL messages
                    mode_payload = create_mode_aware_payload(
                        mode=self._mode,
                        run_id=self._run_id,
                        instrument=instrument,
                        timeframe="1min"
                    )
                    pub.update(mode_payload)

                    # Update payload_str with mode info
                    payload_str = json.dumps(pub, sort_keys=True)

                    # Publish to type-specific channel
                    type_specific_channel = get_instrument_channel(instrument, "indicators")
                    self.redis_client.publish(type_specific_channel, payload_str)
                    logger.debug(f"Published intrabar indicators for {instrument} on tick update")
                except Exception as pub_err:
                    logger.debug(f"Failed to publish intrabar indicators to Redis: {pub_err}")
            except Exception as e:
                logger.warning(f"Failed to cache indicators in Redis: {e}")

        return indicators
    
    def update_candle(self, instrument: str, candle: Dict[str, Any]) -> TechnicalIndicators:
        """Update indicators based on new OHLC candle using pandas.

        Publishes indicators to Redis pub/sub when candles close, providing stable indicator values.
        (Indicators are also published on every tick via update_tick() for real-time UI updates)

        Args:
            instrument: Instrument symbol
            candle: OHLC data with open, high, low, close, volume, timestamp/start_at

        Returns:
            Updated TechnicalIndicators object
        """
        # Parse candle timestamp (use virtual time from candle, not current time)
        candle_timestamp = None
        if isinstance(candle.get('start_at'), str):
            candle_timestamp = pd.to_datetime(candle['start_at'])
        elif isinstance(candle.get('timestamp'), str):
            candle_timestamp = pd.to_datetime(candle['timestamp'])
        elif candle.get('start_at'):
            candle_timestamp = pd.to_datetime(candle['start_at'])
        else:
            # Fallback to virtual time if available, otherwise current time
            candle_timestamp = pd.to_datetime(get_market_time())
        
        # Initialize DataFrame if needed
        if instrument not in self._ohlc_data:
            self._ohlc_data[instrument] = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])

        # Add new candle to DataFrame
        new_row = {
            'timestamp': candle_timestamp,
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle.get('volume', 0),
            'oi': candle.get('oi')
        }

        # Append to DataFrame and maintain window size
        self._ohlc_data[instrument].loc[len(self._ohlc_data[instrument])] = new_row
        if len(self._ohlc_data[instrument]) > self.window_size:
            self._ohlc_data[instrument] = self._ohlc_data[instrument].tail(self.window_size)

        # Calculate all indicators
        indicators = self._calculate_all_indicators(instrument)
        
        # Update timestamp to use candle timestamp (virtual time) instead of current time
        if candle_timestamp is not None:
            indicators.timestamp = candle_timestamp.isoformat()

        # Store latest
        self._latest_indicators[instrument] = indicators

        # Cache and publish to Redis if available
        if self.redis_client:
            try:
                indicators_dict = asdict(indicators)
                # Store using standardized Redis keys
                for key, value in indicators_dict.items():
                    if value is not None and key in ALL_INDICATORS:
                        redis_key = get_indicator_redis_key(instrument, key, indicators.timeframe)
                        self.redis_client.setex(redis_key, 300, str(value))

                # Publish standardized complete payload (only on candle close)
                try:
                    import json
                    import hashlib
                    
                    # Create complete, standardized payload with all indicators
                    pub = self._json_safe_dict(indicators_dict)
                    # Remove None values
                    pub = {k: v for k, v in pub.items() if v is not None}

                    # Add candle-close flags to distinguish from intrabar tick updates
                    pub.update({
                        "intrabar": False,       # False for candle-close updates (stable values)
                        "candle_closed": True,   # True for candle-close updates, False for tick updates
                        "update_type": "candle"  # "tick" or "candle" to distinguish source
                    })

                    # Add canonical timestamps using candle timestamp (virtual time)
                    market_ts = candle_timestamp if candle_timestamp else get_market_time()
                    if isinstance(market_ts, pd.Timestamp):
                        from datetime import datetime
                        market_ts = market_ts.to_pydatetime()
                    
                    # In BACKTEST mode, use candle time for indicator_timestamp for accurate analytics
                    # In LIVE mode, use current time for indicator_timestamp (when calculated)
                    indicator_ts = market_ts if self._mode == "BACKTEST" else get_market_time()

                    timestamp_payload = create_canonical_timestamp_payload(
                        market_timestamp=market_ts,
                        indicator_timestamp=indicator_ts
                    )
                    pub.update(timestamp_payload)
                    
                    # Deduplication: Check if this payload is identical to last published
                    payload_str = json.dumps(pub, sort_keys=True)
                    payload_hash = hashlib.md5(payload_str.encode()).hexdigest()
                    
                    last_hash = self._last_published_hash.get(instrument)
                    if last_hash == payload_hash:
                        # Identical payload - skip publishing to prevent duplicates
                        logger.debug(f"Skipping duplicate indicator publish for {instrument}")
                        return indicators
                    
                    # Update last published hash
                    self._last_published_hash[instrument] = payload_hash
                    
                    # Add mode-aware payload to ALL messages
                    mode_payload = create_mode_aware_payload(
                        mode=self._mode,
                        run_id=self._run_id,
                        instrument=instrument,
                        timeframe="1min"
                    )
                    pub.update(mode_payload)

                    # Update payload_str with mode info
                    payload_str = json.dumps(pub, sort_keys=True)

                    # Publish to type-specific channel only
                    type_specific_channel = get_instrument_channel(instrument, "indicators")
                    self.redis_client.publish(type_specific_channel, payload_str)
                    logger.debug(f"Published indicators for {instrument} in {self._mode} mode on candle close")
                except Exception as pub_err:
                    logger.warning(f"Failed to publish indicators to Redis: {pub_err}", exc_info=True)
            except Exception as e:
                logger.warning(f"Failed to cache indicators in Redis: {e}")

        return indicators
    
    def get_indicators(self, instrument: str) -> Optional[TechnicalIndicators]:
        """Get latest pre-calculated indicators for instrument.
        
        This is the API that agents call to get technical indicators.
        
        Args:
            instrument: Instrument symbol
            
        Returns:
            Latest TechnicalIndicators or None if not available
        """
        return self._latest_indicators.get(instrument)

    def calculate_indicators(self, instrument: str) -> Optional[TechnicalIndicators]:
        """Calculate indicators for instrument (API compatibility method).

        This method maintains backward compatibility with existing code
        that expects a simple calculate_indicators(instrument) call.

        Args:
            instrument: Instrument symbol

        Returns:
            TechnicalIndicators object or None if calculation fails
        """
        try:
            # Calculate indicators using existing logic
            indicators = self._calculate_all_indicators(instrument)

            # Publish to Redis if available
            if self.redis_client and indicators:
                # GATE BY MODE: In BACKTEST mode, background publishing should be disabled
                # In HISTORICAL mode, indicators are calculated for replay
                # No special handling needed - indicators work the same

                indicators_dict = asdict(indicators)
                safe_indicators = self._json_safe_dict(indicators_dict)
                # Add canonical timestamps
                timestamp_payload = create_canonical_timestamp_payload(
                    market_timestamp=get_market_time(redis_client=self.redis_client),
                    indicator_timestamp=get_market_time(redis_client=self.redis_client)
                )
                safe_indicators.update(timestamp_payload)

                # Store individual indicator values as Redis keys for verification
                core_indicators = [
                    'rsi_14', 'macd_value', 'bollinger_upper', 'adx_14',
                    'current_price', 'trend_direction', 'signal_strength'
                ]

                for indicator_name in core_indicators:
                    if indicator_name in safe_indicators and safe_indicators[indicator_name] is not None:
                        redis_key = get_indicator_redis_key(instrument, indicator_name, "1min")
                        try:
                            self.redis_client.set(redis_key, str(safe_indicators[indicator_name]))
                        except Exception as store_error:
                            logger.warning(f"Failed to store indicator {indicator_name}: {store_error}")

                # Store timestamp for freshness validation
                timestamp_key = get_indicator_redis_key(instrument, 'timestamp', "1min")
                try:
                    self.redis_client.set(timestamp_key, safe_indicators.get('indicator_timestamp', datetime.now().isoformat()))
                except Exception as store_error:
                    logger.warning(f"Failed to store indicator timestamp: {store_error}")

                # Publish to type-specific channel only
                type_specific_channel = get_instrument_channel(instrument, "indicators")
                logger.info(f"Publishing indicators to Redis channel: {type_specific_channel}")
                logger.info(f"Indicator data keys: {list(safe_indicators.keys())}")
                logger.info(f"Sample values - RSI: {safe_indicators.get('rsi_14')}, ATR: {safe_indicators.get('atr_14')}")

                try:
                    result = self.redis_client.publish(type_specific_channel, json.dumps(safe_indicators))
                    logger.info(f"Publish result: {result} subscribers received")
                except Exception as pub_error:
                    logger.error(f"Failed to publish indicators to Redis: {pub_error}")
                    print(f"TECHNICAL INDICATORS PUBLISH ERROR: {pub_error}")

            return indicators
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {instrument}: {e}")
            return None

    def get_indicators_dict(self, instrument: str, timeframe: str = "1min") -> Dict[str, Any]:
        """Get latest indicators as dictionary.

        Args:
            instrument: Instrument symbol
            timeframe: Timeframe string (default: "1min")

        Returns:
            Dictionary of indicators or empty dict
        """
        # First try to get from memory
        if timeframe == "1min":
            indicators = self._latest_indicators.get(instrument)
        else:
            indicators = self.get_indicators_mtf(instrument, timeframe)
        
        if indicators:
            # Convert dataclass to dict, filtering out None values
            result = {}
            for key, value in asdict(indicators).items():
                if value is not None:
                    result[key] = value
            return result

        # If not in memory, try to reconstruct from Redis
        if self.redis_client:
            try:
                result = {}
                # Get all indicator keys for this instrument and timeframe
                pattern = get_all_indicators_redis_pattern(instrument, timeframe)
                keys = self.redis_client.keys(pattern)
                if keys:
                    for key in keys:
                        value_str = self.redis_client.get(key)
                        if value_str:
                            # Extract indicator name from key
                            key_parts = key.split(":")
                            if len(key_parts) >= 4:  # indicators:INSTRUMENT:TIMEFRAME:indicator
                                indicator_name = ":".join(key_parts[3:])  # Handle keys like indicators:INSTRUMENT:1min:rsi_14
                                try:
                                    # Try to parse as number first
                                    result[indicator_name] = float(value_str)
                                except ValueError:
                                    # If not a number, keep as string
                                    result[indicator_name] = value_str
                    if result:
                        # Add timestamp if available
                        timestamp_key = get_indicator_redis_key(instrument, "timestamp", timeframe)
                        timestamp_str = self.redis_client.get(timestamp_key)
                        if timestamp_str:
                            result["timestamp"] = timestamp_str
                        result["instrument"] = instrument
                        return result
            except Exception as e:
                logger.warning(f"Failed to reconstruct indicators from Redis for {instrument}:{timeframe}: {e}")

        return {}
    
    def _calculate_all_indicators(self, instrument: str) -> TechnicalIndicators:
        """Calculate comprehensive technical indicators using pandas and pandas-ta.

        Args:
            instrument: Instrument symbol

        Returns:
            Complete TechnicalIndicators object with all calculated indicators
        """
        df = self._ohlc_data.get(instrument)
        if df is None or len(df) < 10:  # Minimum data required (reduced for basic testing)
            current_price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0
            return TechnicalIndicators(
                timestamp=datetime.now().isoformat(),
                instrument=instrument,
                current_price=current_price
            )

        current_price = float(df["close"].iloc[-1])

        indicators = TechnicalIndicators(
            timestamp=datetime.now().isoformat(),
            instrument=instrument,
            current_price=current_price
        )

        try:
            # === TREND INDICATORS ===
            # Moving Averages
            if len(df) >= 10:
                indicators.sma_10 = self._safe_float(ta.sma(df["close"], length=10))
                indicators.ema_10 = self._safe_float(ta.ema(df["close"], length=10))

            if len(df) >= 20:
                indicators.sma_20 = self._safe_float(ta.sma(df["close"], length=20))
                indicators.ema_20 = self._safe_float(ta.ema(df["close"], length=20))
                indicators.wma_20 = self._safe_float(ta.wma(df["close"], length=20))

            if len(df) >= 50:
                indicators.sma_50 = self._safe_float(ta.sma(df["close"], length=50))
                indicators.ema_50 = self._safe_float(ta.ema(df["close"], length=50))

            # === MOMENTUM INDICATORS ===
            if len(df) >= 14:
                indicators.rsi_14 = self._safe_float(ta.rsi(df["close"], length=14))

            if len(df) >= 9:
                indicators.rsi_9 = self._safe_float(ta.rsi(df["close"], length=9))

            if len(df) >= 14:
                stoch = ta.stoch(df["high"], df["low"], df["close"])
                if stoch is not None and len(stoch.columns) >= 2:
                    indicators.stoch_k = self._safe_float(stoch.iloc[:, 0])  # STOCHk
                    indicators.stoch_d = self._safe_float(stoch.iloc[:, 1])  # STOCHd

                indicators.williams_r = self._safe_float(ta.willr(df["high"], df["low"], df["close"], length=14))

            # MACD
            if len(df) >= 26:
                macd = ta.macd(df["close"])
                if macd is not None and len(macd.columns) >= 3:
                    indicators.macd_value = self._safe_float(macd.iloc[:, 0])    # MACD
                    indicators.macd_signal = self._safe_float(macd.iloc[:, 1])   # MACDh
                    indicators.macd_histogram = self._safe_float(macd.iloc[:, 2]) # MACDs

            # === VOLATILITY INDICATORS ===
            # Bollinger Bands
            if len(df) >= 20:
                bb = ta.bbands(df["close"], length=20)
                if bb is not None and len(bb.columns) >= 3:
                    indicators.bollinger_upper = self._safe_float(bb.iloc[:, 0])   # BBL
                    indicators.bollinger_middle = self._safe_float(bb.iloc[:, 1])  # BBM
                    indicators.bollinger_lower = self._safe_float(bb.iloc[:, 2])   # BBU
                    # Calculate width and %B
                    if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
                        indicators.bollinger_width = (indicators.bollinger_upper - indicators.bollinger_lower) / indicators.bollinger_middle
                        indicators.bollinger_percent_b = (current_price - indicators.bollinger_lower) / (indicators.bollinger_upper - indicators.bollinger_lower) if (indicators.bollinger_upper - indicators.bollinger_lower) != 0 else 0

            # ATR
            if len(df) >= 14:
                indicators.atr_14 = self._safe_float(ta.atr(df["high"], df["low"], df["close"], length=14))

            if len(df) >= 20:
                indicators.atr_20 = self._safe_float(ta.atr(df["high"], df["low"], df["close"], length=20))

            # === TREND STRENGTH ===
            if len(df) >= 14:
                adx = ta.adx(df["high"], df["low"], df["close"], length=14)
                if adx is not None and len(adx.columns) >= 3:
                    indicators.adx_14 = self._safe_float(adx.iloc[:, 0])    # ADX
                    indicators.di_plus = self._safe_float(adx.iloc[:, 1])  # DMP
                    indicators.di_minus = self._safe_float(adx.iloc[:, 2]) # DMN

            # Ichimoku Cloud (requires minimum data)
            if len(df) >= 52:
                ichimoku = ta.ichimoku(df["high"], df["low"], df["close"])
                # ichimoku can return a tuple or DataFrame - handle both
                if ichimoku is not None:
                    if isinstance(ichimoku, tuple):
                        # If tuple, skip ichimoku for now
                        pass
                    elif hasattr(ichimoku, 'columns') and len(ichimoku.columns) >= 5:
                        indicators.ichimoku_tenkan = self._safe_float(ichimoku.iloc[:, 0])   # TENKAN
                        indicators.ichimoku_kijun = self._safe_float(ichimoku.iloc[:, 1])    # KIJUN
                        indicators.ichimoku_senkou_a = self._safe_float(ichimoku.iloc[:, 3]) # SENKOU_A
                        indicators.ichimoku_senkou_b = self._safe_float(ichimoku.iloc[:, 4]) # SENKOU_B

            # === VOLUME INDICATORS ===
            if len(df) >= 1:
                indicators.obv = self._safe_float(ta.obv(df["close"], df["volume"]))

            if len(df) >= 20:
                indicators.volume_sma_20 = self._safe_float(ta.sma(df["volume"], length=20))
                indicators.volume_rsi_14 = self._safe_float(ta.rsi(df["volume"], length=14))

            if len(df) >= 20:
                indicators.cmf_20 = self._safe_float(ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=20))

            # === OPEN INTEREST INDICATORS ===
            if "oi" in df.columns:
                oi_series = df["oi"].ffill()
                latest_oi = oi_series.iloc[-1] if len(oi_series) else None
                if latest_oi is not None and not pd.isna(latest_oi):
                    indicators.oi = float(latest_oi)

                if len(oi_series) >= 2:
                    prev_oi = oi_series.iloc[-2]
                    if prev_oi is not None and not pd.isna(prev_oi):
                        change = latest_oi - prev_oi if latest_oi is not None else None
                        if change is not None:
                            indicators.oi_change = float(change)
                            indicators.oi_pct_change = float((change / prev_oi) * 100) if prev_oi else None

                # Use pure-Python fallbacks for OI indicators to avoid numba typing errors
                # (pandas_ta's numba-accelerated SMA/EMA can fail on object dtypes).
                if len(oi_series) >= 5:
                    try:
                        indicators.oi_sma_5 = float(pd.Series(oi_series).astype(float).tail(5).mean())
                    except Exception:
                        indicators.oi_sma_5 = None

                    try:
                        prev = pd.Series(oi_series).astype(float)
                        if len(prev) >= 6:
                            indicators.oi_momentum_5 = float(prev.iloc[-1] - prev.iloc[-6])
                        else:
                            indicators.oi_momentum_5 = float(prev.iloc[-1] - prev.iloc[0]) if len(prev) else None
                    except Exception:
                        indicators.oi_momentum_5 = None

                if len(oi_series) >= 10:
                    try:
                        series = pd.Series(oi_series).astype(float)
                        indicators.oi_ema_10 = float(series.ewm(span=10, adjust=False).mean().iloc[-1])
                    except Exception:
                        indicators.oi_ema_10 = None

            # === OSCILLATORS ===
            if len(df) >= 20:
                indicators.cci_20 = self._safe_float(ta.cci(df["high"], df["low"], df["close"], length=20))

            if len(df) >= 14:
                indicators.mfi_14 = self._safe_float(ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14))

            if len(df) >= 12:
                indicators.roc_12 = self._safe_float(ta.roc(df["close"], length=12))

            if len(df) >= 10:
                indicators.momentum_10 = self._safe_float(ta.mom(df["close"], length=10))

            # CCI (Commodity Channel Index)
            if len(df) >= 20:
                indicators.cci_20 = self._safe_float(ta.cci(df["high"], df["low"], df["close"], length=20))

            # MFI (Money Flow Index)
            if len(df) >= 14:
                indicators.mfi_14 = self._safe_float(ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14))

            # === SUPPORT/RESISTANCE ===
            if len(df) >= 1:
                # Use previous day's OHLC for pivot points (simplified)
                prev_day = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
                pivot_base = (prev_day["high"] + prev_day["low"] + prev_day["close"]) / 3
                indicators.pivot_point = pivot_base
                indicators.pivot_r1 = 2 * pivot_base - prev_day["low"]
                indicators.pivot_r2 = pivot_base + (prev_day["high"] - prev_day["low"])
                indicators.pivot_s1 = 2 * pivot_base - prev_day["high"]
                indicators.pivot_s2 = pivot_base - (prev_day["high"] - prev_day["low"])

            # === PRICE ACTION ===
            if len(df) >= 20:
                indicators.high_20 = float(df["high"].tail(20).max())
                indicators.low_20 = float(df["low"].tail(20).min())
                indicators.range_20 = indicators.high_20 - indicators.low_20

            # === SIGNAL STRENGTH ===
            # Composite signal based on multiple indicators (0-100 scale)
            signal_score = 0
            signal_count = 0

            # RSI signals (30-70 range is neutral)
            if indicators.rsi_14:
                signal_count += 1
                if indicators.rsi_14 < 30:
                    signal_score += 100  # Oversold
                elif indicators.rsi_14 > 70:
                    signal_score += 0    # Overbought
                else:
                    signal_score += 50   # Neutral

            # MACD signals
            if indicators.macd_histogram:
                signal_count += 1
                if indicators.macd_histogram > 0:
                    signal_score += 75  # Bullish momentum
                else:
                    signal_score += 25  # Bearish momentum

            # Bollinger Band position
            if indicators.bollinger_percent_b:
                signal_count += 1
                if indicators.bollinger_percent_b < 0.2:
                    signal_score += 100  # Near lower band (potential bounce)
                elif indicators.bollinger_percent_b > 0.8:
                    signal_score += 0    # Near upper band (potential reversal)
                else:
                    signal_score += 50   # Middle range

            # ADX trend strength
            if indicators.adx_14:
                signal_count += 1
                if indicators.adx_14 > 25:
                    signal_score += 80  # Strong trend
                else:
                    signal_score += 30  # Weak trend

            indicators.signal_strength = signal_score / max(signal_count, 1)

            # === TREND DIRECTION & STRENGTH ===
            # Determine trend direction based on moving averages
            trend_score = 0
            if indicators.sma_20 and indicators.sma_50:
                if current_price > indicators.sma_20 > indicators.sma_50:
                    indicators.trend_direction = "UP"
                    trend_score = 80
                elif current_price < indicators.sma_20 < indicators.sma_50:
                    indicators.trend_direction = "DOWN"
                    trend_score = 20
                else:
                    indicators.trend_direction = "SIDEWAYS"
                    trend_score = 50
            elif indicators.ema_10 and indicators.ema_20:
                if current_price > indicators.ema_10 > indicators.ema_20:
                    indicators.trend_direction = "UP"
                    trend_score = 75
                elif current_price < indicators.ema_10 < indicators.ema_20:
                    indicators.trend_direction = "DOWN"
                    trend_score = 25
                else:
                    indicators.trend_direction = "SIDEWAYS"
                    trend_score = 50

            # Incorporate ADX for trend strength
            if indicators.adx_14:
                if indicators.adx_14 > 25:  # Strong trend
                    trend_score = min(100, trend_score + 20)
                elif indicators.adx_14 < 20:  # Weak trend
                    trend_score = max(0, trend_score - 20)

            indicators.trend_strength = trend_score

        except Exception as e:
            logger.error(f"Error calculating indicators for {instrument}: {e}", exc_info=True)

        return indicators

    def _safe_float(self, series_or_value) -> Optional[float]:
        """Safely extract float value from pandas Series or return None."""
        try:
            if hasattr(series_or_value, 'iloc'):
                # It's a Series
                if not series_or_value.empty:
                    value = series_or_value.iloc[-1]
                    return float(value) if pd.notna(value) else None
            else:
                # It's a scalar
                return float(series_or_value) if series_or_value is not None and pd.notna(series_or_value) else None
        except (ValueError, TypeError, IndexError):
            return None
            if macd is not None and not macd.empty:
                indicators.macd_value = float(macd["MACD_12_26_9"].iloc[-1]) if pd.notna(macd["MACD_12_26_9"].iloc[-1]) else None
                indicators.macd_signal = float(macd["MACDs_12_26_9"].iloc[-1]) if pd.notna(macd["MACDs_12_26_9"].iloc[-1]) else None
                indicators.macd_histogram = float(macd["MACDh_12_26_9"].iloc[-1]) if pd.notna(macd["MACDh_12_26_9"].iloc[-1]) else None
            
            # === VOLATILITY INDICATORS ===
            atr = ta.atr(df["high"], df["low"], df["close"], length=14)
            if not atr.empty and pd.notna(atr.iloc[-1]):
                indicators.atr_14 = float(atr.iloc[-1])
                
                # Volatility level
                atr_pct = (indicators.atr_14 / current_price) * 100
                if atr_pct < 1.0:
                    indicators.volatility_level = "LOW"
                elif atr_pct > 2.5:
                    indicators.volatility_level = "HIGH"
                else:
                    indicators.volatility_level = "MEDIUM"
            
            # Bollinger Bands
            bbands = ta.bbands(df["close"], length=20, std=2)
            if bbands is not None and not bbands.empty:
                # Handle different column naming (BBU_20_2.0 or similar)
                cols = bbands.columns
                upper_col = [c for c in cols if 'BBU' in c][0] if any('BBU' in c for c in cols) else None
                middle_col = [c for c in cols if 'BBM' in c][0] if any('BBM' in c for c in cols) else None
                lower_col = [c for c in cols if 'BBL' in c][0] if any('BBL' in c for c in cols) else None
                
                if upper_col and pd.notna(bbands[upper_col].iloc[-1]):
                    indicators.bollinger_upper = float(bbands[upper_col].iloc[-1])
                if middle_col and pd.notna(bbands[middle_col].iloc[-1]):
                    indicators.bollinger_middle = float(bbands[middle_col].iloc[-1])
                if lower_col and pd.notna(bbands[lower_col].iloc[-1]):
                    indicators.bollinger_lower = float(bbands[lower_col].iloc[-1])
            
            # === TREND STRENGTH ===
            adx_result = ta.adx(df["high"], df["low"], df["close"], length=14)
            if adx_result is not None and not adx_result.empty and "ADX_14" in adx_result.columns:
                indicators.adx_14 = float(adx_result["ADX_14"].iloc[-1]) if pd.notna(adx_result["ADX_14"].iloc[-1]) else None
            
            # === VOLUME INDICATORS ===
            if "volume" in df.columns:
                vol_sma = ta.sma(df["volume"], length=20)
                if not vol_sma.empty and pd.notna(vol_sma.iloc[-1]):
                    indicators.volume_sma_20 = float(vol_sma.iloc[-1])
                    current_vol = float(df["volume"].iloc[-1])
                    indicators.volume_ratio = current_vol / indicators.volume_sma_20 if indicators.volume_sma_20 > 0 else 1.0
            
            # === SUPPORT/RESISTANCE ===
            lookback = min(20, len(df))
            indicators.support_level = float(df["low"].tail(lookback).min())
            indicators.resistance_level = float(df["high"].tail(lookback).max())
            
            # === TREND DIRECTION ===
            if indicators.sma_20 is not None:
                if current_price > indicators.sma_20 * 1.005:  # 0.5% above
                    indicators.trend_direction = "UP"
                    indicators.trend_strength = min(100, ((current_price - indicators.sma_20) / indicators.sma_20 * 100) * 10)
                elif current_price < indicators.sma_20 * 0.995:  # 0.5% below
                    indicators.trend_direction = "DOWN"
                    indicators.trend_strength = min(100, ((indicators.sma_20 - current_price) / current_price * 100) * 10)
                else:
                    indicators.trend_direction = "SIDEWAYS"
                    indicators.trend_strength = 30.0
            
        except Exception as e:
            logger.warning(f"Error calculating indicators for {instrument}: {e}")
        
        return indicators
    
    def get_indicators_dict(self, instrument: str) -> Dict[str, Any]:
        """Get latest indicators as dictionary for specified instrument.
        
        This is a convenience method for agents that prefer dict format.
        
        Args:
            instrument: Instrument symbol
            
        Returns:
            Dictionary of technical indicators or empty dict if not available
        """
        indicators = self.get_indicators(instrument)
        return indicators.to_dict() if indicators else {}
    
    def get_raw_data(self, instrument: str, periods: int = 50) -> List[Dict[str, Any]]:
        """Get raw OHLCV data for instrument.
        
        Args:
            instrument: Instrument symbol
            periods: Number of periods to return
            
        Returns:
            List of OHLCV dictionaries
        """
        window = self._data_windows.get(instrument, deque())
        return list(window)[-periods:]
    
    def update_candle_mtf(
        self, 
        instrument: str, 
        timeframe: str, 
        candle: Dict[str, Any]
    ) -> TechnicalIndicators:
        """Update indicators for specific timeframe (multi-timeframe support).
        
        Args:
            instrument: Instrument symbol
            timeframe: Timeframe string (e.g., "5m", "15m", "1h", "daily")
            candle: OHLC data with open, high, low, close, volume, timestamp
        
        Returns:
            Updated TechnicalIndicators object for the timeframe
        """
        key = (instrument, timeframe)
        
        # Initialize DataFrame if needed
        if key not in self._ohlc_data_mtf:
            self._ohlc_data_mtf[key] = pd.DataFrame(
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
            )
        
        # Add new candle to DataFrame
        new_row = {
            'timestamp': pd.to_datetime(candle['start_at']) if isinstance(candle.get('start_at'), str)
                        else pd.to_datetime(candle['timestamp']),
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle.get('volume', 0),
            'oi': candle.get('oi')
        }
        
        # Append to DataFrame and maintain window size
        self._ohlc_data_mtf[key].loc[len(self._ohlc_data_mtf[key])] = new_row
        if len(self._ohlc_data_mtf[key]) > self.window_size:
            self._ohlc_data_mtf[key] = self._ohlc_data_mtf[key].tail(self.window_size)
        
        # Calculate all indicators for this timeframe
        indicators = self._calculate_all_indicators_mtf(instrument, timeframe)
        
        # Store latest
        self._indicators_mtf[key] = indicators
        
        # Cache to Redis with timeframe key
        if self.redis_client:
            try:
                indicators_dict = asdict(indicators)
                for key_name, value in indicators_dict.items():
                    if value is not None and key_name in ALL_INDICATORS:
                        redis_key = f"indicators:{instrument}:{timeframe}:{key_name}"
                        self.redis_client.setex(redis_key, 300, str(value))
            except Exception as e:
                logger.warning(f"Failed to cache MTF indicators in Redis: {e}")
        
        return indicators
    
    def get_indicators_mtf(
        self, 
        instrument: str, 
        timeframe: str
    ) -> Optional[TechnicalIndicators]:
        """Get indicators for specific timeframe.
        
        Args:
            instrument: Instrument symbol
            timeframe: Timeframe string (e.g., "5m", "15m", "1h", "daily")
        
        Returns:
            TechnicalIndicators for the timeframe or None
        """
        key = (instrument, timeframe)
        return self._indicators_mtf.get(key)
    
    def get_all_timeframe_indicators(
        self,
        instrument: str,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, TechnicalIndicators]:
        """Get indicators for multiple timeframes.
        
        Args:
            instrument: Instrument symbol
            timeframes: List of timeframes (default: ["5m", "15m", "1h", "daily"])
        
        Returns:
            Dictionary mapping timeframe to TechnicalIndicators
        """
        if timeframes is None:
            timeframes = ["5m", "15m", "1h", "daily"]
        
        result = {}
        for tf in timeframes:
            indicators = self.get_indicators_mtf(instrument, tf)
            if indicators:
                result[tf] = indicators
        
        return result
    
    def _calculate_all_indicators_mtf(
        self, 
        instrument: str, 
        timeframe: str
    ) -> TechnicalIndicators:
        """Calculate indicators for specific timeframe.
        
        This is the same as _calculate_all_indicators but uses MTF data storage.
        
        Args:
            instrument: Instrument symbol
            timeframe: Timeframe string
        
        Returns:
            TechnicalIndicators object
        """
        key = (instrument, timeframe)
        df = self._ohlc_data_mtf.get(key)
        
        if df is None or len(df) < 20:
            current_price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0
            return TechnicalIndicators(
                timestamp=datetime.now().isoformat(),
                instrument=instrument,
                current_price=current_price,
                timeframe=timeframe
            )
        
        current_price = float(df["close"].iloc[-1])
        
        indicators = TechnicalIndicators(
            timestamp=datetime.now().isoformat(),
            instrument=instrument,
            current_price=current_price,
            timeframe=timeframe
        )
        
        # Use the same calculation logic as _calculate_all_indicators
        # but work with the MTF DataFrame
        try:
            # === TREND INDICATORS ===
            if len(df) >= 10:
                indicators.sma_10 = self._safe_float(ta.sma(df["close"], length=10))
                indicators.ema_10 = self._safe_float(ta.ema(df["close"], length=10))
            
            if len(df) >= 20:
                indicators.sma_20 = self._safe_float(ta.sma(df["close"], length=20))
                indicators.ema_20 = self._safe_float(ta.ema(df["close"], length=20))
                indicators.wma_20 = self._safe_float(ta.wma(df["close"], length=20))
            
            if len(df) >= 50:
                indicators.sma_50 = self._safe_float(ta.sma(df["close"], length=50))
                indicators.ema_50 = self._safe_float(ta.ema(df["close"], length=50))
            
            # === MOMENTUM INDICATORS ===
            if len(df) >= 14:
                indicators.rsi_14 = self._safe_float(ta.rsi(df["close"], length=14))
            
            if len(df) >= 9:
                indicators.rsi_9 = self._safe_float(ta.rsi(df["close"], length=9))
            
            # MACD
            if len(df) >= 26:
                macd = ta.macd(df["close"])
                if macd is not None and len(macd.columns) >= 3:
                    indicators.macd_value = self._safe_float(macd.iloc[:, 0])
                    indicators.macd_signal = self._safe_float(macd.iloc[:, 1])
                    indicators.macd_histogram = self._safe_float(macd.iloc[:, 2])
            
            # === VOLATILITY INDICATORS ===
            if len(df) >= 20:
                bb = ta.bbands(df["close"], length=20)
                if bb is not None and len(bb.columns) >= 3:
                    indicators.bollinger_upper = self._safe_float(bb.iloc[:, 0])
                    indicators.bollinger_middle = self._safe_float(bb.iloc[:, 1])
                    indicators.bollinger_lower = self._safe_float(bb.iloc[:, 2])
                    if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
                        indicators.bollinger_width = (
                            (indicators.bollinger_upper - indicators.bollinger_lower) / indicators.bollinger_middle
                        )
                        if (indicators.bollinger_upper - indicators.bollinger_lower) != 0:
                            indicators.bollinger_percent_b = (
                                (current_price - indicators.bollinger_lower) / 
                                (indicators.bollinger_upper - indicators.bollinger_lower)
                            )
            
            if len(df) >= 14:
                indicators.atr_14 = self._safe_float(ta.atr(df["high"], df["low"], df["close"], length=14))
            
            # === TREND STRENGTH ===
            if len(df) >= 14:
                adx = ta.adx(df["high"], df["low"], df["close"], length=14)
                if adx is not None and len(adx.columns) >= 3:
                    indicators.adx_14 = self._safe_float(adx.iloc[:, 0])
                    indicators.di_plus = self._safe_float(adx.iloc[:, 1])
                    indicators.di_minus = self._safe_float(adx.iloc[:, 2])
            
            # === VOLUME INDICATORS ===
            if len(df) >= 20:
                indicators.volume_sma_20 = self._safe_float(ta.sma(df["volume"], length=20))
                if len(df) >= 14:
                    indicators.volume_rsi_14 = self._safe_float(ta.rsi(df["volume"], length=14))

                # Calculate volume ratio
                if indicators.volume_sma_20 and indicators.volume_sma_20 > 0:
                    current_volume = df["volume"].iloc[-1]
                    indicators.volume_ratio = current_volume / indicators.volume_sma_20

            # === OPEN INTEREST INDICATORS ===
            if "oi" in df.columns:
                oi_series = df["oi"].ffill()
                latest_oi = oi_series.iloc[-1] if len(oi_series) else None
                if latest_oi is not None and not pd.isna(latest_oi):
                    indicators.oi = float(latest_oi)

                if len(oi_series) >= 2:
                    prev_oi = oi_series.iloc[-2]
                    if prev_oi is not None and not pd.isna(prev_oi):
                        change = latest_oi - prev_oi if latest_oi is not None else None
                        if change is not None:
                            indicators.oi_change = float(change)
                            indicators.oi_pct_change = float((change / prev_oi) * 100) if prev_oi else None

                if len(oi_series) >= 5:
                    try:
                        indicators.oi_sma_5 = float(pd.Series(oi_series).astype(float).tail(5).mean())
                    except Exception:
                        indicators.oi_sma_5 = None

                    try:
                        prev = pd.Series(oi_series).astype(float)
                        if len(prev) >= 6:
                            indicators.oi_momentum_5 = float(prev.iloc[-1] - prev.iloc[-6])
                        else:
                            indicators.oi_momentum_5 = float(prev.iloc[-1] - prev.iloc[0]) if len(prev) else None
                    except Exception:
                        indicators.oi_momentum_5 = None

                if len(oi_series) >= 10:
                    try:
                        series = pd.Series(oi_series).astype(float)
                        indicators.oi_ema_10 = float(series.ewm(span=10, adjust=False).mean().iloc[-1])
                    except Exception:
                        indicators.oi_ema_10 = None

            # === ADDITIONAL OSCILLATORS ===
            if len(df) >= 20:
                indicators.cci_20 = self._safe_float(ta.cci(df["high"], df["low"], df["close"], length=20))

            if len(df) >= 14:
                indicators.mfi_14 = self._safe_float(ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14))

            if len(df) >= 12:
                indicators.roc_12 = self._safe_float(ta.roc(df["close"], length=12))

            if len(df) >= 10:
                indicators.momentum_10 = self._safe_float(ta.mom(df["close"], length=10))

            # === SUPPORT/RESISTANCE ===
            if len(df) >= 1:
                # Use previous day's OHLC for pivot points (simplified)
                prev_day = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
                pivot_base = (prev_day["high"] + prev_day["low"] + prev_day["close"]) / 3
                indicators.pivot_point = pivot_base
                indicators.pivot_r1 = 2 * pivot_base - prev_day["low"]
                indicators.pivot_r2 = pivot_base + (prev_day["high"] - prev_day["low"])
                indicators.pivot_s1 = 2 * pivot_base - prev_day["high"]
                indicators.pivot_s2 = pivot_base - (prev_day["high"] - prev_day["low"])

            # === PRICE ACTION ===
            if len(df) >= 20:
                indicators.high_20 = float(df["high"].tail(20).max())
                indicators.low_20 = float(df["low"].tail(20).min())
                indicators.range_20 = indicators.high_20 - indicators.low_20

            # === TREND DIRECTION & STRENGTH ===
            trend_score = 0
            if indicators.sma_20 and indicators.sma_50:
                if current_price > indicators.sma_20 > indicators.sma_50:
                    indicators.trend_direction = "UP"
                    trend_score = 80
                elif current_price < indicators.sma_20 < indicators.sma_50:
                    indicators.trend_direction = "DOWN"
                    trend_score = 20
                else:
                    indicators.trend_direction = "SIDEWAYS"
                    trend_score = 50
            elif indicators.ema_10 and indicators.ema_20:
                if current_price > indicators.ema_10 > indicators.ema_20:
                    indicators.trend_direction = "UP"
                    trend_score = 75
                elif current_price < indicators.ema_10 < indicators.ema_20:
                    indicators.trend_direction = "DOWN"
                    trend_score = 25
                else:
                    indicators.trend_direction = "SIDEWAYS"
                    trend_score = 50

            # Incorporate ADX for trend strength
            if indicators.adx_14:
                if indicators.adx_14 > 25:  # Strong trend
                    trend_score = min(100, trend_score + 20)
                elif indicators.adx_14 < 20:  # Weak trend
                    trend_score = max(0, trend_score - 20)

            indicators.trend_strength = trend_score

            # === SIGNAL STRENGTH ===
            signal_score = 0
            signal_count = 0

            # RSI signals (30-70 range is neutral)
            if indicators.rsi_14:
                signal_count += 1
                if indicators.rsi_14 < 30:
                    signal_score += 100  # Oversold
                elif indicators.rsi_14 > 70:
                    signal_score += 0    # Overbought
                else:
                    signal_score += 50   # Neutral

            # MACD signals
            if indicators.macd_histogram:
                signal_count += 1
                if indicators.macd_histogram > 0:
                    signal_score += 75  # Bullish momentum
                else:
                    signal_score += 25  # Bearish momentum

            indicators.signal_strength = signal_score / max(signal_count, 1)
            
        except Exception as e:
            logger.error(f"Error calculating MTF indicators for {instrument}:{timeframe}: {e}", exc_info=True)
        
        return indicators
    
    def calculate_indicators_from_ohlc_bars(
        self,
        instrument: str,
        timeframe: str,
        ohlc_bars: List[Any]  # List of OHLCBar objects
    ) -> TechnicalIndicators:
        """Calculate indicators from a list of OHLCBar objects (for multi-timeframe analysis).
        
        This method is designed to work with MultiTimeframeReader.
        
        Args:
            instrument: Instrument symbol
            timeframe: Timeframe string
            ohlc_bars: List of OHLCBar objects
        
        Returns:
            TechnicalIndicators object
        """
        if not ohlc_bars:
            return TechnicalIndicators(
                timestamp=datetime.now().isoformat(),
                instrument=instrument,
                current_price=0.0,
                timeframe=timeframe
            )
        
        # Convert OHLCBar objects to DataFrame
        data = []
        for bar in ohlc_bars:
            data.append({
                'timestamp': pd.to_datetime(bar.start_at),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume or 0,
                'oi': bar.open_interest
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Store in MTF data
        key = (instrument, timeframe)
        self._ohlc_data_mtf[key] = df.tail(self.window_size)
        
        # Calculate indicators
        indicators = self._calculate_all_indicators_mtf(instrument, timeframe)
        self._indicators_mtf[key] = indicators
        
        # Store in Redis if available
        if self.redis_client and indicators:
            try:
                indicators_dict = asdict(indicators)
                # Store using standardized Redis keys with timeframe
                for key_name, value in indicators_dict.items():
                    if value is not None and key_name in ALL_INDICATORS:
                        redis_key = get_indicator_redis_key(instrument, key_name, timeframe)
                        self.redis_client.setex(redis_key, 300, str(value))
            except Exception as e:
                logger.warning(f"Failed to store MTF indicators for {instrument}:{timeframe}: {e}")
        
        return indicators


# Singleton instance for global access
_technical_service: Optional[TechnicalIndicatorsService] = None


def get_technical_service() -> TechnicalIndicatorsService:
    """Get global technical indicators service instance.
    
    Returns:
        Singleton TechnicalIndicatorsService instance
    """
    global _technical_service
    if _technical_service is None:
        _technical_service = TechnicalIndicatorsService()
    return _technical_service

