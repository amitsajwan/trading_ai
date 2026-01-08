"""Verify both historical and live modes at market_data level"""
import requests
import redis
import json
import time
import sys
import os
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

IST = timezone(timedelta(hours=5, minutes=30))
BASE_URL = "http://localhost:8004"

def check_api_running():
    """Check if API is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=3)
        if response.status_code == 200:
            return True, response.json()
        return False, None
    except:
        return False, None

def get_redis_data():
    """Get current data from Redis"""
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    # Get latest price and timestamp
    price = r.get('price:BANKNIFTY:latest')
    ts = r.get('price:BANKNIFTY:latest_ts')
    
    # Get virtual time
    virtual_time_enabled = r.get("system:virtual_time:enabled")
    virtual_time_current = r.get("system:virtual_time:current")
    
    # Get most recent tick
    tick_keys = sorted(r.keys('tick:BANKNIFTY:*'))
    most_recent_tick = None
    if tick_keys:
        for key in reversed(tick_keys[-20:]):
            if ':latest' in key:
                continue
            try:
                tick_data = r.get(key)
                if tick_data:
                    tick = json.loads(tick_data)
                    ts_str = tick.get('timestamp', '')
                    if ts_str:
                        most_recent_tick = {
                            'key': key,
                            'timestamp': ts_str,
                            'price': tick.get('last_price')
                        }
                        break
            except:
                pass
    
    return {
        'price': float(price) if price else None,
        'timestamp': ts,
        'virtual_time_enabled': virtual_time_enabled == "1" if virtual_time_enabled else False,
        'virtual_time_current': virtual_time_current,
        'most_recent_tick': most_recent_tick,
        'total_ticks': len(tick_keys) if tick_keys else 0
    }

def determine_mode(redis_data):
    """Determine if we're in historical or live mode"""
    if redis_data['virtual_time_enabled']:
        return "HISTORICAL", redis_data['virtual_time_current']
    
    if not redis_data['timestamp']:
        return "UNKNOWN", None
    
    try:
        data_ts = parse(redis_data['timestamp'])
        if data_ts.tzinfo is None:
            data_ts = data_ts.replace(tzinfo=IST)
        
        now_ist = datetime.now(IST)
        age_seconds = (now_ist - data_ts).total_seconds()
        age_days = age_seconds / 86400
        
        if age_days > 1:
            return "HISTORICAL", data_ts.strftime('%Y-%m-%d')
        elif age_seconds < 300:  # Less than 5 minutes
            return "LIVE", "current"
        else:
            if age_seconds < 86400:  # Less than 1 day
                return "LIVE (stale)", f"{age_seconds/3600:.1f} hours old"
            else:
                return "HISTORICAL", data_ts.strftime('%Y-%m-%d')
    except:
        return "UNKNOWN", None

def test_endpoints():
    """Test all API endpoints"""
    results = {}
    endpoints = [
        ("/health", "Health Check"),
        ("/api/v1/market/tick/BANKNIFTY", "Latest Tick"),
        ("/api/v1/market/price/BANKNIFTY", "Latest Price"),
        ("/api/v1/market/ohlc/BANKNIFTY?timeframe=minute&limit=5", "OHLC Bars"),
        ("/api/v1/market/raw/BANKNIFTY?limit=5", "Raw Data"),
    ]
    
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                results[name] = {"status": "OK", "data": data}
            else:
                results[name] = {"status": "ERROR", "code": response.status_code}
        except Exception as e:
            results[name] = {"status": "ERROR", "error": str(e)}
    
    return results

def verify_mode(mode_name):
    """Verify current mode"""
    print("=" * 70)
    print(f"MODE: {mode_name}")
    print("=" * 70)
    
    # Check API
    api_running, health = check_api_running()
    if not api_running:
        print("ERROR: API is not running on port 8004")
        print("\nTo start API from market_data level:")
        print('  cd market_data')
        print('  $env:PYTHONPATH = "./src"; python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host=\'0.0.0.0\', port=8004)"')
        return False
    
    print("OK: API is running")
    
    # Get Redis data
    redis_data = get_redis_data()
    mode, mode_info = determine_mode(redis_data)
    
    print(f"\nMode Detection: {mode}")
    if mode_info:
        print(f"Mode Info: {mode_info}")
    
    # Verify mode matches
    expected_keywords = mode_name.upper().split()
    mode_upper = mode.upper()
    matches = any(keyword in mode_upper for keyword in expected_keywords)
    
    if not matches:
        print(f"\nWARNING: Expected {mode_name} mode, but detected: {mode}")
        return False
    
    # For historical mode, show data date info
    if "HISTORICAL" in mode_name.upper():
        if redis_data['timestamp']:
            ts = parse(redis_data['timestamp'])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=IST)
            now_ist = datetime.now(IST)
            age_days = (now_ist - ts).total_seconds() / 86400
            
            print(f"\nHistorical Replay Info:")
            print(f"  Replaying data from: {ts.strftime('%Y-%m-%d %H:%M:%S IST')}")
            if age_days >= 1:
                print(f"  Data is {age_days:.1f} days old")
            else:
                print(f"  Data is from today (replaying today's historical data)")
            if redis_data['virtual_time_current']:
                vt_ts = parse(redis_data['virtual_time_current'])
                if vt_ts.tzinfo is None:
                    vt_ts = vt_ts.replace(tzinfo=IST)
                print(f"  Virtual time: {vt_ts.strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    print(f"\nRedis Data:")
    print(f"  Price: {redis_data['price']}")
    
    # Format timestamp in IST
    if redis_data['timestamp']:
        ts = parse(redis_data['timestamp'])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        ts_ist = ts.strftime('%Y-%m-%d %H:%M:%S IST')
        now_ist = datetime.now(IST)
        age_seconds = (now_ist - ts).total_seconds()
        age_days = age_seconds / 86400
        
        print(f"  Timestamp: {ts_ist}")
        if age_days > 1:
            print(f"  Data Age: {age_days:.1f} days old (HISTORICAL)")
        elif age_seconds < 300:
            print(f"  Data Age: {age_seconds:.0f} seconds old (LIVE)")
        else:
            print(f"  Data Age: {age_seconds/3600:.1f} hours old")
    else:
        print(f"  Timestamp: None")
    
    print(f"  Virtual Time Enabled: {redis_data['virtual_time_enabled']}")
    if redis_data['virtual_time_current']:
        vt_ts = parse(redis_data['virtual_time_current'])
        if vt_ts.tzinfo is None:
            vt_ts = vt_ts.replace(tzinfo=IST)
        print(f"  Virtual Time: {vt_ts.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"  Total Ticks: {redis_data['total_ticks']}")
    
    if redis_data['most_recent_tick']:
        tick_ts = parse(redis_data['most_recent_tick']['timestamp'])
        if tick_ts.tzinfo is None:
            tick_ts = tick_ts.replace(tzinfo=IST)
        now_ist = datetime.now(IST)
        age_seconds = (now_ist - tick_ts).total_seconds()
        age_days = age_seconds / 86400
        
        # Format timestamp in IST
        tick_ts_ist = tick_ts.strftime('%Y-%m-%d %H:%M:%S IST')
        print(f"  Most Recent Tick: {tick_ts_ist}")
        print(f"  Tick Price: {redis_data['most_recent_tick']['price']}")
        if age_days > 1:
            print(f"  Tick Age: {age_days:.1f} days ({age_seconds/3600:.1f} hours)")
        else:
            print(f"  Tick Age: {age_seconds/60:.1f} minutes")
        
        # For historical mode, show replay info
        if "HISTORICAL" in mode:
            if age_days >= 1:
                print(f"  Historical replay: {age_days:.1f} days old data")
            else:
                print(f"  Historical replay: Today's data being replayed")
    
    # Test endpoints
    print(f"\nTesting Endpoints:")
    results = test_endpoints()
    passed = 0
    total = len(results)
    
    for name, result in results.items():
        if result['status'] == 'OK':
            print(f"  OK: {name}")
            passed += 1
        else:
            print(f"  ERROR: {name} - {result.get('code', result.get('error', 'Unknown'))}")
    
    print(f"\nResults: {passed}/{total} endpoints passed")
    
    if passed == total:
        print(f"SUCCESS: {mode_name} mode verified!")
        return True
    else:
        print(f"WARNING: Some endpoints failed")
        return False

def main():
    print("=" * 70)
    print("MARKET_DATA LEVEL VERIFICATION")
    print("=" * 70)
    print("\nThis script verifies the CURRENT mode")
    print("Works independently of start_local.py")
    print("Make sure the API is running on port 8004\n")
    
    # Check current mode
    redis_data = get_redis_data()
    mode, mode_info = determine_mode(redis_data)
    
    print(f"Current Mode Detected: {mode}")
    if mode_info:
        print(f"Mode Info: {mode_info}\n")
    
    # Verify based on current mode
    if "HISTORICAL" in mode:
        success = verify_mode("HISTORICAL")
        print("\n" + "=" * 70)
        print("TO TEST LIVE MODE:")
        print("=" * 70)
        print("1. Stop historical replay")
        print("2. Clear virtual time: python -c \"import redis; r=redis.Redis(); r.delete('system:virtual_time:enabled'); r.delete('system:virtual_time:current')\"")
        print("3. Start live collectors: python start_local.py --provider zerodha")
        print("4. Wait 5-10 seconds")
        print("5. Run this script again")
        return success
    elif "LIVE" in mode:
        success = verify_mode("LIVE")
        print("\n" + "=" * 70)
        print("TO TEST HISTORICAL MODE:")
        print("=" * 70)
        print("1. Stop live collectors")
        print("2. Start historical replay: python start_local.py --provider historical --historical-source zerodha --historical-speed 10")
        print("3. Wait for replay to populate data")
        print("4. Run this script again")
        return success
    else:
        print("WARNING: Could not determine mode")
        print("Please start either:")
        print("  - Historical: python start_local.py --provider historical --historical-source zerodha --historical-speed 10")
        print("  - Live: python start_local.py --provider zerodha")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

