#!/usr/bin/env python3
import redis
import json

def check_market_data():
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)

    # Check system mode
    mode = r.get('system:execution_mode')
    print(f"System mode: {mode}")

    # Check tick data
    tick_keys = r.keys('market:tick:*')
    print(f"Tick keys found: {len(tick_keys)}")
    if tick_keys:
        print("Sample tick keys:", tick_keys[:3])
        sample_key = tick_keys[0]
        data = r.get(sample_key)
        if data:
            try:
                parsed = json.loads(data)
                print(f"Sample tick data for {sample_key}:")
                print(f"  Last price: {parsed.get('last_price')}")
                print(f"  Timestamp: {parsed.get('timestamp')}")
                print(f"  Volume: {parsed.get('volume')}")
            except:
                print(f"Raw data: {data[:200]}...")

    # Check if historical data is being used
    hist_running = r.get('system:historical:running')
    print(f"Historical mode running: {hist_running}")

if __name__ == "__main__":
    check_market_data()