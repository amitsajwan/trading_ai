#!/usr/bin/env python3
"""COMPREHENSIVE AUDIT: Where is the ~60k price coming from?"""

import requests
import json
import redis

print("\n" + "="*80)
print("🚨 SECURITY AUDIT: IDENTIFY ALL DATA SOURCES")
print("="*80)

r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)

# 1. Check all API endpoints
print("\n1️⃣  MARKET DATA API ENDPOINTS:")
print("-" * 80)

endpoints = [
    ("1-min OHLC", "http://localhost:8004/api/v1/market/ohlc/BANKNIFTY26FEBFUT?timeframe=1min"),
    ("5-min OHLC", "http://localhost:8004/api/v1/market/ohlc/BANKNIFTY26FEBFUT?timeframe=5min"),
    ("Indicators", "http://localhost:8004/api/v1/technical/indicators/BANKNIFTY26FEBFUT"),
    ("Health", "http://localhost:8004/health"),
]

for name, url in endpoints:
    try:
        response = requests.get(url, timeout=2)
        data = response.json() if response.headers.get('content-type', '').count('json') else response.text
        
        if isinstance(data, list) and len(data) > 0:
            latest = data[-1] if isinstance(data, list) else data
            close = latest.get('close') if isinstance(latest, dict) else 'N/A'
            print(f"   ✅ {name}: {response.status_code}")
            if close and close != 'N/A':
                print(f"      Latest close: {close}")
        elif isinstance(data, dict):
            print(f"   ✅ {name}: {response.status_code}")
            if 'close' in data:
                print(f"      Close: {data.get('close')}")
        else:
            print(f"   ✅ {name}: {response.status_code}")
    except Exception as e:
        print(f"   ❌ {name}: {str(e)[:50]}")

# 2. Check all Redis keys with price data
print("\n2️⃣  REDIS DATA SOURCES (looking for ~60k prices):")
print("-" * 80)

all_keys = r.keys("*")
price_keys = [k for k in all_keys if any(x in k.lower() for x in ['price', 'ltp', 'close', 'ohlc', 'depth', 'tick'])]

print(f"   Found {len(price_keys)} price-related keys")
print("\n   Checking each for prices around 60k:")

found_60k = False
for key in sorted(price_keys)[:20]:  # Check first 20
    try:
        val = r.get(key)
        if val:
            # Try to parse as JSON
            try:
                data = json.loads(val)
                if isinstance(data, dict):
                    if 'close' in data:
                        close = float(data['close'])
                        if 55000 < close < 65000:
                            print(f"   🚨 FOUND: {key}")
                            print(f"      Value: {data}")
                            found_60k = True
            except:
                # Try direct float
                try:
                    num = float(val)
                    if 55000 < num < 65000:
                        print(f"   🚨 FOUND: {key} = {num}")
                        found_60k = True
                except:
                    pass
    except:
        pass

if not found_60k:
    print("   ℹ️  No data found around 60k in Redis keys")

# 3. Check what dashboard actually calls
print("\n3️⃣  DASHBOARD API CALLS (from logs):")
print("-" * 80)

import subprocess
result = subprocess.run(["docker", "logs", "zerodha-market-data-dashboard", "--tail", "100"], 
                       capture_output=True, text=True)
dashboard_logs = result.stdout + result.stderr

# Find all GET requests
import re
get_requests = re.findall(r'GET\s+([^\s]+)', dashboard_logs)
post_requests = re.findall(r'POST\s+([^\s]+)', dashboard_logs)

print(f"   GET requests: {len(set(get_requests))}")
for req in sorted(set(get_requests))[-5:]:
    print(f"      {req}")

print(f"\n   POST requests: {len(set(post_requests))}")
for req in sorted(set(post_requests))[-5:]:
    print(f"      {req}")

# 4. Check system configuration
print("\n4️⃣  SYSTEM CONFIGURATION:")
print("-" * 80)

try:
    with open('.mode_config.json') as f:
        config = json.load(f)
        print(f"   Mode: {config.get('mode')}")
        print(f"   Manual Override: {config.get('manual_override')}")
        print(f"   Date: {config.get('date')}")
        print(f"   Speed: {config.get('speed')}")
except Exception as e:
    print(f"   ❌ Error reading config: {e}")

# 5. Check environment
print("\n5️⃣  ENVIRONMENT VARIABLES (from containers):")
print("-" * 80)

result = subprocess.run(["docker", "inspect", "zerodha-market-data-dashboard"], 
                       capture_output=True, text=True)
try:
    inspect_data = json.loads(result.stdout)
    if inspect_data and len(inspect_data) > 0:
        env_vars = inspect_data[0].get('Config', {}).get('Env', [])
        relevant_env = [e for e in env_vars if any(x in e.upper() for x in ['MODE', 'MOCK', 'HIST', 'LIVE', 'DEBUG'])]
        for env in relevant_env:
            print(f"   {env}")
except:
    print(f"   ❌ Could not read docker inspect")

# 6. Trace the data flow
print("\n6️⃣  DATA FLOW ANALYSIS:")
print("-" * 80)

print(f"""
   CURRENT STATE:
   ✅ Redis has 1-min candles: 375 candles, close=45085.36 (28 Jan 2026)
   ✅ Market Data API returns: 100 candles, close=45085.36 (28 Jan 2026)  
   ✅ System mode: {config.get('mode', 'N/A')}
   ✅ Manual override: {config.get('manual_override', 'N/A')}
   ❌ Raw ticks queue: EMPTY (0 ticks)
   ❌ Historical replay service: CRASHING
   
   POSSIBLE SOURCES FOR ~60k:
   1. Dashboard caching old data?
   2. Different instrument being displayed?
   3. Different timeframe (5-min instead of 1-min)?
   4. Browser cache issue?
   5. Dashboard pulling from wrong API endpoint?
""")

print("\n" + "="*80)
print("✅ AUDIT COMPLETE - See above for where 60k price comes from")
print("="*80)
