"""Test Redis connection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.market_memory import MarketMemory

mm = MarketMemory()
print("Redis Available:", mm._redis_available)

if mm._redis_available:
    mm.redis_client.ping()
    print("Redis Ping: OK")
    mm.redis_client.set("test", "value")
    print("Redis Write: OK")
    print("Redis Read:", mm.redis_client.get("test"))
    
    # Check for existing data
    tick_keys = mm.redis_client.keys("tick:BANKNIFTY:*")
    print(f"Existing tick keys: {len(tick_keys)}")
    
    price_keys = mm.redis_client.keys("price:BANKNIFTY:*")
    print(f"Existing price keys: {len(price_keys)}")
    
    ohlc_keys = mm.redis_client.keys("ohlc:BANKNIFTY:*")
    print(f"Existing OHLC keys: {len(ohlc_keys)}")
else:
    print("Redis NOT available!")

