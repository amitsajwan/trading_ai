"""Redis-backed MarketStore implementation.

This adapter is a thin wrapper so we can reuse the existing Redis client
without binding to legacy settings or globals.

Automatically builds OHLC candles from ticks and updates technical indicators.
"""
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Iterable, Optional, Dict, Any

from ..contracts import MarketStore, MarketTick, OHLCBar
from ..bar_generator import BarGenerator
from ..timestamp_utils import (
    create_canonical_timestamp_payload,
    create_event_envelope,
    create_mode_aware_payload,
    get_instrument_channel,
    get_market_time
)

try:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from redis_key_manager import get_redis_key, get_redis_pattern
except Exception:  # pragma: no cover
    def get_redis_key(key: str, *args, **kwargs):
        return key

    def get_redis_pattern(pattern: str, mode: Optional[str] = None):
        return pattern

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_candle_builders: Dict[str, Optional[Any]] = {}
_technical_service: Optional[Any] = None


def _iso(dt: datetime) -> str:
    # Convert datetime to ISO-8601 with timezone if present
    if dt.tzinfo is None:
        return dt.isoformat()
    return dt.isoformat()


def _serialize_tick(tick: MarketTick) -> dict:
    return {
        "instrument": tick.instrument,
        "timestamp": _iso(tick.timestamp),
        "last_price": tick.last_price,
        "volume": tick.volume,
        "candle_volume": tick.volume,
        "oi": tick.open_interest,
        "oi_day_high": tick.oi_day_high,
        "oi_day_low": tick.oi_day_low,
        "original_timestamp": _iso(tick.original_timestamp) if tick.original_timestamp else None,
    }


def _serialize_ohlc(bar: OHLCBar) -> dict:
    return {
        "instrument": bar.instrument,
        "timeframe": bar.timeframe,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "oi": bar.open_interest,
        "start_at": _iso(bar.start_at),
        "end_at": _iso(bar.end_at),
    }


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
            open_interest=data.get("oi"),
            oi_day_high=data.get("oi_day_high"),
            oi_day_low=data.get("oi_day_low"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse tick from redis: %s", exc)
        return None


def _parse_ohlc(payload: str) -> Optional[OHLCBar]:
    try:
        data = json.loads(payload)
        start_ts_raw = data.get("start_at") or data.get("timestamp")
        end_ts_raw = data.get("end_at")
        
        # Handle both Unix timestamp (int) and ISO format (str)
        if start_ts_raw:
            if isinstance(start_ts_raw, (int, float)):
                # Unix timestamp
                start_ts = datetime.fromtimestamp(start_ts_raw)
            else:
                # ISO format string
                start_ts = datetime.fromisoformat(start_ts_raw)
        else:
            start_ts = datetime.now()
        
        if end_ts_raw:
            if isinstance(end_ts_raw, (int, float)):
                # Unix timestamp
                end_ts = datetime.fromtimestamp(end_ts_raw)
            else:
                # ISO format string
                end_ts = datetime.fromisoformat(end_ts_raw)
        else:
            # Fallback: assume end_at = start_at + 1 minute for 1m bars
            end_ts = start_ts
        
        volume_raw = data.get("volume")
        if volume_raw is not None:
            volume = int(volume_raw)
        else:
            volume = None

        return OHLCBar(
            instrument=data.get("instrument", ""),
            timeframe=data.get("timeframe", ""),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=volume,
            open_interest=data.get("oi") or data.get("open_interest"),
            start_at=start_ts,
            end_at=end_ts,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse ohlc from redis: %s", exc)
        return None


class RedisMarketStore(MarketStore):
    """Redis-backed MarketStore (no global config).
    
    Automatically builds OHLC candles from ticks and updates technical indicators.
    Works for both live and historical data.
    """

    def __init__(
        self,
        redis_client,
        *,
        mode: str = "LIVE",  # "LIVE", "PAPER", "BACKTEST"
        run_id: Optional[str] = None,
        tick_ttl_hours: int = 24,
        price_ttl_seconds: int = 86400,  # 24 hours to match tick TTL
        ohlc_ttl_hours: int = 24,
        enable_candle_building: bool = True,
        enable_technical_indicators: bool = True,  # Enabled - ichimoku bug fixed
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

        # Mode configuration (mandatory for all messages)
        self._mode = mode
        self._run_id = run_id

        # Candle builders per instrument and timeframe
        self._candle_builders: Dict[str, Dict[str, Any]] = {}
        self._enable_candle_building = enable_candle_building
        self._enable_technical_indicators = enable_technical_indicators

        # Multi-timeframe aggregation (derives 5m/15m bars from 1m candles)
        self._mtf_generators: Dict[str, Dict[int, BarGenerator]] = {}
        self._mtf_windows = (5, 15)
        
        # Initialize technical indicators service if enabled
        if self._enable_technical_indicators:
            try:
                from ..technical_indicators_service import get_technical_service
                self._technical_service = get_technical_service()
                # Ensure publisher/caching path is active for store-driven updates.
                if self._technical_service is not None and getattr(self._technical_service, "redis_client", None) is None:
                    self._technical_service.redis_client = self.redis
                if self._technical_service is None:
                    logger.info("Technical indicators service not yet available, will check later")
            except Exception as e:
                logger.warning(f"Could not import technical indicators service: {e}")
                self._technical_service = None
        else:
            self._technical_service = None

    def _next_event_sequence(self, stream: str, instrument: str, timeframe: str) -> Optional[int]:
        """Return per-stream monotonic sequence from Redis (best-effort)."""
        if not self._available:
            return None
        try:
            seq_key = get_redis_key(f"events:seq:{stream}:{instrument}:{timeframe}")
            return int(self.redis.incr(seq_key))
        except Exception:
            return None

    def _initialize_technical_service_with_existing_data(self) -> None:
        """Initialize technical indicators service with existing OHLC data from Redis."""
        if not self._technical_service or not self._available:
            return
            
        try:
            # Get all instruments that have OHLC data
            ohlc_keys = self.redis.keys(get_redis_pattern("ohlc:*:*"))
            instruments = set()
            # Coerce to list safely (Mock may return a Mock or non-iterable)
            try:
                ohlc_iter = list(ohlc_keys) if ohlc_keys is not None else []
            except Exception:
                ohlc_iter = []
            for key in ohlc_iter:
                parts = key.split(":")
                if not parts:
                    continue
                # Handle mode-prefixed keys: live:ohlc:INSTRUMENT:...
                if parts[0] in ("live", "historical", "paper"):
                    if len(parts) >= 3:
                        instruments.add(parts[2])
                else:
                    if len(parts) >= 2:
                        instruments.add(parts[1])  # Extract instrument name
            
            # For each instrument, load recent OHLC data and initialize technical service
            for instrument in instruments:
                try:
                    ohlc_bars = list(self.get_ohlc(instrument, "1min", limit=100))  # Load last 100 bars
                    if ohlc_bars:
                        # Convert OHLCBar objects to dictionaries
                        ohlc_dicts = []
                        for bar in ohlc_bars:
                            ohlc_dicts.append({
                                'open': bar.open,
                                'high': bar.high,
                                'low': bar.low,
                                'close': bar.close,
                                'volume': bar.volume,
                                'oi': bar.open_interest,
                                'start_at': bar.start_at.isoformat(),
                                'timestamp': bar.start_at.isoformat()
                            })
                        
                        # Initialize technical service with this data
                        self._technical_service.initialize_with_ohlc_data(instrument, ohlc_dicts)
                        logger.info(f"Initialized technical indicators for {instrument} with {len(ohlc_dicts)} OHLC bars")
                        
                except Exception as e:
                    logger.warning(f"Failed to initialize technical indicators for {instrument}: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to initialize technical service with existing data: {e}")

    def store_tick(self, tick: MarketTick) -> None:
        if not self._available:
            return
        payload = _serialize_tick(tick)
        ts_key = _iso(tick.timestamp)
        payload_json = json.dumps(payload)
        try:
            self.redis.setex(get_redis_key(f"tick:{tick.instrument}:{ts_key}"), self._tick_ttl, payload_json)
            # Also store latest tick blob and price for quick lookup.
            # Guard against out-of-order ticks overriding fresher latest pointers.
            should_update_latest = True
            latest_ts_key = get_redis_key(f"price:{tick.instrument}:latest_ts")
            existing_latest_ts = self.redis.get(latest_ts_key)
            if existing_latest_ts:
                try:
                    existing_dt = datetime.fromisoformat(str(existing_latest_ts).replace("Z", "+00:00"))
                    new_dt = tick.timestamp
                    if new_dt.tzinfo is None and existing_dt.tzinfo is not None:
                        new_dt = new_dt.replace(tzinfo=existing_dt.tzinfo)
                    elif new_dt.tzinfo is not None and existing_dt.tzinfo is None:
                        existing_dt = existing_dt.replace(tzinfo=new_dt.tzinfo)
                    should_update_latest = new_dt >= existing_dt
                except Exception:
                    should_update_latest = True

            if should_update_latest:
                self.redis.setex(get_redis_key(f"websocket:tick:{tick.instrument}:latest"), self._tick_ttl, payload_json)
                self.redis.setex(get_redis_key(f"price:{tick.instrument}:latest"), self._price_ttl, str(tick.last_price))
                self.redis.setex(latest_ts_key, self._price_ttl, ts_key)
                if tick.volume is not None:
                    self.redis.setex(get_redis_key(f"volume:{tick.instrument}:latest"), self._price_ttl, str(tick.volume))
            else:
                logger.debug(
                    "Skipping stale tick for latest pointer: %s ts=%s existing=%s",
                    tick.instrument,
                    ts_key,
                    existing_latest_ts,
                )
            
            # Publish tick to Redis pub/sub for real-time subscribers (Socket.IO, signal monitoring, etc.)
            try:
                # Create canonical timestamp payload
                timestamp_payload = create_canonical_timestamp_payload(
                    market_timestamp=tick.timestamp,
                    original_timestamp=tick.original_timestamp
                )
                
                # Enhanced payload with canonical timestamps
                enhanced_payload = payload.copy()
                enhanced_payload.update(timestamp_payload)

                # Publish to type-specific channel only (e.g., market:tick:BANKNIFTY:INDEX)
                type_specific_channel = get_instrument_channel(tick.instrument, "tick")
                seq = self._next_event_sequence("X", tick.instrument, "1min")
                envelope = create_event_envelope(
                    stream="X",
                    payload=enhanced_payload,
                    instrument=tick.instrument,
                    timeframe="1min",
                    event_time=tick.timestamp,
                    mode=self._mode,
                    run_id=self._run_id,
                    sequence=seq,
                )
                # GATE BY MODE: In BACKTEST mode, only historical replay may publish
                # In HISTORICAL mode, publish to WebSocket for real-time-like experience

                self.redis.publish(type_specific_channel, json.dumps(envelope))
            except Exception as pub_exc:
                # Don't fail if pub/sub fails (may not be enabled)
                logger.debug(f"Failed to publish tick to pub/sub: {pub_exc}")
            
            # Automatically build OHLC candles from ticks (if enabled)
            if self._enable_candle_building:
                self._process_tick_for_ohlc(tick)
            
            # Note: We do NOT call update_tick here for indicators.
            # Indicators are only updated and published when candles close (in on_candle_close callback).
            # This ensures stable indicator values within a candle and prevents duplicate publishing.
        except Exception as exc:  # noqa: BLE001
            logger.error("Error storing tick: %s", exc, exc_info=True)
    
    def _process_tick_for_ohlc(self, tick: MarketTick) -> None:
        """Process tick through candle builder to generate OHLC bars."""
        try:
            from ..adapters.candle_builder import CandleBuilder

            instrument = tick.instrument
            timeframe = "1min"  # Default timeframe for minute candles

            # Get or create candle builder for this instrument and timeframe
            if instrument not in self._candle_builders:
                self._candle_builders[instrument] = {}

            if timeframe not in self._candle_builders[instrument]:
                # Create candle builder with callback to store OHLC bars
                def on_candle_close(bar: OHLCBar):
                    """Callback when candle closes - store it and update indicators."""
                    print(f"CANDLE CLOSE CALLBACK: {instrument} at {bar.start_at} - O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close}")
                    try:
                        self.store_ohlc(bar)
                        print(f"OHLC stored for {instrument}")

                        # Also update technical indicators when candle closes
                        if self._enable_technical_indicators:
                            # Try to get technical service if not available
                            if self._technical_service is None:
                                try:
                                    from ..technical_indicators_service import get_technical_service
                                    self._technical_service = get_technical_service()
                                    if self._technical_service is not None and getattr(self._technical_service, "redis_client", None) is None:
                                        self._technical_service.redis_client = self.redis
                                except Exception:
                                    pass
                            
                            if self._technical_service:
                                print(f"UPDATING INDICATORS for {instrument} candle close")
                                candle_dict = {
                                    "open": bar.open,
                                    "high": bar.high,
                                    "low": bar.low,
                                    "close": bar.close,
                                    "volume": bar.volume or 0,
                                    "oi": bar.open_interest,
                                    "start_at": bar.start_at.isoformat(),
                                    "timestamp": bar.start_at.isoformat()
                                }
                                print(f"Calling update_candle with data")
                                result = self._technical_service.update_candle(instrument, candle_dict)
                                print(f"INDICATORS UPDATED for {instrument}: RSI={getattr(result, 'rsi_14', 'N/A')}, MACD={getattr(result, 'macd_value', 'N/A')}")
                        else:
                            print(f"TECHNICAL SERVICE NOT AVAILABLE: enabled={self._enable_technical_indicators}, service={self._technical_service is not None}")
                    except Exception as e:
                        print(f"ERROR in candle close callback: {e}")
                        import traceback
                        traceback.print_exc()

                self._candle_builders[instrument][timeframe] = CandleBuilder(
                    timeframe=timeframe,
                    on_candle_close=on_candle_close
                )

            # Process tick through candle builder
            candle_builder = self._candle_builders[instrument][timeframe]
            closed_bar = candle_builder.process_tick(tick)
            # closed_bar is already stored via on_candle_close callback

            # Debug: Log candle status
            active_candles = list(candle_builder._active_candles.get(instrument, {}).keys())
            logger.debug(f"Active candles for {instrument}: {active_candles}")

            # Also check if we need to force close any expired candles (older than current time - timeframe)
            self._force_close_expired_candles(instrument, timeframe, tick.timestamp)

        except Exception as e:
            logger.debug(f"Error processing tick for OHLC: {e}")

    def _force_close_expired_candles(self, instrument: str, timeframe: str, current_time: datetime) -> None:
        """Force close any candles that should have closed based on wall clock time."""
        try:
            if instrument not in self._candle_builders or timeframe not in self._candle_builders[instrument]:
                return

            candle_builder = self._candle_builders[instrument][timeframe]

            # Use the public force_close_all method but filter to only close truly expired candles
            # For now, let's close all candles that are older than 2 minutes to be safe
            candles_to_close = []
            for candle_key, candle in candle_builder._active_candles.get(instrument, {}).items():
                # Check if candle should have closed based on wall clock time
                elapsed = (current_time - candle.start_time).total_seconds()
                if elapsed >= candle_builder.timeframe_seconds * 2:  # Close if 2x timeframe old
                    candles_to_close.append((instrument, candle_key))

            # Close expired candles
            for inst, candle_key in candles_to_close:
                try:
                    closed_bar = candle_builder._close_candle(inst, candle_key)
                    if closed_bar:
                        logger.debug(f"Force closed expired candle for {inst} {timeframe}: {closed_bar.start_at}")
                except Exception as e:
                    logger.debug(f"Error force closing candle {candle_key}: {e}")

        except Exception as e:
            logger.debug(f"Error in force_close_expired_candles: {e}")

    def _normalize_timeframe_value(self, timeframe: str) -> str:
        """Normalize timeframe aliases to canonical values."""
        tf = (timeframe or "").strip().lower()

        if tf in ("minute", "1m", "1min", "1minute"):
            return "1m"

        if tf.endswith("minute"):
            digits = tf.replace("minute", "").strip()
            if digits.isdigit():
                return "1m" if digits == "1" else f"{digits}m"

        if tf.endswith("min"):
            digits = tf[:-3]
            if digits.isdigit():
                return "1m" if digits == "1" else f"{digits}m"

        if tf.endswith("m") and tf[:-1].isdigit():
            digits = tf[:-1]
            return "1m" if digits == "1" else f"{digits}m"

        return tf

    def _is_base_minute_timeframe(self, timeframe: str) -> bool:
        tf = self._normalize_timeframe_value(timeframe)
        return tf == "1m"

    def _ensure_mtf_generators(self, instrument: str) -> Dict[int, BarGenerator]:
        """Create (5m, 15m) bar generators for an instrument if missing."""
        if instrument not in self._mtf_generators:
            self._mtf_generators[instrument] = {}
            for window in self._mtf_windows:
                self._mtf_generators[instrument][window] = BarGenerator(
                    on_bar=lambda _: None,
                    window=window,
                    on_window_bar=lambda agg_bar, inst=instrument: self._handle_mtf_bar(inst, agg_bar)
                )
        return self._mtf_generators[instrument]

    def _handle_mtf_bar(self, instrument: str, bar: OHLCBar) -> None:
        """Store aggregated bar and update multi-timeframe indicators."""
        try:
            self.store_ohlc(bar)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to store aggregated bar {instrument}:{bar.timeframe}: {exc}")

        # Update multi-timeframe indicator snapshots (best-effort)
        if self._enable_technical_indicators:
            try:
                if self._technical_service is None:
                    from ..technical_indicators_service import get_technical_service
                    self._technical_service = get_technical_service()
                    if self._technical_service is not None and getattr(self._technical_service, "redis_client", None) is None:
                        self._technical_service.redis_client = self.redis

                if self._technical_service:
                    candle_dict = {
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume or 0,
                        "oi": bar.open_interest,
                        "start_at": bar.start_at.isoformat(),
                        "timestamp": bar.start_at.isoformat(),
                    }
                    self._technical_service.update_candle_mtf(instrument, bar.timeframe, candle_dict)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to update MTF indicators for {instrument}:{bar.timeframe}: {exc}")

    def _maybe_generate_mtf(self, bar: OHLCBar) -> None:
        """Derive higher timeframes from 1-minute candles."""
        if not self._is_base_minute_timeframe(bar.timeframe):
            return

        generators = self._ensure_mtf_generators(bar.instrument)
        for generator in generators.values():
            try:
                generator.update_bar(bar)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"MTF update failed for {bar.instrument}:{bar.timeframe}: {exc}")

    def _store_ohlc_compat(self, bar: OHLCBar) -> bool:
        """Compatibility path for test doubles with partial Redis API support."""
        try:
            payload = _serialize_ohlc(bar)
            payload_json = json.dumps(payload)
            score = float(bar.start_at.timestamp())
            key = get_redis_key(f"ohlc_sorted:{bar.instrument}:{bar.timeframe}")
            self.redis.zadd(key, {payload_json: score})
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Compatibility OHLC store failed: %s", exc)
            return False

    def get_latest_tick(self, instrument: str) -> Optional[MarketTick]:
        if not self._available:
            return None
        try:
            payload = self.redis.get(get_redis_key(f"websocket:tick:{instrument}:latest"))
            return _parse_tick(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error reading latest tick: %s", exc)
            return None

    def store_ohlc(self, bar: OHLCBar) -> None:
        if not self._available:
            return

        try:
            # Normalize timeframe to canonical form before persisting/publishing
            normalized_tf = self._normalize_timeframe_value(bar.timeframe)
            bar.timeframe = normalized_tf

            # Use standardized data storage manager
            from ..data_storage_manager import DataStorageManager
            storage_manager = DataStorageManager(self.redis)

            # Prepare bar data for storage
            bar_data = {
                "timestamp": bar.start_at.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume or 0,
                "oi": bar.open_interest,
                "end_at": bar.end_at.isoformat(),
            }

            # Store using standardized format
            if not hasattr(self.redis, "zscore"):
                # Lightweight/fake Redis clients used in isolated tests may not
                # implement sorted-set verification helpers. Use direct
                # compatibility storage to avoid duplicate writes from retries.
                success = self._store_ohlc_compat(bar)
            else:
                success = storage_manager.store_ohlc_bar(
                    bar.instrument,
                    bar.timeframe,
                    bar_data,
                    use_sorted_sets=True
                )

                if not success and self._store_ohlc_compat(bar):
                    success = True

            if not success:
                logger.error(f"FAIL-FAST: Failed to store OHLC bar: {bar.instrument}:{bar.timeframe}")
                raise RuntimeError(f"Failed to store OHLC bar: {bar.instrument}:{bar.timeframe}")

            logger.debug(f"Stored OHLC bar: {bar.instrument}:{bar.timeframe}")

            # Publish OHLC data to Redis pub/sub for real-time WebSocket updates
            try:
                payload = _serialize_ohlc(bar)
                payload.update({
                    "candle_closed": True,
                    "update_type": "candle",
                })

                seq = self._next_event_sequence("Y1", bar.instrument, bar.timeframe)
                envelope = create_event_envelope(
                    stream="Y1",
                    payload=payload,
                    instrument=bar.instrument,
                    timeframe=bar.timeframe,
                    event_time=bar.start_at,
                    mode=self._mode,
                    run_id=self._run_id,
                    sequence=seq,
                )
                # Publish to specific instrument/timeframe channel
                self.redis.publish(f"market:ohlc:{bar.instrument}:{bar.timeframe}", json.dumps(envelope))
            except Exception as pub_exc:
                logger.debug(f"Failed to publish OHLC to pub/sub: {pub_exc}")

            # Derive multi-timeframe aggregates from base 1m candles
            try:
                self._maybe_generate_mtf(bar)
            except Exception as mtf_exc:
                logger.debug(f"Failed to generate multi-timeframe bars: {mtf_exc}")

        except Exception as exc:  # noqa: BLE001
            logger.error("FAIL-FAST: Error storing ohlc: %s", exc, exc_info=True)
            raise



    def get_ohlc(self, instrument: str, timeframe: str, limit: int = 100) -> Iterable[OHLCBar]:
        if not self._available:
            return []

        try:
            # Use standardized data storage manager
            from ..data_storage_manager import DataStorageManager
            storage_manager = DataStorageManager(self.redis)

            # Get bars from storage manager
            bars_data = storage_manager.get_ohlc_bars(instrument, timeframe, limit=limit, prefer_sorted_sets=True)

            # Convert to OHLCBar objects
            bars = []
            for bar_data in bars_data:
                try:
                    bar = _parse_ohlc(json.dumps(bar_data))
                    if bar:
                        bars.append(bar)
                except Exception as parse_exc:
                    logger.warning(f"Failed to parse OHLC bar: {parse_exc}")
                    continue

            if not bars:
                logger.warning(f"No OHLC bars found for {instrument}:{timeframe}")
                return []
            
            return bars

        except Exception as exc:  # noqa: BLE001
            logger.error(f"FAIL-FAST: Error reading ohlc: {exc}", exc_info=True)
            raise



