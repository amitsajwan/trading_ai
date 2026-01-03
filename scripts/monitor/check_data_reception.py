"""Check if data is being received."""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.market_memory import MarketMemory

mm = MarketMemory()
print("Checking for data reception...")
print("=" * 60)

for i in range(10):
    price = mm.get_current_price("BANKNIFTY")
    ohlc = mm.get_recent_ohlc("BANKNIFTY", "1min", 1)
    
    print(f"[{i+1}/10] Price: {price}, OHLC records: {len(ohlc)}")
    
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

