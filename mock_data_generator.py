#!/usr/bin/env python3
"""
Simple mock data generator for testing the trading system locally.
Generates fake market data when real Kite API is not available.
"""

import redis
import random
import time
from datetime import datetime
from config import get_config


def generate_mock_data():
    """Generate mock market data for testing."""
    config = get_config()
    r = redis.Redis(**config.get_redis_config())

    # Base price for BANKNIFTY
    base_price = 60000.0
    current_price = base_price

    print(f"Starting mock data generator for {config.instrument_symbol}")
    print(f"Redis config: {config.redis_host}:{config.redis_port}")

    while True:
        # Add some random movement
        change = random.uniform(-50, 50)
        current_price += change

        # Keep within reasonable bounds
        current_price = max(58000, min(62000, current_price))

        # Generate mock data
        timestamp = datetime.now().isoformat()
        volume = random.randint(10000, 50000)
        depth = {
            "buy": [{"price": current_price - 1, "quantity": 100}],
            "sell": [{"price": current_price + 1, "quantity": 100}]
        }

        # Store in Redis
        import json
        price_key = config.redis_price_key
        volume_key = config.redis_volume_key
        depth_key = f"depth:{config.instrument_key}"

        r.set(f"{price_key}:last_price", current_price)
        r.set(f"{price_key}:latest_ts", timestamp)
        r.set(f"{price_key}:quote", json.dumps({"last_price": current_price, "depth": depth}))
        r.set(f"{volume_key}:latest", volume)

        # Also write explicit depth keys for consumers/tests
        r.set(f"{depth_key}:buy", json.dumps(depth.get("buy", [])))
        r.set(f"{depth_key}:sell", json.dumps(depth.get("sell", [])))
        r.set(f"{depth_key}:timestamp", timestamp)
        r.set(f"{depth_key}:total_bid_qty", sum(d.get("quantity", 0) for d in depth.get("buy", [])))
        r.set(f"{depth_key}:total_ask_qty", sum(d.get("quantity", 0) for d in depth.get("sell", [])))

        print(f"[{config.instrument_symbol}] price={current_price:.2f} ts={timestamp}")

        # Wait before next update
        time.sleep(2)


if __name__ == "__main__":
    generate_mock_data()
