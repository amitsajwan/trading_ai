"""WebSocket tick source - Real-time tick collection using KiteTicker.

This source:
1. Uses KiteTicker WebSocket to get real-time market ticks
2. Publishes raw ticks to Redis pub/sub channels (Kite schema preserved)
3. Adds canonical timestamps for downstream processing
4. Supports multiple instruments simultaneously

Architecture: WebSocket → Redis Pub/Sub → LTP Processor → Enhanced Data
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

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

from market_data.timestamp_utils import get_instrument_channel, create_canonical_timestamp_payload, normalize_timestamp, IST

try:
    from redis_key_manager import get_redis_key
except Exception:
    def get_redis_key(key: str, *args, **kwargs):
        return key

# Import config
try:
    from config import get_config
    config = get_config()
    print(f"DEBUG: Config loaded: {config.instrument_symbol if config else 'None'}")
except Exception as e:
    print(f"DEBUG: Config import failed: {e}")
    config = None

logger = logging.getLogger(__name__)


def _coerce_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _serialize_tick_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_tick_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_tick_value(v) for v in value]
    return value


def _serialize_tick(tick: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _serialize_tick_value(v) for k, v in tick.items()}


class WebSocketTickCollector:
    """Real-time tick collector using Zerodha KiteTicker WebSocket."""

    def __init__(self, instruments: Optional[Dict[str, str]] = None):
        """Initialize WebSocket tick collector.

        Args:
            instruments: Dict mapping trading symbols to instrument tokens
        """
        if not KITE_AVAILABLE:
            raise RuntimeError("kiteconnect library not available")

        if not REDIS_AVAILABLE:
            raise RuntimeError("redis library not available")

        # Load credentials
        self.api_key, self.access_token = self._load_credentials()
        if not self.api_key or not self.access_token:
            raise RuntimeError("Kite credentials not available")

        # Initialize Kite client
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)

        # Initialize Redis
        redis_config = {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": 0,
            "decode_responses": True
        }
        self.redis_client = redis.Redis(**redis_config)

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
        self.ws_mode: Optional[str] = None

        logger.info(f"WebSocketTickCollector initialized for {len(self.instruments)} instruments")

    def _load_credentials(self) -> tuple[str, str]:
        """Load Kite credentials from environment or file."""
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')

        if api_key and access_token:
            return api_key, access_token

        cred_path = os.path.join(os.getcwd(), "credentials.json")
        if os.path.exists(cred_path):
            try:
                with open(cred_path, "r", encoding="utf-8") as f:
                    creds = json.load(f)
                return creds.get("api_key"), creds.get("access_token")
            except Exception as e:
                logger.error(f"Error loading credentials: {e}")

        return None, None

    def _get_default_instruments(self) -> Dict[str, str]:
        """Get default instruments to track."""
        if config:
            symbol = config.instrument_symbol
            try:
                logger.info(f"Fetching instruments for symbol: {symbol}")
                instruments = self.kite.instruments(exchange="NFO")
                logger.info(f"Fetched {len(instruments)} instruments from NFO")
                for inst in instruments:
                    if inst['tradingsymbol'] == symbol:
                        token = str(inst['instrument_token'])
                        logger.info(f"Found token {token} for symbol {symbol}")
                        return {token: symbol}
                logger.error(f"Instrument {symbol} not found in NFO exchange")
            except Exception as e:
                logger.error(f"Error fetching instruments: {e}")

        logger.warning("Using fallback BankNifty futures token for live data")
        return {"15148802": "BANKNIFTY26FEBFUT"}

    def start(self):
        """Start the WebSocket tick collector."""
        if self.running:
            logger.warning("Collector already running")
            return

        logger.info("Starting WebSocket tick collector...")
        self.running = True

        self.ticker = KiteTicker(self.api_key, self.access_token)

        self.ticker.on_ticks = self._on_ticks
        self.ticker.on_connect = self._on_connect
        self.ticker.on_close = self._on_close
        self.ticker.on_error = self._on_error

        try:
            self.ticker.connect(threaded=True)
            logger.info("WebSocket tick collector started")
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

        try:
            self.ticker.subscribe(self.instrument_tokens)
            self._apply_ws_mode()
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

    def _apply_ws_mode(self) -> None:
        if not self.ticker:
            return

        mode_name = os.getenv("KITE_TICKER_MODE", "full").strip().lower()
        mode_map = {
            "ltp": self.ticker.MODE_LTP,
            "quote": self.ticker.MODE_QUOTE,
            "full": self.ticker.MODE_FULL,
        }

        if mode_name not in mode_map:
            logger.warning(f"Unknown KITE_TICKER_MODE '{mode_name}', defaulting to 'full'")
            mode_name = "full"

        self.ticker.set_mode(mode_map[mode_name], self.instrument_tokens)
        self.ws_mode = mode_name
        logger.info(f"WebSocket mode set to: {mode_name}")

    def _process_tick(self, tick: Dict[str, Any]):
        """Process a single tick and publish to Redis."""
        instrument_token = tick.get("instrument_token")
        instrument_token_key = str(instrument_token) if instrument_token is not None else "UNKNOWN"
        symbol = self.token_to_symbol.get(instrument_token_key, f"UNKNOWN_{instrument_token_key}")

        last_price = tick.get("last_price") or tick.get("last")
        current_cumulative_volume = tick.get("volume")
        kite_timestamp_raw = tick.get("timestamp") or tick.get("exchange_timestamp") or tick.get("last_trade_time")
        kite_timestamp = _coerce_timestamp(kite_timestamp_raw)

        if last_price is None:
            logger.warning(f"Incomplete tick data for {symbol}: {tick}")
            return

        kite_datetime = normalize_timestamp(kite_timestamp, IST) if kite_timestamp else datetime.now(IST)
        market_timestamp = kite_datetime

        if current_cumulative_volume is not None:
            self.last_cumulative_volume[instrument_token_key] = int(current_cumulative_volume)

        raw_tick = _serialize_tick(tick)
        tick_data = {
            **raw_tick,
            "instrument": symbol,
        }

        if "timestamp" not in tick_data:
            tick_data["timestamp"] = market_timestamp.isoformat()

        if "volume" in tick_data and "cumulative_volume" not in tick_data:
            tick_data["cumulative_volume"] = tick_data["volume"]

        tick_data.update(
            create_canonical_timestamp_payload(
                market_timestamp=market_timestamp,
                original_timestamp=kite_timestamp if kite_timestamp else None
            )
        )

        self._publish_tick(tick_data)

        volume_log = current_cumulative_volume if current_cumulative_volume is not None else "n/a"
        logger.info(f"Processed tick: {symbol} @ ₹{float(last_price):.2f}, vol: {volume_log}")

    def _publish_tick(self, tick_data: Dict[str, Any]):
        """Publish tick data to Redis pub/sub channels."""
        try:
            symbol = tick_data["instrument"]

            from market_data.timestamp_utils import detect_instrument_type
            instrument_type = detect_instrument_type(symbol)

            type_specific_channel = get_instrument_channel(symbol, "tick")
            self.redis_client.publish(type_specific_channel, json.dumps(tick_data))

            generic_channel = f"tick:{symbol}"
            self.redis_client.publish(generic_channel, json.dumps(tick_data))

            raw_channel = f"raw_ticks:{symbol}"
            self.redis_client.publish(raw_channel, json.dumps(tick_data))

            self.redis_client.setex(
                get_redis_key(f"websocket:tick:{symbol}:latest"),
                300,
                json.dumps(tick_data)
            )

            logger.info(f"Published tick for {symbol} to channels: {type_specific_channel}, {generic_channel}")

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

        try:
            while collector.running:
                time.sleep(1)
                if int(time.time()) % 60 == 0:
                    status = collector.get_status()
                    logger.info(f"Collector status: connected={status['connected']}, instruments={len(status['instruments'])}")
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            collector.stop()

    except Exception as e:
        logger.error(f"Collector failed: {e}", exc_info=True)
        sys.exit(1)


class WebSocketSource(WebSocketTickCollector):
    """Alias for the live WebSocket collector."""


def start_websocket_source(instruments: Optional[Dict[str, str]] = None) -> WebSocketSource:
    collector = WebSocketSource(instruments=instruments)
    collector.start()
    return collector


if __name__ == "__main__":
    main()
