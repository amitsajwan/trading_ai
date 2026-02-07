#!/usr/bin/env python3
"""Synthetic indicators publisher for real-time UI updates."""

import redis
import json
import time
import random
from datetime import datetime

def main():
    """Run synthetic indicators publisher."""
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    print("Synthetic indicators publisher started for BANKNIFTY...")

    try:
        while True:
            # Create synthetic indicator data
            indicators_data = {
                "instrument": "BANKNIFTY",
                "timeframe": "1min",
                "timestamp": datetime.now().isoformat(),
                "atr_14": round(random.uniform(50, 200), 2),
                "atr_20": round(random.uniform(60, 220), 2),
                "rsi_14": round(random.uniform(30, 70), 2),
                "macd_value": round(random.uniform(-50, 50), 2),
                "adx_14": round(random.uniform(15, 35), 2),
                "mode": "LIVE",
                "run_id": "synthetic"
            }

            # Publish to indicators channel
            try:
                channel = "indicators:BANKNIFTY:INDEX"
                redis_client.publish(channel, json.dumps(indicators_data))
                print(f"Published indicators to {channel}: RSI={indicators_data['rsi_14']}, ATR={indicators_data['atr_14']}")
            except Exception as e:
                print(f"❌ Indicators publish error: {e}")

            # Publish every 5-10 seconds
            time.sleep(random.uniform(5, 10))

    except KeyboardInterrupt:
        print("Synthetic indicators publisher stopped")
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()