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
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set, TYPE_CHECKING
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

from market_data.timestamp_utils import get_instrument_channel, create_canonical_timestamp_payload, normalize_timestamp, IST

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

        logger.info(f"WebSocketTickCollector initialized for {len(self.instruments)} instruments")

    def _load_credentials(self) -> tuple[str, str]:
        """Load Kite credentials from environment or file."""
        # Try environment variables first
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')

        if api_key and access_token:
            return api_key, access_token

        # Fall back to credentials.json
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
            # Need to get instrument token for the symbol
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
        
        # Fallback to hardcoded (current valid BankNifty futures token)
        logger.warning("Using fallback BankNifty futures token for live data")
        return {"15148802": "BANKNIFTY26FEBFUT"}  # Current valid token for Feb expiry

    def start(self):
        """Start the WebSocket tick collector."""
        if self.running:
            logger.warning("Collector already running")
            return

        logger.info("Starting WebSocket tick collector...")
        self.running = True

        # Initialize KiteTicker
        self.ticker = KiteTicker(self.api_key, self.access_token)

        # Set up callbacks
        self.ticker.on_ticks = self._on_ticks
        self.ticker.on_connect = self._on_connect
        self.ticker.on_close = self._on_close
        self.ticker.on_error = self._on_error

        # Start WebSocket connection (blocking)
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

        # Subscribe to instruments
        try:
            self.ticker.subscribe(self.instrument_tokens)
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

        # Extract tick data
        last_price = tick.get("last_price") or tick.get("last")
        current_cumulative_volume = tick.get("volume", 0)
        kite_timestamp = tick.get("timestamp") or tick.get("exchange_timestamp")

        if not last_price:
            logger.warning(f"Incomplete tick data for {symbol}: {tick}")
            return

        # Use Kite timestamp as market timestamp for live data
        # This ensures market_timestamp reflects when the trade actually occurred
        kite_datetime = normalize_timestamp(kite_timestamp, IST) if kite_timestamp else datetime.now(IST)
        market_timestamp = kite_datetime

        # Calculate candle volume by differencing cumulative volume
        previous_volume = self.last_cumulative_volume.get(instrument_token, 0)
        candle_volume = max(0, current_cumulative_volume - previous_volume)
        self.last_cumulative_volume[instrument_token] = current_cumulative_volume

        # Create tick payload
        tick_data = {
            "instrument": symbol,
            "instrument_token": instrument_token,
            "last_price": float(last_price),
            "cumulative_volume": current_cumulative_volume,
            "candle_volume": candle_volume,
            "timestamp": market_timestamp.isoformat(),
            **create_canonical_timestamp_payload(
                market_timestamp=market_timestamp,
                original_timestamp=kite_timestamp if kite_timestamp else None
            )
        }

        # Publish to Redis pub/sub channels
        self._publish_tick(tick_data)

        logger.info(f"Processed tick: {symbol} @ ₹{last_price:.2f}, vol: {candle_volume:,}")

    def _publish_tick(self, tick_data: Dict[str, Any]):
        """Publish tick data to Redis pub/sub channels."""
        try:
            symbol = tick_data["instrument"]

            # Determine instrument type for channel naming
            from market_data.timestamp_utils import detect_instrument_type
            instrument_type = detect_instrument_type(symbol)

            # Publish to type-specific channel (e.g., market:tick:BANKNIFTY:FUT)
            type_specific_channel = get_instrument_channel(symbol, "tick")
            self.redis_client.publish(type_specific_channel, json.dumps(tick_data))

            # Also publish to generic tick channel for backward compatibility
            generic_channel = f"tick:{symbol}"
            self.redis_client.publish(generic_channel, json.dumps(tick_data))

            # Also publish to raw_ticks channel for LTP collector
            raw_channel = f"raw_ticks:{symbol}"
            self.redis_client.publish(raw_channel, json.dumps(tick_data))
            print(f"DEBUG: Published to {raw_channel}")

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