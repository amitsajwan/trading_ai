"""Check current price from Redis."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.market_memory import MarketMemory

mm = MarketMemory()
print("Checking price...")
print("=" * 60)

price = mm.get_current_price("BANKNIFTY")
print(f"Current Price: {price}")

ohlc = mm.get_recent_ohlc("BANKNIFTY", "1min", 1)
print(f"OHLC Records: {len(ohlc)}")

if ohlc:
    print(f"Latest OHLC Close: {ohlc[-1].get('close', 'N/A')}")

# Check Redis directly
if mm._redis_available:
    import redis
    keys = mm.redis_client.keys("price:BANKNIFTY:*")
    print(f"Price keys: {len(keys)}")
    if keys:
        latest = mm.redis_client.get("price:BANKNIFTY:latest")
        print(f"Latest price key: {latest}")
    
    tick_keys = mm.redis_client.keys("tick:BANKNIFTY:*")
    print(f"Tick keys: {len(tick_keys)}")
    if tick_keys:
        latest_tick_key = sorted(tick_keys)[-1]
        tick_data = mm.redis_client.get(latest_tick_key)
        print(f"Latest tick: {tick_data[:100] if tick_data else 'None'}")

