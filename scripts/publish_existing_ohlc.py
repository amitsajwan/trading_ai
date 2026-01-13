#!/usr/bin/env python3
"""Publish existing OHLC data to Redis pub/sub channels for real-time updates."""

import redis
import json
import os
import sys
from datetime import datetime

# Add market_data to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'market_data', 'src'))

from market_data.adapters.redis_store import RedisMarketStore
from market_data.api import build_store

def publish_existing_ohlc():
    """Publish existing OHLC data to Redis pub/sub channels."""

    # Initialize Redis store
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    store = build_store(redis_client=redis_client)

    # Get existing OHLC data for BANKNIFTY 1min
    bars = list(store.get_ohlc("BANKNIFTY", "1min", limit=50))

    print(f"Found {len(bars)} existing OHLC bars for BANKNIFTY 1min")

    # Publish each bar to Redis pub/sub
    for bar in bars[-20:]:  # Publish last 20 bars
        try:
            payload = {
                "instrument": bar.instrument,
                "timeframe": bar.timeframe,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "start_at": bar.start_at.isoformat(),
            }
            payload_json = json.dumps(payload)

            # Publish to channels
            redis_client.publish(f"market:ohlc:{bar.instrument}:{bar.timeframe}", payload_json)
            redis_client.publish("market:ohlc", payload_json)
            redis_client.publish(f"market:ohlc:{bar.instrument}", payload_json)

            print(f"Published OHLC bar for {bar.instrument} {bar.timeframe} at {bar.start_at}")

        except Exception as e:
            print(f"Error publishing OHLC bar: {e}")

    print("Finished publishing existing OHLC data")

if __name__ == "__main__":
    publish_existing_ohlc()