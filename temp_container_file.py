#!/usr/bin/env python3
"""LTP Processor - Processes WebSocket ticks from Redis and applies volume logic.

This processor:
1. Subscribes to raw WebSocket ticks from Redis pub/sub
2. Applies volume source prioritization (core instrument > direct > synthetic)
3. Publishes enhanced tick data with proper volume for technical analysis
4. Handles dual-instrument volume logic for derivatives

Architecture: WebSocket Collector  Redis Pub/Sub  LTP Processor  Enhanced Data
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
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


def get_symbol_config():
    if config:
        trading_symbol = config.instrument_trading_symbol
        symbol = config.instrument_symbol
        exchange = config.instrument_exchange
        return exchange, symbol
    return "NSE", "BANKNIFTY"


def sanitize_key(symbol: str) -> str:
    return symbol.upper().replace(" ", "")


class LTPDataProcessor:
    """"Redis subscriber that processes WebSocket ticks and applies volume logic."""

    # Core instrument mapping for derivatives
    CORE_INSTRUMENT_MAPPING = {
        'BANKNIFTY26JANFUT': 'BANKNIFTY',
        'BANKNIFTY27JANFUT': 'BANKNIFTY',
        'NIFTY26JANFUT': 'NIFTY',
        'NIFTY27JANFUT': 'NIFTY',
        # Add more mappings as needed for other derivatives
    }

    def __init__(self, market_memory: Any) -> None:
        self.market_memory = market_memory
        self.exchange, self.symbol = get_symbol_config()
        self.key = config.instrument_key if config else sanitize_key(self.symbol)
        self.price = 44000.0  # seed
        self.drift = 0.0

        # Determine core instrument for volume data
        self.core_instrument = self._get_core_instrument()
        self.volume_source = self._determine_volume_source()

        # Redis client for pub/sub
        if redis:
            redis_config = config.get_redis_config() if config else {
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "db": 0,
                "decode_responses": True
            }
            self.redis_client = redis.Redis(**redis_config)
            self.pubsub = self.redis_client.pubsub()
        else:
            self.redis_client = None
            self.pubsub = None

        # Volume tracking for differencing
        self.last_volume = {}
        self.last_timestamp = {}

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _get_core_instrument(self) -> Optional[str]:
        """Get the core instrument for volume data (e.g., BANKNIFTY for futures)."""
        trading_symbol = config.instrument_trading_symbol if config else self.symbol
        return self.CORE_INSTRUMENT_MAPPING.get(trading_symbol)

    def _determine_volume_source(self) -> str:
        """Determine volume source priority: core > direct > synthetic."""
        if self.core_instrument:
            return "core"
        return "direct"

    def _calculate_volume_diff(self, instrument_name: str, current_volume: int, timestamp: datetime) -> int:
        """Calculate volume difference from previous tick."""
        key = instrument_name
        last_vol = self.last_volume.get(key, 0)
        last_ts = self.last_timestamp.get(key)

        # Reset if timestamp indicates new candle or significant time gap
        if last_ts and (timestamp - last_ts).total_seconds() > 300:  # 5 minutes
            last_vol = 0

        volume_diff = max(0, current_volume - last_vol)

        # Update tracking
        self.last_volume[key] = current_volume
        self.last_timestamp[key] = timestamp

        return volume_diff

    def _get_enhanced_volume(self, tick_data: Dict[str, Any], instrument_name: str, timestamp: datetime) -> Tuple[int, str]:
        """Get volume with proper source prioritization."""
        current_volume = tick_data.get("volume_traded", 0)

        # For core instrument (e.g., BANKNIFTY index), use direct volume
        if instrument_name == self.core_instrument:
            return current_volume, "core"

        # For derivatives, prioritize core instrument volume if available
        if self.core_instrument and self.market_memory:
            try:
                core_data = self.market_memory.get(self.core_instrument)
                if core_data and "volume" in core_data:
                    return core_data["volume"], "core"
            except Exception:
                pass

        # Fallback to direct volume with differencing
        volume_diff = self._calculate_volume_diff(instrument_name, current_volume, timestamp)
        return volume_diff, "direct"

    def _process_tick(self, tick_data: Dict[str, Any]) -> None:
        """Process a single WebSocket tick and publish enhanced data."""
        try:
            instrument_name = tick_data.get("instrument_token", "unknown")
            timestamp = datetime.fromisoformat(tick_data.get("timestamp", datetime.now().isoformat()))

            # Get enhanced volume
            final_volume, volume_source = self._get_enhanced_volume(tick_data, instrument_name, timestamp)

            # Create enhanced data payload
            enhanced_data = {
                "instrument": instrument_name,
                "timestamp": timestamp.isoformat(),
                "last_price": tick_data.get("last_price", 0),
                "volume": final_volume,
                "volume_source": volume_source,
                "core_instrument": self.core_instrument if self.core_instrument != instrument_name else None,
                **tick_data  # Include all original tick data
            }

            # Publish to Redis for downstream consumers
            if self.redis_client:
                channel = f"enhanced_ticks:{self.key}"
                self.redis_client.publish(channel, json.dumps(enhanced_data))
                self.logger.debug(f"Published enhanced tick to {channel}: volume={final_volume} ({volume_source})")

            # Store in market memory if available
            # if self.market_memory:
                # self.market_memory.set(instrument_name, enhanced_data)

        except Exception as e:
            self.logger.error(f"Error processing tick: {e}")

    def start_processing(self) -> None:
        """Start processing WebSocket ticks from Redis pub/sub."""
        if not self.pubsub:
            self.logger.error("Redis pubsub not available")
            return

        try:
            # Subscribe to raw ticks channel
            channel = f"raw_ticks:{self.key}"
            self.pubsub.subscribe(channel)
            self.logger.info(f"Subscribed to Redis channel: {channel}")

            # Process messages
            for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        tick_data = json.loads(message["data"])
                        self._process_tick(tick_data)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse tick data: {e}")
                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}")

        except KeyboardInterrupt:
            self.logger.info("Stopping LTP processor...")
        except Exception as e:
            self.logger.error(f"Error in LTP processor: {e}")
        finally:
            if self.pubsub:
                self.pubsub.close()


def main():
    """Main entry point for LTP processor."""
    print("[ltp] Starting LTP Data Processor...")

    # Initialize market memory
    market_memory = None
    try:
        if redis:
            redis_config = config.get_redis_config() if config else {
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "db": 0,
                "decode_responses": True
            }
            redis_client = redis.Redis(**redis_config)
            # from market_data.api import build_store
            # market_memory = build_store(redis_client=redis_client)
#             print("[ltp] Initialized Redis-backed market store")
    except Exception as e:
        print(f"[ltp] Failed to initialize market store: {e}")
        market_memory = None

    processor = LTPDataProcessor(market_memory)
    processor.start_processing()


if __name__ == "__main__":
    main()
