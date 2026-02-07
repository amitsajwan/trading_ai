#!/usr/bin/env python3
"""Load REAL 28 Jan 2026 historical data from Zerodha API using Docker's valid token"""

import os
import sys
import json
import redis
from datetime import datetime
from kiteconnect import KiteConnect

# Get fresh token from kite-auth-service
import subprocess

print("\n" + "="*70)
print("🔑 GETTING VALID TOKEN FROM KITE AUTH SERVICE")
print("="*70)

# Get auth status from Redis (kite-auth-service publishes it there)
r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)

try:
    auth_status = r.get("auth:status:latest")
    if auth_status:
        auth_data = json.loads(auth_status)
        print(f"\n✅ Auth Status from Docker:")
        print(f"   Status: {auth_data.get('authenticated')}")
        print(f"   User: {auth_data.get('user_id')}")
except Exception as e:
    print(f"⚠️  Could not get auth from Redis: {e}")

# Try to load credentials from Docker inspect (kite-auth-service might have injected it)
try:
    result = subprocess.run(
        ["docker", "exec", "zerodha-kite-auth-service", "python", "-c", 
         "import json; data = json.load(open('/app/credentials.json')); print(data.get('access_token'))"],
        capture_output=True, text=True, timeout=5
    )
    
    if result.returncode == 0 and result.stdout.strip():
        token_from_docker = result.stdout.strip()
        print(f"\n✅ Got access token from Docker kite-auth-service")
        
        # Load credentials and update token
        with open('credentials.json') as f:
            creds = json.load(f)
        
        creds['access_token'] = token_from_docker
        print(f"   Token: {token_from_docker[:20]}...{token_from_docker[-10:]}")
    else:
        print(f"\n⚠️  Could not get token from Docker: {result.stderr[:100]}")
        # Fall back to credentials.json
        with open('credentials.json') as f:
            creds = json.load(f)
except Exception as e:
    print(f"\n⚠️  Error getting Docker token: {e}")
    with open('credentials.json') as f:
        creds = json.load(f)

print("\n" + "="*70)
print("📥 LOADING REAL 28 JAN 2026 HISTORICAL DATA")
print("="*70)

def load_historical_data():
    """Load 28 Jan 2026 historical data from Zerodha API"""
    
    # Initialize Kite
    kite = KiteConnect(api_key=creds.get('api_key'))
    kite.set_access_token(creds.get('access_token'))
    
    # Initialize Redis
    r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)
    
    # BankNifty 26 Feb 2026 Futures
    instrument_token = 211456000  # BANKNIFTY26FEBFUT
    instrument_name = "BANKNIFTY26FEBFUT"
    
    try:
        print(f"\n📊 Loading historical data for {instrument_name}...")
        print(f"   Date: 28 Jan 2026")
        print(f"   Interval: 1-minute candles")
        
        # Fetch from Zerodha API
        from_date = datetime(2026, 1, 28, 0, 0, 0)
        to_date = datetime(2026, 1, 28, 23, 59, 59)
        
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval="minute",
            continuous=False,
            oi=False
        )
        
        print(f"   ✅ Fetched {len(data)} candles from Zerodha API")
        
        if len(data) == 0:
            print(f"   ⚠️  No data returned for this date")
            return False
        
        # Show first and last candles
        first_candle = data[0]
        last_candle = data[-1]
        
        print(f"\n   First candle (market open):")
        print(f"      Date: {first_candle.get('date')}")
        print(f"      Open: ₹{first_candle['open']}")
        print(f"      Close: ₹{first_candle['close']}")
        
        print(f"\n   Last candle (market close):")
        print(f"      Date: {last_candle.get('date')}")
        print(f"      Open: ₹{last_candle['open']}")
        print(f"      Close: ₹{last_candle['close']}")
        
        # Calculate day's movement
        opening = float(first_candle['open'])
        closing = float(last_candle['close'])
        movement = closing - opening
        movement_pct = (movement / opening) * 100
        
        print(f"\n   📈 Day's movement:")
        print(f"      {opening:.2f} → {closing:.2f}")
        print(f"      {movement:+.2f} points ({movement_pct:+.2f}%)")
        
        # Store in Redis sorted set (by timestamp)
        ohlc_key = f"ohlc_sorted:{instrument_name}:1min"
        
        # Clear existing data
        r.delete(ohlc_key)
        
        for candle in data:
            # Parse timestamp
            if isinstance(candle['date'], str):
                ts = datetime.fromisoformat(candle['date'].replace('Z', '+00:00'))
            else:
                ts = candle['date']
            
            # Create OHLC object
            ohlc = {
                "instrument": instrument_name,
                "timeframe": "1min",
                "open": candle['open'],
                "high": candle['high'],
                "low": candle['low'],
                "close": candle['close'],
                "volume": candle['volume'],
                "start_at": ts.isoformat(),
                "timestamp": ts.isoformat()
            }
            
            # Store with timestamp as score for sorted retrieval
            score = ts.timestamp()
            r.zadd(ohlc_key, {json.dumps(ohlc): score})
        
        # Also store latest as current
        r.set(f"ohlc:latest:{instrument_name}:1min", json.dumps(ohlc))
        
        print(f"\n   ✅ Stored {len(data)} candles in Redis")
        print(f"      Key: {ohlc_key}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔒 USING REAL ZERODHA API CREDENTIALS")
    print("="*70)
    success = load_historical_data()
    print("\n" + "="*70)
    if success:
        print("✅ Real historical data loaded successfully!")
        print("\nNow the dashboard will show REAL 28 Jan 2026 data (~60k)")
        print("Refresh: http://localhost:8008")
    else:
        print("❌ Failed to load historical data")
        sys.exit(1)
