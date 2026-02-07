#!/usr/bin/env python3
"""Load today's historical OHLC data from Zerodha to populate the chart."""
import sys
import json
import os
import redis
from datetime import datetime
from kiteconnect import KiteConnect

sys.path.insert(0, '.')
from redis_key_manager import get_redis_key

# Default to LIVE mode for loading today's data
os.environ.setdefault("EXECUTION_MODE", "live")

sys.path.insert(0, 'market_data/src')

# Load credentials
with open('credentials.json') as f:
    creds = json.load(f)

# Initialize Kite
kite = KiteConnect(api_key=creds['api_key'])
kite.set_access_token(creds['data']['access_token'])

# Fetch today's data from 9:15 AM to now
instrument_token = 260105  # BANKNIFTY26FEBFUT
from_date = datetime(2026, 2, 2, 9, 15)
to_date = datetime.now()

print(f"Fetching historical data from {from_date} to {to_date}...")
data = kite.historical_data(instrument_token, from_date, to_date, 'minute')
print(f"✓ Fetched {len(data)} bars")

# Connect to Redis
r = redis.Redis(host='localhost', port=6380, decode_responses=False)

# Store in Redis using the same format as live data
instrument = "BANKNIFTY26FEBFUT"
timeframe = "1min"
stored_count = 0

for bar in data:
    # Create OHLC bar
    ohlc_bar = {
        "timestamp": bar['date'].strftime("%Y-%m-%dT%H:%M:%S+05:30"),
        "open": float(bar['open']),
        "high": float(bar['high']),
        "low": float(bar['low']),
        "close": float(bar['close']),
        "volume": int(bar['volume']),
        "instrument": instrument,
        "timeframe": timeframe,
        "_stored_at": datetime.utcnow().isoformat() + "+00:00",
        "_stored_by": "load_today_historical",
        "_format_version": "2.0"
    }
    
    # Store in sorted set (score = timestamp)
    score = bar['date'].timestamp()
    redis_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}")
    r.zadd(redis_key, {json.dumps(ohlc_bar): score})
    stored_count += 1

print(f"✓ Stored {stored_count} bars in Redis")

# Verify
redis_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}")
total_bars = r.zcard(redis_key)
print(f"✓ Total bars in Redis: {total_bars}")
print(f"✓ Redis key: {redis_key}")
print(f"\nChart should now have enough data for indicators!")
print(f"RSI needs 14 bars, MACD needs 26 bars - you have {total_bars} bars")
