#!/usr/bin/env python3
"""Load real Zerodha historical data for 28 Jan 2026 into Redis"""

import os
import sys
import json
import redis
from datetime import datetime, date, timedelta
from kiteconnect import KiteConnect

# Add market_data to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'market_data', 'src'))

# from market_data.contracts import MarketTick, Candle

def load_historical_data():
    """Load 28 Jan 2026 historical data from Zerodha API"""
    
    # Load credentials
    try:
        with open('credentials.json') as f:
            creds = json.load(f)
    except:
        print("❌ credentials.json not found")
        return False
    
    # Initialize Kite
    kite = KiteConnect(api_key=creds.get('api_key'))
    kite.set_access_token(creds.get('access_token'))
    
    # Initialize Redis
    r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)
    
    # BankNifty 26 Feb 2026 Futures
    instrument_token = 211456000  # BANKNIFTY26FEBFUT
    instrument_name = "BANKNIFTY26FEBFUT"
    
    try:
        print(f"📊 Loading historical data for {instrument_name}...")
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
            continuous=False,  # Don't use continuous contracts
            oi=False
        )
        
        print(f"   ✅ Fetched {len(data)} candles from Zerodha API")
        
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
        
        print(f"   ✅ Stored {len(data)} candles in Redis")
        print(f"      Key: {ohlc_key}")
        print(f"   ✅ Latest candle:")
        print(f"      {json.dumps(ohlc, indent=2)}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*70)
    print("📥 LOADING HISTORICAL DATA FROM ZERODHA API")
    print("="*70)
    success = load_historical_data()
    print("="*70)
    if success:
        print("✅ Historical data loaded successfully!")
        print("\nNow the dashboard should show real 28 Jan 2026 data")
        print("Refresh: http://localhost:8008")
    else:
        print("❌ Failed to load historical data")
        sys.exit(1)
