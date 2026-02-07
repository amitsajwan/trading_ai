#!/usr/bin/env python3
"""Synthetic tick publisher for real-time UI updates when live data is not available."""

import redis
import json
import time
import random
from datetime import datetime

def main():
    """Run synthetic tick publisher."""
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    # Start with realistic BANKNIFTY price
    base_price = 59450.0
    current_price = base_price
    volume = 270

    print("Synthetic tick publisher started for BANKNIFTY...")

    try:
        while True:
            # Add small random price movement (-5 to +5 points)
            price_change = random.uniform(-5, 5)
            current_price += price_change
            current_price = round(current_price, 2)

            # Add small volume change
            volume_change = random.randint(-50, 50)
            volume = max(100, volume + volume_change)

            # Create tick data
            tick_data = {
                "instrument": "BANKNIFTY",
                "last_price": current_price,
                "price": current_price,
                "volume": volume,
                "timestamp": datetime.now().isoformat(),
                "oi": 15678000 + random.randint(-1000, 1000)  # Realistic OI
            }

            # Publish to Redis pub/sub (type-specific channel only)
            try:
                # Use type-specific channel (default to INDEX for synthetic data)
                type_specific_channel = "market:tick:BANKNIFTY:INDEX"
                redis_client.publish(type_specific_channel, json.dumps(tick_data))
                print(f"Published tick: Rs.{current_price:.2f} (Vol: {volume}) to {type_specific_channel}")
            except Exception as e:
                print(f"❌ Publish error: {e}")

            # Publish every 2-5 seconds for realistic updates
            time.sleep(random.uniform(2, 5))

    except KeyboardInterrupt:
        print("Synthetic tick publisher stopped")
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()