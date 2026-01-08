"""Check if data is being received."""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.market_memory import MarketMemory
from config import get_config

cfg = get_config()
instrument = cfg.instrument_symbol

mm = MarketMemory()
print("Checking for data reception...")
print("=" * 60)

for i in range(10):
    price = mm.get_current_price(instrument)
    ohlc = mm.get_recent_ohlc(instrument, "1min", 1)
    
    print(f"[{i+1}/10] Price ({instrument}): {price}, OHLC records: {len(ohlc)}")
    
    if price:
        print("✅ DATA RECEIVED!")
        if ohlc:
            print(f"Latest OHLC: {ohlc[-1]}")
        break
    
    time.sleep(2)

if not price:
    print("⚠️  No data received after 20 seconds")
    print("Check if:")
    print("  1. Market is open (9:15 AM - 3:30 PM IST)")
    print("  2. WebSocket service is running")
    print("  3. Redis is accessible")


