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
    create_event_envelope,
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
    timeframe: str = "1m"

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
    WARMUP_REQUIREMENTS: Dict[str, int] = {
        "rsi": 14,
        "macd": 26,
        "bollinger": 20,
        "cci": 20,
        "stoch": 14,
        "atr": 14,
        "mfi": 14,
        "roc": 12,
        "momentum": 10,
        "adx": 14,
    }

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

    def _normalize_ohlc_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sort, deduplicate by timestamp, and cap to window size."""
        if df is None or df.empty:
            return df

        out = df.copy()
        if "timestamp" in out.columns:
            out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
            out = out.dropna(subset=["timestamp"]).sort_values("timestamp")
            # Keep the latest value for each candle timestamp.
            out = out.drop_duplicates(subset=["timestamp"], keep="last")

        return out.tail(self.window_size).reset_index(drop=True)

    def _cache_indicator_value(
        self,
        instrument: str,
        timeframe: str,
        indicator_name: str,
        value: Any,
        ttl_seconds: int = 300,
    ) -> None:
        """Store or clear a single indicator key in Redis.

        Important behavior:
        - Writes with TTL to avoid indefinite stale values.
        - Deletes key when value is None so stale historical values are not reused.
        """
        if not self.redis_client:
            return

        redis_key = get_indicator_redis_key(instrument, indicator_name, timeframe)
        try:
            if value is None:
                self.redis_client.delete(redis_key)
            else:
                self.redis_client.setex(redis_key, ttl_seconds, str(value))
        except Exception as e:
            logger.debug(f"Failed to cache indicator {indicator_name} for {instrument}:{timeframe}: {e}")

    def _persist_indicator_metadata(
        self,
        instrument: str,
        timeframe: str,
        indicator_timestamp: Any,
        source: str,
        update_type: Optional[str] = None,
        stream: Optional[str] = None,
        bars_available: Optional[int] = None,
        ttl_seconds: int = 300,
    ) -> None:
        """Persist timestamp/source metadata for indicator consumers.

        Stores canonical timeframe-scoped keys only.
        """
        if not self.redis_client:
            return

        ts_iso: Optional[str] = None
        try:
            parsed = pd.to_datetime(indicator_timestamp, errors="coerce")
            if pd.notna(parsed):
                parsed_dt = parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed
                ts_iso = get_market_time(timestamp=parsed_dt, redis_client=self.redis_client).isoformat()
        except Exception:
            ts_iso = None

        if not ts_iso:
            ts_iso = get_market_time(redis_client=self.redis_client).isoformat()

        source_value = (source or "unknown").strip().lower()

        # Canonical timeframe-scoped metadata keys
        self._cache_indicator_value(instrument, timeframe, "timestamp", ts_iso, ttl_seconds)
        self._cache_indicator_value(instrument, timeframe, "indicator_timestamp", ts_iso, ttl_seconds)
        self._cache_indicator_value(instrument, timeframe, "source", source_value, ttl_seconds)
        self._cache_indicator_value(instrument, timeframe, "update_type", update_type, ttl_seconds)
        self._cache_indicator_value(instrument, timeframe, "indicator_update_type", update_type, ttl_seconds)
        self._cache_indicator_value(instrument, timeframe, "stream", stream, ttl_seconds)
        self._cache_indicator_value(instrument, timeframe, "indicator_stream", stream, ttl_seconds)
        self._cache_indicator_value(instrument, timeframe, "bars_available", bars_available, ttl_seconds)

        # Best-effort cleanup of removed legacy compatibility keys.
        legacy_timestamp_key = f"indicators:{instrument.upper()}:timestamp"
        legacy_source_key = f"indicators:{instrument.upper()}:source"
        try:
            self.redis_client.delete(legacy_timestamp_key)
            self.redis_client.delete(legacy_source_key)
        except Exception as e:
            logger.debug(
                "Failed to delete legacy indicator metadata keys for %s:%s: %s",
                instrument,
                timeframe,
                e,
            )

    def _next_event_sequence(self, stream: str, instrument: str, timeframe: str) -> Optional[int]:
        if not self.redis_client:
            return None
        try:
            key = f"events:seq:{stream}:{instrument}:{timeframe}"
            return int(self.redis_client.incr(key))
        except Exception:
            return None

    def _publish_indicator_event(
        self,
        *,
        stream: str,
        instrument: str,
        timeframe: str,
        payload: Dict[str, Any],
        event_time: Any,
        source_event_id: Optional[str] = None,
    ) -> None:
        if not self.redis_client:
            return

        seq = self._next_event_sequence(stream, instrument, timeframe)
        envelope = create_event_envelope(
            stream=stream,
            payload=payload,
            instrument=instrument,
            timeframe=timeframe,
            event_time=event_time,
            emitted_at=payload.get("indicator_timestamp") or payload.get("indicator_timestamp_utc"),
            source_event_id=source_event_id,
            mode=self._mode,
            run_id=self._run_id,
            sequence=seq,
        )

        type_specific_channel = get_instrument_channel(instrument, "indicators")
        self.redis_client.publish(type_specific_channel, json.dumps(envelope, default=str))

    def initialize_with_ohlc_data(self, instrument: str, ohlc_bars: List[Dict[str, Any]]) -> None:
        """Initialize technical indicators with existing OHLC data.
        
        Args:
            instrument: Instrument symbol
            ohlc_bars: List of OHLC bar dictionaries
        """
        if not ohlc_bars:
            return

        # Rebuild frame from incoming bars, then normalize to avoid duplicate-candle drift.
        rows = []
        for bar in ohlc_bars[-self.window_size:]:
            rows.append({
                'timestamp': bar.get('start_at') or bar.get('timestamp'),
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar.get('volume', 0),
                'oi': bar.get('oi')
            })

        frame = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        self._ohlc_data[instrument] = self._normalize_ohlc_dataframe(frame)

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
                        if key in ALL_INDICATORS:
                            self._cache_indicator_value(instrument, indicators.timeframe, key, value)

                    self._persist_indicator_metadata(
                        instrument,
                        indicators.timeframe,
                        indicators.timestamp,
                        source="ohlc_initialize",
                        update_type="batch_initialize",
                        stream="Y2",
                        bars_available=len(self._ohlc_data.get(instrument, [])),
                    )

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
                        pub.update({
                            "intrabar": False,
                            "candle_closed": True,
                            "update_type": "batch_initialize",
                            "indicator_update_type": "batch_initialize",
                            "indicator_stream": "Y2",
                            "source": "ohlc_initialize",
                            "bars_available": len(self._ohlc_data.get(instrument, [])),
                            "warmup_requirements": dict(self.WARMUP_REQUIREMENTS),
                        })

                        self._publish_indicator_event(
                            stream="Y2",
                            instrument=instrument,
                            timeframe=indicators.timeframe,
                            payload=pub,
                            event_time=pub.get("market_timestamp") or indicators.timestamp,
                        )
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
                    if key in ALL_INDICATORS:
                        self._cache_indicator_value(instrument, indicators.timeframe, key, value)

                self._persist_indicator_metadata(
                    instrument,
                    indicators.timeframe,
                    tick_timestamp,
                    source="tick",
                    update_type="tick",
                    stream="LZ1",
                    bars_available=len(self._ohlc_data.get(instrument, [])),
                )

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
                        "update_type": "tick",    # "tick" or "candle" to distinguish source
                        "indicator_update_type": "tick",
                        "indicator_stream": "LZ1",
                        "source": "tick",
                        "bars_available": len(self._ohlc_data.get(instrument, [])),
                        "warmup_requirements": dict(self.WARMUP_REQUIREMENTS),
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

                    self._publish_indicator_event(
                        stream="LZ1",
                        instrument=instrument,
                        timeframe="1min",
                        payload=pub,
                        event_time=pub.get("market_timestamp") or tick_ts,
                    )
                    logger.debug(f"Published intrabar indicators for {instrument} on tick update")
                except Exception as pub_err:
                    logger.debug(f"Failed to publish intrabar indicators to Redis: {pub_err}")
            except Exception as e:
                logger.warning(f"Failed to cache indicators in Redis: {e}")

        return indicators

    def _apply_derived_state(self, indicators: TechnicalIndicators, current_price: float) -> None:
        """Compute state fields required by dashboard cards."""
        if indicators.rsi_14 is None:
            indicators.rsi_status = "NEUTRAL"
        elif indicators.rsi_14 < 30:
            indicators.rsi_status = "OVERSOLD"
        elif indicators.rsi_14 > 70:
            indicators.rsi_status = "OVERBOUGHT"
        else:
            indicators.rsi_status = "NEUTRAL"

        if indicators.atr_14 is None or current_price <= 0:
            indicators.volatility_level = "MEDIUM"
        else:
            atr_ratio = float(indicators.atr_14) / float(current_price)
            if atr_ratio < 0.0015:
                indicators.volatility_level = "LOW"
            elif atr_ratio < 0.0035:
                indicators.volatility_level = "MEDIUM"
            else:
                indicators.volatility_level = "HIGH"

        if indicators.pivot_s1 is not None:
            indicators.support_level = indicators.pivot_s1
        if indicators.pivot_r1 is not None:
            indicators.resistance_level = indicators.pivot_r1
    
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
        self._ohlc_data[instrument] = self._normalize_ohlc_dataframe(self._ohlc_data[instrument])

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
                    if key in ALL_INDICATORS:
                        self._cache_indicator_value(instrument, indicators.timeframe, key, value)

                self._persist_indicator_metadata(
                    instrument,
                    indicators.timeframe,
                    indicators.timestamp,
                    source="candle",
                    update_type="candle",
                    stream="Y2",
                    bars_available=len(self._ohlc_data.get(instrument, [])),
                )

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
                        "update_type": "candle",  # "tick" or "candle" to distinguish source
                        "indicator_update_type": "candle",
                        "indicator_stream": "Y2",
                        "source": "candle",
                        "bars_available": len(self._ohlc_data.get(instrument, [])),
                        "warmup_requirements": dict(self.WARMUP_REQUIREMENTS),
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
                    
                    self._publish_indicator_event(
                        stream="Y2",
                        instrument=instrument,
                        timeframe="1min",
                        payload=pub,
                        event_time=pub.get("market_timestamp") or market_ts,
                    )
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
        """Calculate indicators for instrument.

        Args:
            instrument: Instrument symbol

        Returns:
            TechnicalIndicators object or None if calculation fails
        """
        try:
            # Calculate indicators using current OHLC buffer
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
                safe_indicators.update({
                    "intrabar": False,
                    "candle_closed": True,
                    "update_type": "batch_recalculate",
                    "indicator_update_type": "batch_recalculate",
                    "indicator_stream": "Y2",
                    "source": "calculate_indicators",
                    "bars_available": len(self._ohlc_data.get(instrument, [])),
                    "warmup_requirements": dict(self.WARMUP_REQUIREMENTS),
                })

                # Store individual indicator values as Redis keys for verification
                core_indicators = [
                    'rsi_14', 'macd_value', 'bollinger_upper', 'adx_14',
                    'current_price', 'trend_direction', 'signal_strength'
                ]

                for indicator_name in core_indicators:
                    if indicator_name in safe_indicators:
                        self._cache_indicator_value(
                            instrument,
                            "1min",
                            indicator_name,
                            safe_indicators.get(indicator_name),
                        )

                # Store timestamp for freshness validation
                self._persist_indicator_metadata(
                    instrument,
                    "1min",
                    safe_indicators.get('indicator_timestamp', datetime.now().isoformat()),
                    source="calculate_indicators",
                    update_type="batch_recalculate",
                    stream="Y2",
                    bars_available=len(self._ohlc_data.get(instrument, [])),
                )

                # Publish to type-specific channel only
                type_specific_channel = get_instrument_channel(instrument, "indicators")
                logger.info(f"Publishing indicators to Redis channel: {type_specific_channel}")
                logger.info(f"Indicator data keys: {list(safe_indicators.keys())}")
                logger.info(f"Sample values - RSI: {safe_indicators.get('rsi_14')}, ATR: {safe_indicators.get('atr_14')}")

                try:
                    self._publish_indicator_event(
                        stream="Y2",
                        instrument=instrument,
                        timeframe="1min",
                        payload=safe_indicators,
                        event_time=safe_indicators.get("market_timestamp") or safe_indicators.get("timestamp") or datetime.now(),
                    )
                    logger.info("Published envelope indicator event")
                except Exception as pub_error:
                    logger.error(f"Failed to publish indicators to Redis: {pub_error}")
                    print(f"TECHNICAL INDICATORS PUBLISH ERROR: {pub_error}")

            return indicators
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {instrument}: {e}")
            return None

    def get_indicators_dict(self, instrument: str, timeframe: str = "1m") -> Dict[str, Any]:
        """Get latest indicators as dictionary.

        Args:
            instrument: Instrument symbol
            timeframe: Timeframe string (default: "1min")

        Returns:
            Dictionary of indicators or empty dict
        """
        # First try to get from memory
        if str(timeframe).strip().lower() in ("1m", "1min", "minute"):
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
                    # pandas_ta returns columns as MACD, MACDh (hist), MACDs (signal).
                    # Use names when available to avoid ordering mismatches.
                    cols = list(macd.columns)
                    macd_col = next((c for c in cols if c.startswith("MACD_") and "MACDh" not in c and "MACDs" not in c), cols[0])
                    hist_col = next((c for c in cols if "MACDh" in c), cols[1])
                    signal_col = next((c for c in cols if "MACDs" in c), cols[2])

                    indicators.macd_value = self._safe_float(macd[macd_col])
                    indicators.macd_signal = self._safe_float(macd[signal_col])
                    indicators.macd_histogram = self._safe_float(macd[hist_col])

            # === VOLATILITY INDICATORS ===
            # Bollinger Bands
            if len(df) >= 20:
                bb = ta.bbands(df["close"], length=20)
                if bb is not None and len(bb.columns) >= 3:
                    cols = list(bb.columns)
                    lower_col = next((c for c in cols if "BBL" in c), cols[0])
                    middle_col = next((c for c in cols if "BBM" in c), cols[1])
                    upper_col = next((c for c in cols if "BBU" in c), cols[2])

                    indicators.bollinger_upper = self._safe_float(bb[upper_col])
                    indicators.bollinger_middle = self._safe_float(bb[middle_col])
                    indicators.bollinger_lower = self._safe_float(bb[lower_col])
                    # Calculate width and %B
                    if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
                        band_span = indicators.bollinger_upper - indicators.bollinger_lower
                        indicators.bollinger_width = band_span / indicators.bollinger_middle
                        indicators.bollinger_percent_b = (current_price - indicators.bollinger_lower) / band_span if band_span != 0 else None

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
                indicators.cci_20 = self._calculate_cci(df, length=20)

            if len(df) >= 14:
                indicators.mfi_14 = self._calculate_mfi(df, length=14)

            if len(df) >= 12:
                indicators.roc_12 = self._safe_float(ta.roc(df["close"], length=12))

            if len(df) >= 10:
                indicators.momentum_10 = self._safe_float(ta.mom(df["close"], length=10))

            # === SUPPORT/RESISTANCE ===
            if len(df) >= 1:
                pivot_levels = self._calculate_pivot_levels(df, indicators.timeframe)
                if pivot_levels:
                    indicators.pivot_point = pivot_levels.get("pivot")
                    indicators.pivot_r1 = pivot_levels.get("r1")
                    indicators.pivot_r2 = pivot_levels.get("r2")
                    indicators.pivot_s1 = pivot_levels.get("s1")
                    indicators.pivot_s2 = pivot_levels.get("s2")

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

        self._apply_derived_state(indicators, indicators.current_price)
        return indicators

    def _safe_float(self, series_or_value) -> Optional[float]:
        """Safely extract float value from pandas Series or return None."""
        try:
            if hasattr(series_or_value, 'iloc'):
                # It's a Series
                if not series_or_value.empty:
                    value = series_or_value.iloc[-1]
                    if pd.notna(value):
                        value = float(value)
                        if math.isinf(value) or math.isnan(value):
                            return None
                        return value
            else:
                # It's a scalar
                if series_or_value is not None and pd.notna(series_or_value):
                    value = float(series_or_value)
                    if math.isinf(value) or math.isnan(value):
                        return None
                    return value
                return None
        except (ValueError, TypeError, IndexError):
            return None

    def _calculate_cci(self, df: pd.DataFrame, length: int = 20) -> Optional[float]:
        """Calculate CCI manually for stability.

        pandas_ta CCI has shown unstable/extreme outputs in this environment for
        futures bars, so we compute using the canonical formula:
        CCI = (TP - SMA(TP)) / (0.015 * MeanDeviation(TP)).
        """
        if len(df) < length:
            return None

        try:
            high = pd.to_numeric(df["high"], errors="coerce")
            low = pd.to_numeric(df["low"], errors="coerce")
            close = pd.to_numeric(df["close"], errors="coerce")

            tp = (high + low + close) / 3.0
            sma = tp.rolling(length).mean()
            mean_dev = tp.rolling(length).apply(
                lambda x: float((abs(x - x.mean())).mean()),
                raw=False,
            )

            if mean_dev.empty or pd.isna(mean_dev.iloc[-1]) or float(mean_dev.iloc[-1]) <= 1e-9:
                return None

            cci = (tp - sma) / (0.015 * mean_dev)
            value = self._safe_float(cci)
            # Protect UI from pathological spikes caused by near-zero denominators.
            if value is not None and abs(value) > 10000:
                return None
            return value
        except Exception:
            return None

    def _calculate_mfi(self, df: pd.DataFrame, length: int = 14) -> Optional[float]:
        """Calculate MFI with volume-quality guardrails."""
        if len(df) < length:
            return None

        try:
            volume = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
            if float(volume.tail(length).sum()) <= 0.0:
                # No usable volume in lookback window; MFI is not meaningful.
                return None

            value = self._safe_float(
                ta.mfi(
                    pd.to_numeric(df["high"], errors="coerce"),
                    pd.to_numeric(df["low"], errors="coerce"),
                    pd.to_numeric(df["close"], errors="coerce"),
                    volume,
                    length=length,
                )
            )
            if value is None:
                return None
            # MFI is a bounded oscillator.
            return value if 0.0 <= value <= 100.0 else None
        except Exception:
            return None

    def _calculate_pivot_levels(self, df: pd.DataFrame, timeframe: str = "1min") -> Optional[Dict[str, float]]:
        """Calculate pivot levels with robust context selection.

        Priority:
        1) Previous completed trading-day OHLC (when timestamps span multiple dates)
        2) Multi-bar lookback window excluding current bar (fallback)
        """
        if df is None or len(df) < 2:
            return None

        source_df: Optional[pd.DataFrame] = None

        try:
            # Preferred source: previous completed trading day.
            if "timestamp" in df.columns:
                ts = pd.to_datetime(df["timestamp"], errors="coerce")
                if ts is not None and not ts.isna().all():
                    dates = sorted(pd.Series(ts.dt.date).dropna().unique())
                    if len(dates) >= 2:
                        previous_date = dates[-2]
                        mask = ts.dt.date == previous_date
                        if bool(mask.any()):
                            source_df = df.loc[mask]

            # Fallback source: recent context excluding current bar.
            if source_df is None or source_df.empty:
                tf = (timeframe or "").strip().lower()
                lookback = 20 if tf in ("1m", "1min", "minute") else 10
                end_idx = len(df) - 1  # exclude current bar
                start_idx = max(0, end_idx - lookback)
                source_df = df.iloc[start_idx:end_idx] if end_idx > 0 else df.iloc[-1:]
                if source_df.empty:
                    source_df = df.iloc[-1:]

            high = pd.to_numeric(source_df["high"], errors="coerce").max()
            low = pd.to_numeric(source_df["low"], errors="coerce").min()
            close = pd.to_numeric(source_df["close"], errors="coerce").iloc[-1]

            if not (pd.notna(high) and pd.notna(low) and pd.notna(close)):
                return None

            high_f = float(high)
            low_f = float(low)
            close_f = float(close)

            pivot = (high_f + low_f + close_f) / 3.0
            return {
                "pivot": pivot,
                "r1": (2.0 * pivot) - low_f,
                "r2": pivot + (high_f - low_f),
                "s1": (2.0 * pivot) - high_f,
                "s2": pivot - (high_f - low_f),
            }
        except Exception:
            return None
    
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
        self._ohlc_data_mtf[key] = self._normalize_ohlc_dataframe(self._ohlc_data_mtf[key])
        
        # Calculate all indicators for this timeframe
        indicators = self._calculate_all_indicators_mtf(instrument, timeframe)
        
        # Store latest
        self._indicators_mtf[key] = indicators
        
        # Cache to Redis with timeframe key
        if self.redis_client:
            try:
                indicators_dict = asdict(indicators)
                for key_name, value in indicators_dict.items():
                    if key_name in ALL_INDICATORS:
                        self._cache_indicator_value(instrument, timeframe, key_name, value)

                self._persist_indicator_metadata(
                    instrument,
                    timeframe,
                    indicators.timestamp,
                    source="candle_mtf",
                    update_type="candle",
                    stream="Y2",
                    bars_available=len(self._ohlc_data_mtf.get((instrument, timeframe), [])),
                )
            except Exception as e:
                logger.warning(f"Failed to cache MTF indicators in Redis: {e}")
        
        self._apply_derived_state(indicators, indicators.current_price)
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
        
        # Keep warm-up threshold aligned with single-timeframe path so
        # indicators like RSI(14) become available as soon as enough bars exist.
        if df is None or len(df) < 10:
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
                    cols = list(macd.columns)
                    macd_col = next((c for c in cols if c.startswith("MACD_") and "MACDh" not in c and "MACDs" not in c), cols[0])
                    hist_col = next((c for c in cols if "MACDh" in c), cols[1])
                    signal_col = next((c for c in cols if "MACDs" in c), cols[2])

                    indicators.macd_value = self._safe_float(macd[macd_col])
                    indicators.macd_signal = self._safe_float(macd[signal_col])
                    indicators.macd_histogram = self._safe_float(macd[hist_col])
            
            # === VOLATILITY INDICATORS ===
            if len(df) >= 20:
                bb = ta.bbands(df["close"], length=20)
                if bb is not None and len(bb.columns) >= 3:
                    cols = list(bb.columns)
                    lower_col = next((c for c in cols if "BBL" in c), cols[0])
                    middle_col = next((c for c in cols if "BBM" in c), cols[1])
                    upper_col = next((c for c in cols if "BBU" in c), cols[2])

                    indicators.bollinger_upper = self._safe_float(bb[upper_col])
                    indicators.bollinger_middle = self._safe_float(bb[middle_col])
                    indicators.bollinger_lower = self._safe_float(bb[lower_col])
                    if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
                        band_span = indicators.bollinger_upper - indicators.bollinger_lower
                        indicators.bollinger_width = (
                            band_span / indicators.bollinger_middle
                        )
                        if band_span != 0:
                            indicators.bollinger_percent_b = (
                                (current_price - indicators.bollinger_lower) / 
                                band_span
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
                indicators.cci_20 = self._calculate_cci(df, length=20)

            if len(df) >= 14:
                indicators.mfi_14 = self._calculate_mfi(df, length=14)

            if len(df) >= 12:
                indicators.roc_12 = self._safe_float(ta.roc(df["close"], length=12))

            if len(df) >= 10:
                indicators.momentum_10 = self._safe_float(ta.mom(df["close"], length=10))

            # === SUPPORT/RESISTANCE ===
            if len(df) >= 1:
                pivot_levels = self._calculate_pivot_levels(df, timeframe)
                if pivot_levels:
                    indicators.pivot_point = pivot_levels.get("pivot")
                    indicators.pivot_r1 = pivot_levels.get("r1")
                    indicators.pivot_r2 = pivot_levels.get("r2")
                    indicators.pivot_s1 = pivot_levels.get("s1")
                    indicators.pivot_s2 = pivot_levels.get("s2")

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
        df = self._normalize_ohlc_dataframe(df)
        
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
                    if key_name in ALL_INDICATORS:
                        self._cache_indicator_value(instrument, timeframe, key_name, value)

                self._persist_indicator_metadata(
                    instrument,
                    timeframe,
                    indicators.timestamp,
                    source="ohlc_bars",
                    update_type="batch_recalculate",
                    stream="Y2",
                    bars_available=len(df),
                )
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

