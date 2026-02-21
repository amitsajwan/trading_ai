"""Volume enhancer (LTP processor).

Processes WebSocket ticks from Redis and applies volume logic.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

try:
    import pytz
except ImportError:
    pytz = None

try:
    import redis  # type: ignore
except ImportError:
    redis = None

try:
    from kiteconnect import KiteConnect  # type: ignore
except ImportError:
    KiteConnect = None

# Import config
try:
    from config import get_config
    config = get_config()
except ImportError:
    config = None

# Import MarketTick
try:
    from market_data.contracts import MarketTick
except ImportError:
    MarketTick = None

try:
    from redis_key_manager import get_redis_key
except Exception:
    get_redis_key = None

try:
    from market_data.env_settings import redis_config as md_redis_config, resolve_instrument_symbol
except Exception:
    md_redis_config = None
    resolve_instrument_symbol = None

try:
    from market_data.volume_utils import compute_volume_diff, extract_volume_fields
except Exception:
    compute_volume_diff = None
    extract_volume_fields = None


def get_symbol_config():
    if config:
        trading_symbol = config.instrument_trading_symbol
        symbol = config.instrument_symbol
        exchange = config.instrument_exchange

        if trading_symbol and ("FUT" in trading_symbol.upper() or "CE" in trading_symbol.upper() or "PE" in trading_symbol.upper()):
            exchange = "NFO"
        elif "FUT" in symbol.upper() or "CE" in symbol.upper() or "PE" in symbol.upper():
            exchange = "NFO"

        return exchange, symbol
    fallback_symbol = resolve_instrument_symbol() if resolve_instrument_symbol else ""
    return os.getenv("INSTRUMENT_EXCHANGE", "NSE"), (fallback_symbol or "UNKNOWN")


def sanitize_key(symbol: str) -> str:
    return symbol.upper().replace(" ", "")


class LTPDataProcessor:
    """Redis subscriber that processes WebSocket ticks and applies volume logic."""

    def __init__(self, market_memory: Any) -> None:
        print(f"DEBUG: LTPDataProcessor.__init__ called with market_memory: {type(market_memory)} {market_memory}")
        self.market_memory = market_memory
        self.exchange, self.symbol = get_symbol_config()
        self.key = config.instrument_key if config else sanitize_key(self.symbol)
        self.price = 44000.0
        self.drift = 0.0

        self.core_instrument = self._get_core_instrument()
        self.volume_source = self._determine_volume_source()

        if redis:
            redis_cfg = config.get_redis_config(decode_responses=True) if config else None
            if redis_cfg is None and md_redis_config is not None:
                redis_cfg = md_redis_config(decode_responses=True)
            if redis_cfg is None:
                raise RuntimeError("Redis configuration unavailable")
            self.redis_client = redis.Redis(**redis_cfg)
            self.pubsub = self.redis_client.pubsub()
        else:
            self.redis_client = None
            self.pubsub = None

        self.last_volume = {}
        self.last_timestamp = {}
        self._progress_log_interval = int(os.getenv("LTP_PROCESSOR_LOG_EVERY", "500"))

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _get_core_instrument(self) -> Optional[str]:
        trading_symbol = (config.instrument_trading_symbol if config else self.symbol) or ""
        normalized = trading_symbol.upper().replace(" ", "")
        if normalized in {"BANKNIFTY", "NIFTY"}:
            return normalized
        match = re.match(r"^(BANKNIFTY|NIFTY)\d{2}[A-Z]{3}(?:FUT|CE|PE)$", normalized)
        if match:
            return match.group(1)
        return None

    def _determine_volume_source(self) -> str:
        if self.core_instrument:
            return "core"
        return "direct"

    def _calculate_volume_diff(self, instrument_name: str, current_volume: int, timestamp: datetime) -> int:
        if compute_volume_diff is None:
            key = instrument_name
            if key not in self.last_volume:
                self.last_volume[key] = current_volume
                self.last_timestamp[key] = timestamp
                return 0

            last_vol = self.last_volume.get(key, 0)
            volume_diff = max(0, current_volume - last_vol)
            self.last_volume[key] = current_volume
            self.last_timestamp[key] = timestamp
            return volume_diff

        return compute_volume_diff(
            instrument_name,
            current_volume,
            timestamp,
            last_volume=self.last_volume,
            last_timestamp=self.last_timestamp,
            reset_gap_seconds=300,
        )

    def _extract_volume(self, tick_data: Dict[str, Any]) -> Tuple[Optional[int], str]:
        if extract_volume_fields is None:
            return None, "missing"
        return extract_volume_fields(tick_data)

    def _get_enhanced_volume(self, tick_data: Dict[str, Any], instrument_name: str, timestamp: datetime) -> Tuple[int, str]:
        current_volume, volume_kind = self._extract_volume(tick_data)

        self.logger.debug(f"[LTP] _get_enhanced_volume called for {instrument_name}, current_volume: {current_volume}")

        if current_volume is None:
            return 0, "missing"

        if volume_kind == "delta":
            self.logger.debug(f"[LTP] Using delta volume directly for {instrument_name}")
            return max(0, current_volume), "direct"

        if instrument_name == self.core_instrument:
            self.logger.debug(f"[LTP] Using direct volume for core instrument: {instrument_name}")
            return current_volume, "core"

        self.logger.debug("[LTP] Market memory disabled, skipping core instrument volume lookup")

        self.logger.debug(f"[LTP] Using cumulative volume with differencing for derivative: {instrument_name}")
        volume_diff = self._calculate_volume_diff(instrument_name, current_volume, timestamp)
        self.logger.debug(f"[LTP] Calculated volume diff: {volume_diff}")
        return volume_diff, "direct"

    def _process_tick(self, tick_data: Dict[str, Any]) -> None:
        try:
            instrument_name = tick_data.get("instrument", "unknown")
            timestamp_str = tick_data.get("timestamp", datetime.now().isoformat())

            self.logger.debug(f"[LTP] Processing tick for instrument: {instrument_name}")
            self.logger.debug(f"[LTP] Tick data keys: {list(tick_data.keys())}")

            assert instrument_name != "unknown", f"Missing instrument_token in tick_data: {tick_data}"
            assert "last_price" in tick_data, f"Missing last_price in tick_data: {tick_data}"

            if not any(key in tick_data for key in ("volume", "cumulative_volume", "volume_traded", "candle_volume")):
                self.logger.warning(f"[LTP] Missing volume fields in tick_data: {tick_data}")

            timestamp_raw = (
                tick_data.get("market_timestamp")
                or tick_data.get("timestamp")
                or tick_data.get("exchange_timestamp")
            )
            timestamp_str = timestamp_raw if isinstance(timestamp_raw, str) else timestamp_str

            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_str))
                except Exception:
                    timestamp = datetime.now(timezone.utc)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            self.logger.debug(f"[LTP] Parsed timestamp: {timestamp.isoformat()}")

            if self.market_memory is not None:
                self.logger.error(f"[LTP] ERROR: market_memory should be None but is: {type(self.market_memory)}")
                raise AssertionError("market_memory should be disabled")

            self.logger.debug(f"[LTP] Getting enhanced volume for {instrument_name}")
            final_volume, volume_source = self._get_enhanced_volume(tick_data, instrument_name, timestamp)
            self.logger.debug(f"[LTP] Enhanced volume: {final_volume} (source: {volume_source})")

            assert final_volume >= 0, f"Volume cannot be negative: {final_volume}"

            cumulative_volume = None
            for key in ("cumulative_volume", "volume_traded"):
                if tick_data.get(key) is not None:
                    try:
                        cumulative_volume = int(tick_data[key])
                    except (TypeError, ValueError):
                        cumulative_volume = None
                    break

            enhanced_data = {
                **tick_data,
                "instrument": instrument_name,
                "timestamp": timestamp.isoformat(),
                "last_price": tick_data.get("last_price", 0),
                "candle_volume": int(final_volume),
                "volume": final_volume,
                "volume_source": volume_source,
                "core_instrument": self.core_instrument if self.core_instrument != instrument_name else None,
            }
            if cumulative_volume is not None:
                enhanced_data["cumulative_volume"] = cumulative_volume

            self.logger.debug(f"[LTP] Created enhanced data payload with keys: {list(enhanced_data.keys())}")

            if self.redis_client:
                message = json.dumps(enhanced_data)

                legacy_channel = f"enhanced_ticks:{self.key}"
                channels = [legacy_channel]
                if get_redis_key:
                    prefixed_channel = get_redis_key(legacy_channel)
                    if prefixed_channel not in channels:
                        channels.append(prefixed_channel)

                for channel in channels:
                    self.redis_client.publish(channel, message)

                self.logger.debug(
                    f"[LTP] Published enhanced tick to {', '.join(channels)}: instrument={instrument_name}, "
                    f"price={enhanced_data['last_price']}, volume={final_volume} ({volume_source})"
                )
            else:
                self.logger.error("[LTP] ERROR: Redis client not available")
                raise AssertionError("Redis client should be available")

            self.logger.debug("[LTP] Market memory storage skipped (disabled)")

        except Exception as e:
            import traceback
            self.logger.error(f"[LTP] Error processing tick: {e}")
            self.logger.error(f"[LTP] Stack trace: {traceback.format_exc()}")
            self.logger.error(f"[LTP] Tick data: {tick_data}")
            raise

    def start_processing(self) -> None:
        self.logger.info("[LTP] Starting LTP Data Processor...")

        if not self.pubsub:
            self.logger.error("[LTP] ERROR: Redis pubsub not available")
            raise AssertionError("Redis pubsub should be available")

        try:
            pattern = f"market:tick:{self.key}:*"
            try:
                self.pubsub.psubscribe(pattern)
                print(f"[DEBUG] Subscribed successfully to {pattern}")
                print(f"[DEBUG] About to listen...")
            except Exception as e:
                print(f"[DEBUG] Subscribe failed: {e}")
                raise

            message_count = 0
            for message in self.pubsub.listen():
                self.logger.debug(f"[LTP] Received message from pubsub.listen(): {message}")
                if message["type"] in ("message", "pmessage"):
                    message_count += 1
                    if message_count == 1 or message_count % self._progress_log_interval == 0:
                        self.logger.info(f"[LTP] Processed {message_count} messages from Redis stream")

                    try:
                        raw_data = message["data"]
                        self.logger.debug(f"[LTP] Raw message data type: {type(raw_data)}")

                        if isinstance(raw_data, bytes):
                            try:
                                raw_data_str = raw_data.decode('utf-8')
                                self.logger.debug(f"[LTP] Raw message decoded successfully, first 200 chars: {raw_data_str[:200]}")
                            except Exception as de:
                                self.logger.error(f"[LTP] Error decoding message bytes: {de}")
                                decoded_replace = raw_data.decode('utf-8', errors='replace')
                                self.logger.error(f"[LTP] Decoded with replace errors (first 200): {decoded_replace[:200]}")
                                raise
                        else:
                            raw_data_str = raw_data
                            self.logger.debug(f"[LTP] Raw data already string, first 200 chars: {raw_data_str[:200]}")

                        evt = json.loads(raw_data_str)
                        tick_data = evt.get("payload") if isinstance(evt, dict) and isinstance(evt.get("payload"), dict) else evt
                        self.logger.debug(
                            f"[LTP] Parsed tick data: instrument={tick_data.get('instrument', 'unknown')}, "
                            f"price={tick_data.get('last_price', 'unknown')}"
                        )
                        self._process_tick(tick_data)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"[LTP] JSON Decode Error: {e}")
                        self.logger.error(f"[LTP] Error details - line:{e.lineno}, col:{e.colno}, pos:{e.pos}")
                        try:
                            if 'raw_data_str' in locals():
                                start = max(0, e.pos - 30)
                                end = min(len(raw_data_str), e.pos + 30)
                                context = raw_data_str[start:end]
                                self.logger.error(f"[LTP] Context around error: ...{repr(context)}...")
                            else:
                                self.logger.error("[LTP] Could not get context - raw_data not decoded")
                        except Exception as ctx_err:
                            self.logger.error(f"[LTP] Error getting context: {ctx_err}")
                    except Exception as e:
                        self.logger.error(f"[LTP] Error processing message: {e}")
                        import traceback
                        self.logger.error(f"[LTP] Stack trace: {traceback.format_exc()}")

        except KeyboardInterrupt:
            self.logger.info("[LTP] Stopping LTP processor...")
        except Exception as e:
            self.logger.error(f"[LTP] Error in LTP processor: {e}")
            import traceback
            self.logger.error(f"[LTP] Stack trace: {traceback.format_exc()}")
        finally:
            if self.pubsub:
                self.pubsub.close()
                self.logger.info("[LTP] Closed Redis pubsub connection")
                self.pubsub.close()
                self.logger.info("[LTP] Closed Redis pubsub connection")


def main():
    print("[ltp] Starting LTP Data Processor...")

    market_memory = None

    processor = LTPDataProcessor(market_memory)
    processor.start_processing()


class LTPDataCollector:
    """Compatibility wrapper collector that writes a single synthetic tick to Redis."""
    def __init__(self, kite=None, market_memory=None):
        self.kite = kite
        self.market_memory = market_memory
        try:
            from config import get_config
            self.cfg = get_config()
            import redis as _redis
            self.redis_client = _redis.Redis(**self.cfg.get_redis_config())
            self.key = getattr(self.cfg, 'redis_price_key', f"price:{self.cfg.instrument_key}:latest")
        except Exception:
            self.cfg = None
            self.redis_client = None
            self.key = None

    def collect_once(self) -> None:
        """Write a synthetic tick to Redis (used as fallback when no kite provider)."""
        try:
            import random
            if not self.redis_client or not self.key:
                return

            price = round(45000.0 + random.uniform(-50, 50), 2)
            ts = datetime.now().isoformat()

            base_last_price_key = f"{self.cfg.redis_price_key}:last_price"
            base_latest_ts_key = f"{self.cfg.redis_price_key}:latest_ts"
            base_quote_key = f"{self.cfg.redis_price_key}:quote"
            keys = [
                (base_last_price_key, str(price)),
                (base_latest_ts_key, ts),
            ]
            quote = {
                "last_price": price,
                "ohlc": {"close": price},
                "volume": 1000
            }
            keys.append((base_quote_key, json.dumps(quote)))

            for key, value in keys:
                self.redis_client.set(key, value)
                if get_redis_key:
                    prefixed_key = get_redis_key(key)
                    if prefixed_key != key:
                        self.redis_client.set(prefixed_key, value)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Synthetic LTP collect_once failed: {e}")


def build_kite_client() -> None:
    """Wrapper to the shared factory used in depth_collector.

    Returns the provider (or None) - kept for compatibility with existing tests.
    """
    try:
        from market_data.sources.depth import build_kite_client as _bk
        return _bk()
    except Exception:
        return None


class VolumeEnhancer(LTPDataProcessor):
    """Alias for LTPDataProcessor."""


def run_volume_enhancer(market_memory: Any = None) -> None:
    processor = VolumeEnhancer(market_memory)
    processor.start_processing()


if __name__ == "__main__":
    main()
