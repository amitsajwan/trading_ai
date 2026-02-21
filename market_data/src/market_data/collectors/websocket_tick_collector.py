#!/usr/bin/env python3
"""WebSocket Tick Collector - Real-time tick collection using KiteTicker.

This collector:
1. Uses KiteTicker WebSocket to get real-time market ticks
2. Publishes raw ticks to Redis pub/sub channels
3. Handles volume differencing for candle calculation
4. Supports multiple instruments simultaneously

Architecture: WebSocket → Redis Pub/Sub → LTP Processor → Enhanced Data
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Set, TYPE_CHECKING, List
from collections import defaultdict

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from kiteconnect import KiteConnect, KiteTicker
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    if not TYPE_CHECKING:
        KiteTicker = None

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from market_data.sources.mock_kite_websocket import create_mock_ticker
except Exception:
    create_mock_ticker = None

try:
    from market_data.adapters.redis_store import RedisMarketStore
    from market_data.contracts import MarketTick
except Exception:
    RedisMarketStore = None
    MarketTick = None

try:
    from market_data.sources.historical_kite_websocket import create_historical_ticker
except Exception:
    create_historical_ticker = None

from market_data.timestamp_utils import (
    get_instrument_channel,
    create_canonical_timestamp_payload,
    create_event_envelope,
    normalize_timestamp,
    IST,
)
from market_data.env_settings import credentials_path_candidates, redis_config, resolve_instrument_symbol
from market_data.kite_client import create_kite_client

# Import config
try:
    from config import get_config
    config = get_config()
    print(f"DEBUG: Config loaded: {config.instrument_symbol if config else 'None'}")
except Exception as e:
    print(f"DEBUG: Config import failed: {e}")
    config = None

# Import EventEngine (optional)
try:
    from market_data.event_engine import EventEngine, Event, EVENT_TICK
    from market_data.enhanced_tick import EnhancedMarketTick
    EVENT_ENGINE_AVAILABLE = True
except ImportError:
    EVENT_ENGINE_AVAILABLE = False
    if not TYPE_CHECKING:
        EventEngine = None
        Event = None

logger = logging.getLogger(__name__)


class WebSocketTickCollector:
    """Real-time tick collector using Zerodha KiteTicker WebSocket.
    
    Optionally supports EventEngine for event-driven architecture.
    """

    def __init__(self, instruments: Optional[Dict[str, str]] = None, event_engine: Optional[EventEngine] = None):
        """Initialize WebSocket tick collector.

        Args:
            instruments: Dict mapping trading symbols to instrument tokens
            event_engine: Optional EventEngine for publishing tick events (backward compatible)
        """
        if not REDIS_AVAILABLE:
            raise RuntimeError("redis library not available")

        self.ws_source = os.getenv("KITE_WS_SOURCE", "real").strip().lower()

        # Credentials are required only for real websocket source
        self.api_key, self.access_token = self._load_credentials()
        if self.ws_source == "real":
            if not KITE_AVAILABLE:
                raise RuntimeError("kiteconnect library not available")
            if not self.api_key or not self.access_token:
                raise RuntimeError("Kite credentials not available")
            self.kite = create_kite_client(api_key=self.api_key, access_token=self.access_token)
        else:
            self.kite = None

        # Initialize Redis
        self.redis_client = redis.Redis(**redis_config(decode_responses=True))
        
        # Initialize Redis store for automatic OHLC building
        if RedisMarketStore:
            self.store = RedisMarketStore(self.redis_client, mode="live")
            logger.info("Redis store initialized for automatic OHLC building")
        else:
            self.store = None
            logger.warning("Redis store not available - OHLC building disabled")
        
        # Optional EventEngine support (backward compatible)
        self.event_engine = event_engine
        if self.event_engine and EVENT_ENGINE_AVAILABLE:
            logger.info("EventEngine integration enabled")
        elif event_engine and not EVENT_ENGINE_AVAILABLE:
            logger.warning("EventEngine requested but not available")

        # Instrument configuration
        self.instruments = instruments or self._get_default_instruments()
        self.instrument_tokens = [int(token) for token in self.instruments.keys()]
        self.token_to_symbol = self.instruments

        # Volume tracking for differencing
        self.last_cumulative_volume: Dict[str, int] = {}

        # WebSocket state
        self.ticker: Optional["KiteTicker"] = None
        self.connected = False
        self.running = False

        logger.info(f"WebSocketTickCollector initialized for {len(self.instruments)} instruments (source={self.ws_source})")

    def _load_credentials(self) -> tuple[str, str]:
        """Load Kite credentials from environment or file."""
        # Try environment variables first
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')

        if api_key and access_token:
            return api_key, access_token

        # Fall back to known credentials.json locations
        for cred_path in credentials_path_candidates():
            if not cred_path.exists():
                continue
            try:
                with cred_path.open("r", encoding="utf-8") as f:
                    creds = json.load(f)
                loaded_key = creds.get("api_key")
                loaded_token = creds.get("access_token")
                if loaded_key and loaded_token:
                    return loaded_key, loaded_token
            except Exception as e:
                logger.error(f"Error loading credentials from {cred_path}: {e}")

        return None, None

    def _get_default_instruments(self) -> Dict[str, str]:
        """Get default instruments to track."""
        fallback_symbol = (config.instrument_symbol if config else "") or resolve_instrument_symbol()
        if not fallback_symbol:
            raise RuntimeError("No instrument configured. Set INSTRUMENT_SYMBOL or INSTRUMENT_KEY.")

        # Optional hard override for emergency runs (bypasses instruments API).
        override_token = (os.getenv("KITE_INSTRUMENT_TOKEN") or "").strip()
        if override_token:
            if override_token.isdigit():
                logger.info("Using KITE_INSTRUMENT_TOKEN override for %s", fallback_symbol)
                return {override_token: fallback_symbol}
            logger.warning("Ignoring non-numeric KITE_INSTRUMENT_TOKEN override: %s", override_token)

        instruments_rows: List[Dict[str, Any]] = []
        fetched_from_api = False
        last_fetch_error: Optional[Exception] = None

        try:
            attempts = max(1, int(os.getenv("KITE_INSTRUMENTS_FETCH_ATTEMPTS", "3")))
        except Exception:
            attempts = 3
        try:
            base_delay_sec = max(0.0, float(os.getenv("KITE_INSTRUMENTS_FETCH_BASE_DELAY", "1.5")))
        except Exception:
            base_delay_sec = 1.5
        try:
            jitter_sec = max(0.0, float(os.getenv("KITE_INSTRUMENTS_FETCH_JITTER_SEC", "0.8")))
        except Exception:
            jitter_sec = 0.8

        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    "Fetching instruments for symbol: %s (attempt %s/%s)",
                    fallback_symbol,
                    attempt,
                    attempts,
                )
                rows = self.kite.instruments(exchange="NFO")
                if isinstance(rows, list):
                    instruments_rows = rows
                    fetched_from_api = True
                    logger.info("Fetched %s instruments from NFO", len(instruments_rows))
                    self._save_instruments_cache("NFO", instruments_rows)
                    break
            except Exception as e:
                last_fetch_error = e
                if attempt < attempts:
                    delay = (base_delay_sec * attempt) + random.uniform(0.0, jitter_sec)
                    logger.warning(
                        "Failed to fetch NFO instruments (attempt %s/%s): %s; retrying in %.1fs",
                        attempt,
                        attempts,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error("Error fetching instruments after %s attempts: %s", attempts, e)

        token = self._find_token_in_rows(instruments_rows, fallback_symbol)
        if token:
            logger.info("Found token %s for symbol %s", token, fallback_symbol)
            return {token: fallback_symbol}

        # Fallback 1: use recent/stale local instruments cache.
        cache_ttl = int(os.getenv("KITE_INSTRUMENTS_CACHE_TTL_SECONDS", "86400"))
        cached_rows = self._load_instruments_cache("NFO", ttl_seconds=cache_ttl)
        token = self._find_token_in_rows(cached_rows, fallback_symbol)
        if token:
            logger.warning(
                "Using cached token %s for %s after instruments API issue",
                token,
                fallback_symbol,
            )
            return {token: fallback_symbol}

        stale_rows = self._load_instruments_cache("NFO", ttl_seconds=0)
        token = self._find_token_in_rows(stale_rows, fallback_symbol)
        if token:
            logger.warning(
                "Using stale cached token %s for %s after instruments API issue",
                token,
                fallback_symbol,
            )
            return {token: fallback_symbol}

        # Fallback 2: resolve token via quote/ltp for this single symbol.
        token = self._resolve_token_via_quote(fallback_symbol)
        if token:
            logger.warning(
                "Resolved token %s for %s via quote/ltp fallback",
                token,
                fallback_symbol,
            )
            return {token: fallback_symbol}

        if fetched_from_api:
            raise RuntimeError(
                f"Instrument token not found for {fallback_symbol} in NFO instruments list. "
                "Set a valid INSTRUMENT_SYMBOL/INSTRUMENT_TRADING_SYMBOL."
            )

        if self.ws_source == "real":
            if last_fetch_error is not None:
                raise RuntimeError(
                    "Instrument token resolution failed due Kite connectivity issues while "
                    f"fetching NFO instruments: {last_fetch_error}. "
                    "Retry the run, or set KITE_INSTRUMENT_TOKEN to bypass instrument discovery."
                )
            raise RuntimeError(
                f"Instrument token not found for {fallback_symbol}. "
                "Set a valid INSTRUMENT_SYMBOL/INSTRUMENT_TRADING_SYMBOL."
            )

        logger.warning("Using synthetic token for %s (source=%s)", fallback_symbol, self.ws_source)
        return {"0": fallback_symbol}

    @staticmethod
    def _find_token_in_rows(rows: List[Dict[str, Any]], symbol: str) -> Optional[str]:
        symbol_u = str(symbol or "").upper()
        for inst in rows or []:
            try:
                if str(inst.get("tradingsymbol", "")).upper() == symbol_u:
                    token = inst.get("instrument_token")
                    if token is not None:
                        return str(token)
            except Exception:
                continue
        return None

    def _resolve_token_via_quote(self, symbol: str) -> Optional[str]:
        """Best-effort token lookup without full instruments dump."""
        nfo_symbol = f"NFO:{symbol}"
        for method_name in ("quote", "ltp"):
            try:
                fn = getattr(self.kite, method_name, None)
                if not callable(fn):
                    continue
                response = fn([nfo_symbol])
                if not isinstance(response, dict) or nfo_symbol not in response:
                    continue
                payload = response.get(nfo_symbol) or {}
                if hasattr(payload, "to_dict"):
                    payload = payload.to_dict()
                if isinstance(payload, dict):
                    token = payload.get("instrument_token")
                    if token is not None:
                        return str(token)
            except Exception as e:
                logger.debug("Token lookup via %s failed for %s: %s", method_name, nfo_symbol, e)
        return None

    def _instruments_cache_path(self, exchange: str) -> Path:
        cache_dir = Path(os.getenv("KITE_INSTRUMENTS_CACHE_DIR", ".run")).resolve()
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return cache_dir / f"kite_instruments_{str(exchange or 'unknown').upper()}.json"

    def _load_instruments_cache(self, exchange: str, ttl_seconds: int = 0) -> List[Dict[str, Any]]:
        cache_path = self._instruments_cache_path(exchange)
        try:
            if not cache_path.exists():
                return []
            if ttl_seconds > 0:
                age = time.time() - cache_path.stat().st_mtime
                if age > ttl_seconds:
                    return []
            with cache_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            rows = payload.get("rows") if isinstance(payload, dict) else None
            return rows if isinstance(rows, list) else []
        except Exception as e:
            logger.debug("Failed to load instruments cache %s: %s", cache_path, e)
            return []

    def _save_instruments_cache(self, exchange: str, rows: List[Dict[str, Any]]) -> None:
        cache_path = self._instruments_cache_path(exchange)
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "count": len(rows or []),
            "rows": rows or [],
        }
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            tmp_path.replace(cache_path)
        except Exception as e:
            logger.debug("Failed to save instruments cache %s: %s", cache_path, e)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    def start(self):
        """Start the WebSocket tick collector."""
        if self.running:
            logger.warning("Collector already running")
            return

        logger.info("Starting WebSocket tick collector...")
        self.running = True

        # Initialize upstream ticker based on source contract
        if self.ws_source == "real":
            self.ticker = KiteTicker(self.api_key, self.access_token)
        elif self.ws_source == "mock":
            if create_mock_ticker is None:
                raise RuntimeError("Mock websocket source not available")
            tick_interval = float(os.getenv("MOCK_TICK_INTERVAL", "1.0"))
            self.ticker = create_mock_ticker(
                tick_interval=tick_interval,
            )
        elif self.ws_source == "historical":
            if create_historical_ticker is None:
                raise RuntimeError("Historical websocket source not available")
            tick_interval = float(os.getenv("HISTORICAL_WS_TICK_INTERVAL", "0.25"))
            historical_source = os.getenv("HISTORICAL_WS_SOURCE", "synthetic")
            self.ticker = create_historical_ticker(
                api_key=self.api_key,
                access_token=self.access_token,
                data_source=historical_source,
                tick_interval=tick_interval,
            )
        else:
            raise RuntimeError(f"Unsupported KITE_WS_SOURCE: {self.ws_source}")

        # Set up callbacks
        self.ticker.on_ticks = self._on_ticks
        self.ticker.on_connect = self._on_connect
        self.ticker.on_close = self._on_close
        self.ticker.on_error = self._on_error

        # Start WebSocket connection (blocking)
        try:
            self.ticker.connect(threaded=True)
            logger.info(f"WebSocket tick collector started using source={self.ws_source}")
        except Exception as e:
            logger.error(f"Failed to start WebSocket collector: {e}")
            self.running = False

    def stop(self):
        """Stop the WebSocket tick collector."""
        logger.info("Stopping WebSocket tick collector...")
        self.running = False

        if self.ticker:
            try:
                self.ticker.close()
            except Exception as e:
                logger.error(f"Error closing ticker: {e}")

        self.connected = False
        logger.info("WebSocket tick collector stopped")

    def _on_connect(self, ws, response):
        """Handle WebSocket connection."""
        logger.info(f"WebSocket connected: {response}")
        self.connected = True

        # Subscribe to instruments
        try:
            self.ticker.subscribe(self.instrument_tokens)
            if hasattr(self.ticker, "set_mode") and hasattr(self.ticker, "MODE_FULL"):
                self.ticker.set_mode(self.ticker.MODE_FULL, self.instrument_tokens)
            logger.info(f"Subscribed to {len(self.instrument_tokens)} instruments: {list(self.instruments.values())}")
        except Exception as e:
            logger.error(f"Error subscribing to instruments: {e}")

    def _on_close(self, ws, code, reason):
        """Handle WebSocket disconnection."""
        logger.warning(f"WebSocket closed: {code} - {reason}")
        self.connected = False

    def _on_error(self, ws, code, reason):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {code} - {reason}")

    def _on_ticks(self, ws, ticks):
        """Handle incoming tick data."""
        for tick in ticks:
            try:
                self._process_tick(tick)
            except Exception as e:
                logger.error(f"Error processing tick: {e}", exc_info=True)

    def _process_tick(self, tick: Dict[str, Any]):
        """Process a single tick and publish to Redis."""
        instrument_token = str(tick.get("instrument_token"))
        symbol = self.token_to_symbol.get(instrument_token, f"UNKNOWN_{instrument_token}")

        def _as_optional_int(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        # Extract tick data
        last_price = tick.get("last_price") or tick.get("last")
        # Kite tick payloads expose cumulative traded volume as `volume_traded`.
        current_cumulative_volume = (
            tick.get("volume_traded")
            if tick.get("volume_traded") is not None
            else tick.get("cumulative_volume")
            if tick.get("cumulative_volume") is not None
            else tick.get("volume", 0)
        )
        try:
            current_cumulative_volume = int(current_cumulative_volume or 0)
        except (TypeError, ValueError):
            current_cumulative_volume = 0

        last_qty = _as_optional_int(tick.get("last_quantity"))
        if last_qty is None:
            last_qty = _as_optional_int(tick.get("last_traded_quantity")) or 0

        total_buy_qty = _as_optional_int(tick.get("total_buy_quantity"))
        if total_buy_qty is None:
            total_buy_qty = _as_optional_int(tick.get("buy_quantity")) or 0

        total_sell_qty = _as_optional_int(tick.get("total_sell_quantity"))
        if total_sell_qty is None:
            total_sell_qty = _as_optional_int(tick.get("sell_quantity")) or 0

        open_interest = _as_optional_int(tick.get("oi"))
        oi_day_high = _as_optional_int(tick.get("oi_day_high"))
        oi_day_low = _as_optional_int(tick.get("oi_day_low"))
        kite_timestamp = tick.get("timestamp") or tick.get("exchange_timestamp")

        if not last_price:
            logger.warning(f"Incomplete tick data for {symbol}: {tick}")
            return

        # Use Kite timestamp as market timestamp for live data.
        kite_datetime = normalize_timestamp(kite_timestamp, IST) if kite_timestamp else datetime.now(IST)
        market_timestamp = kite_datetime

        # Calculate candle volume by differencing cumulative volume.
        # On first tick after startup, seed baseline and avoid a synthetic spike.
        previous_volume = self.last_cumulative_volume.get(instrument_token)
        if previous_volume is None:
            candle_volume = 0
        else:
            candle_volume = max(0, current_cumulative_volume - int(previous_volume or 0))
        self.last_cumulative_volume[instrument_token] = current_cumulative_volume

        # Create tick payload
        tick_data = {
            "instrument": symbol,
            "instrument_token": instrument_token,
            "last_price": float(last_price),
            "cumulative_volume": current_cumulative_volume,
            "volume_traded": current_cumulative_volume,
            "candle_volume": candle_volume,
            "last_quantity": last_qty,
            "last_traded_quantity": last_qty,
            "buy_quantity": total_buy_qty,
            "sell_quantity": total_sell_qty,
            "total_buy_quantity": total_buy_qty,
            "total_sell_quantity": total_sell_qty,
            "oi": open_interest,
            "oi_day_high": oi_day_high,
            "oi_day_low": oi_day_low,
            "timestamp": market_timestamp.isoformat(),
            **create_canonical_timestamp_payload(
                market_timestamp=market_timestamp,
                original_timestamp=kite_timestamp if kite_timestamp else None,
            ),
        }

        # Store tick in Redis store for automatic OHLC building + canonical X stream publish
        published_via_store = False
        if self.store and MarketTick:
            market_tick = MarketTick(
                instrument=symbol,
                timestamp=market_timestamp,
                last_price=float(last_price),
                volume=candle_volume,
                open_interest=open_interest or tick.get("open_interest"),
                oi_day_high=oi_day_high,
                oi_day_low=oi_day_low,
                original_timestamp=kite_datetime if kite_timestamp else None,
            )
            self.store.store_tick(market_tick)
            published_via_store = True
            logger.debug(f"Stored tick in Redis store: {symbol} @ {last_price}")

        # Publish to Redis pub/sub channels only when store path is not active.
        if not published_via_store:
            self._publish_tick(tick_data)

        logger.info(
            f"Processed tick: {symbol} @ INR {last_price:.2f}, "
            f"vol_delta: {candle_volume:,}, vol_total: {current_cumulative_volume:,}, "
            f"last_qty: {last_qty:,}, bid_qty: {total_buy_qty:,}, ask_qty: {total_sell_qty:,}"
        )

    def _publish_tick(self, tick_data: Dict[str, Any]):
        """Publish tick data to Redis pub/sub channels."""
        try:
            symbol = tick_data["instrument"]

            # Publish to type-specific channel (e.g., market:tick:BANKNIFTY:FUT)
            type_specific_channel = get_instrument_channel(symbol, "tick")
            envelope = create_event_envelope(
                stream="X",
                payload=tick_data,
                instrument=symbol,
                timeframe="1min",
                event_time=tick_data.get("market_timestamp") or tick_data.get("timestamp"),
            )
            self.redis_client.publish(type_specific_channel, json.dumps(envelope))

            # Store latest tick in Redis (for LTP collector to consume)
            self.redis_client.setex(
                f"websocket:tick:{symbol}:latest",
                300,  # 5 minute expiry
                json.dumps(tick_data)
            )

            # Optional: Publish to EventEngine if available
            if self.event_engine and EVENT_ENGINE_AVAILABLE:
                try:
                    # Create EnhancedMarketTick for event-driven strategies
                    enhanced_tick = EnhancedMarketTick(
                        instrument=symbol,
                        last_price=tick_data["last_price"],
                        volume=tick_data["candle_volume"],
                        cumulative_volume=tick_data["cumulative_volume"],
                        timestamp=datetime.fromisoformat(tick_data["timestamp"])
                    )
                    event = Event(EVENT_TICK, enhanced_tick)
                    self.event_engine.put(event)
                except Exception as e:
                    logger.debug(f"Error publishing to EventEngine: {e}")

            logger.info(f"Published tick envelope for {symbol} to channel: {type_specific_channel}")

        except Exception as e:
            logger.error(f"Error publishing tick: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get collector status."""
        return {
            "running": self.running,
            "connected": self.connected,
            "instruments": list(self.instruments.values()),
            "last_volumes": self.last_cumulative_volume.copy()
        }


def main():
    """Main entry point for standalone execution."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        collector = WebSocketTickCollector()
        collector.start()

        # Keep running until interrupted
        try:
            while collector.running:
                time.sleep(1)
                # Log status periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    status = collector.get_status()
                    logger.info(f"Collector status: connected={status['connected']}, instruments={len(status['instruments'])}")
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            collector.stop()

    except Exception as e:
        logger.error(f"Collector failed: {e}", exc_info=True)
        sys.exit(1)


# Re-export canonical implementation from sources (preferred)
# DISABLED: sources/websocket.py lacks event_engine support required for event-driven architecture
# try:
#     from market_data.sources.websocket import WebSocketTickCollector as _WebSocketTickCollector
#     from market_data.sources.websocket import main as _sources_main
#
#     WebSocketTickCollector = _WebSocketTickCollector
#     main = _sources_main
# except Exception:
#     pass


if __name__ == "__main__":
    main()
