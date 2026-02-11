#!/usr/bin/env python3
"""Inject sample historical OHLC data into Redis with proper mode prefixes."""
import redis
import json
from datetime import datetime, timedelta
import random

def main():
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6380, decode_responses=True)
    print("✓ Connected to Redis")
    
    # Generate sample OHLC data
    instrument = "BANKNIFTY26FEBFUT"
    timeframes = ["1min", "5min", "15min", "1h"]
    base_price = 53000.0
    
    # Generate last 100 bars for each timeframe
    now = datetime.now()
    
    for tf in timeframes:
        print(f"\n📊 Generating {tf} data...")
        key = f"historical:ohlc_sorted:{instrument}:{tf}"
        
        # Clear existing data
        r.delete(key)
        
        # Generate bars
        for i in range(100):
            bar_time = now - timedelta(minutes=(100-i) * (1 if tf == "1min" else 5 if tf == "5min" else 15 if tf == "15min" else 60))
            timestamp = int(bar_time.timestamp())
            
            # Random walk price
            open_price = base_price + random.uniform(-500, 500)
            high_price = open_price + random.uniform(0, 100)
            low_price = open_price - random.uniform(0, 100)
            close_price = random.uniform(low_price, high_price)
            volume = random.randint(1000, 10000)
            
            bar_data = {
                "start_at": timestamp,
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume,
                "oi": random.randint(100000, 500000)
            }
            
            # Store in sorted set (score = timestamp)
            r.zadd(key, {json.dumps(bar_data): timestamp})
        
        count = r.zcard(key)
        print(f"   ✓ Stored {count} bars in {key}")
    
    # Inject current price
    current_price_key = f"historical:price:{instrument}"
    current_price = round(base_price + random.uniform(-200, 200), 2)
    r.set(current_price_key, current_price)
    print(f"\n💰 Set current price: ₹{current_price}")
    
    # Verify
    print("\n=== VERIFICATION ===")
    pattern = "historical:*"
    keys = list(r.scan_iter(pattern, count=100))
    print(f"✓ Found {len(keys)} historical keys:")
    for key in keys[:10]:
        if "ohlc_sorted" in key:
            count = r.zcard(key)
            print(f"  • {key}: {count} bars")
        else:
            val = r.get(key)
            print(f"  • {key}: {val}")
    
    print("\n✅ Historical data injected successfully!")
    print(f"🌐 View dashboard at: http://localhost:8000")

if __name__ == "__main__":
    main()
