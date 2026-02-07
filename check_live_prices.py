#!/usr/bin/env python3
"""Check what live prices the API is now returning"""

import requests
import json
import redis

print("\n" + "="*70)
print("🔍 CHECKING LIVE PRICES (LIVE MODE ACTIVE)")
print("="*70)

# Check API
print("\n1️⃣  Market Data API Response:")
try:
    response = requests.get("http://localhost:8004/api/v1/market/ohlc/BANKNIFTY26FEBFUT?timeframe=1min", timeout=5)
    data = response.json()
    
    if isinstance(data, list) and len(data) > 0:
        latest = data[-1]
        print(f"   ✅ Latest candle from API:")
        print(f"      Close: ₹{latest.get('close', 'N/A')}")
        print(f"      Date: {latest.get('date', 'N/A')}")
        print(f"      Volume: {latest.get('volume', 'N/A')}")
        
        # Check if it's current or historical
        if latest.get('date'):
            date_str = str(latest['date'])
            if '2026-01-31' in date_str:
                print(f"   ✅ DATE: 31 Jan 2026 (TODAY - LIVE DATA)")
            elif '2026-01-28' in date_str:
                print(f"   ⚠️  DATE: 28 Jan 2026 (OLD - HISTORICAL DATA)")
            else:
                print(f"   ❓ DATE: {date_str}")
    else:
        print(f"   Response: {data}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Check Redis raw ticks
print("\n2️⃣  Redis Raw Ticks Queue:")
r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)

tick_count = r.llen("raw_ticks:BANKNIFTY26FEBFUT")
print(f"   Queue length: {tick_count} ticks")

if tick_count > 0:
    last_3_ticks = r.lrange("raw_ticks:BANKNIFTY26FEBFUT", -3, -1)
    print(f"   Last 3 ticks:")
    for i, tick_json in enumerate(last_3_ticks):
        try:
            tick = json.loads(tick_json)
            ltp = tick.get('ltp')
            timestamp = tick.get('timestamp')
            print(f"      {i+1}. LTP: ₹{ltp}, Time: {timestamp}")
        except:
            print(f"      {i+1}. {tick_json[:50]}...")

# Check indicators
print("\n3️⃣  Indicators (calculated from live data):")
try:
    response = requests.get("http://localhost:8004/api/v1/technical/indicators/BANKNIFTY26FEBFUT", timeout=5)
    data = response.json()
    
    if isinstance(data, dict):
        print(f"   ✅ Indicators calculated:")
        for key, value in list(data.items())[:5]:
            if isinstance(value, (int, float)):
                print(f"      {key}: {value:.2f}")
    else:
        print(f"   Response: {data}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Check system mode
print("\n4️⃣  System Mode:")
try:
    with open('.mode_config.json') as f:
        config = json.load(f)
        print(f"   Mode: {config.get('mode')}")
        print(f"   Manual Override: {config.get('manual_override')}")
except:
    pass

print("\n" + "="*70)
print("📊 EXPECTED RESULTS FOR LIVE MODE:")
print("="*70)
print("""
✅ API close price: ~₹60,000 (TODAY'S LIVE PRICE)
✅ API date: 2026-01-31 (TODAY)
✅ Raw ticks queue: >0 (receiving live ticks)
✅ Indicators: Calculated from live data
✅ Mode: LIVE
✅ Override: live

If you see 45k and 2026-01-28, system still in historical mode.
If you see 60k and 2026-01-31, system now shows LIVE data!
""")
