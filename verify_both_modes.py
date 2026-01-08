"""Verify both historical and live modes from scratch"""
import requests
import redis
import json
import time
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse

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
    
    # Get most recent tick keys
    tick_keys = sorted(r.keys('tick:BANKNIFTY:*'))
    most_recent_tick = None
    if tick_keys:
        # Get the most recent one by timestamp
        for key in reversed(tick_keys[-20:]):  # Check last 20
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
            # Could be stale live data or historical
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

def verify_historical_mode():
    """Verify historical mode"""
    print("=" * 70)
    print("MODE 1: HISTORICAL REPLAY MODE")
    print("=" * 70)
    
    # Check API
    api_running, health = check_api_running()
    if not api_running:
        print("ERROR: API is not running on port 8004")
        print("Please start it first:")
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
    
    if "HISTORICAL" not in mode:
        print(f"\nWARNING: Expected HISTORICAL mode, but detected: {mode}")
        print("To start historical mode:")
        print("  python start_local.py --provider historical --historical-source zerodha --historical-speed 0")
        return False
    
    print(f"\nRedis Data:")
    print(f"  Price: {redis_data['price']}")
    print(f"  Timestamp: {redis_data['timestamp']}")
    print(f"  Virtual Time Enabled: {redis_data['virtual_time_enabled']}")
    if redis_data['virtual_time_current']:
        print(f"  Virtual Time: {redis_data['virtual_time_current']}")
    print(f"  Total Ticks: {redis_data['total_ticks']}")
    
    if redis_data['most_recent_tick']:
        print(f"  Most Recent Tick: {redis_data['most_recent_tick']['timestamp']} - Price: {redis_data['most_recent_tick']['price']}")
    
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
        print("SUCCESS: Historical mode verified!")
        return True
    else:
        print("WARNING: Some endpoints failed")
        return False

def verify_live_mode():
    """Verify live mode"""
    print("\n" + "=" * 70)
    print("MODE 2: LIVE DATA MODE")
    print("=" * 70)
    
    # Check API
    api_running, health = check_api_running()
    if not api_running:
        print("ERROR: API is not running on port 8004")
        return False
    
    print("OK: API is running")
    
    # Get Redis data
    redis_data = get_redis_data()
    mode, mode_info = determine_mode(redis_data)
    
    print(f"\nMode Detection: {mode}")
    if mode_info:
        print(f"Mode Info: {mode_info}")
    
    if "LIVE" not in mode:
        print(f"\nWARNING: Expected LIVE mode, but detected: {mode}")
        print("To start live mode:")
        print("  python start_local.py --provider zerodha")
        return False
    
    print(f"\nRedis Data:")
    print(f"  Price: {redis_data['price']}")
    print(f"  Timestamp: {redis_data['timestamp']}")
    print(f"  Virtual Time Enabled: {redis_data['virtual_time_enabled']} (should be False)")
    print(f"  Total Ticks: {redis_data['total_ticks']}")
    
    if redis_data['most_recent_tick']:
        tick_ts = parse(redis_data['most_recent_tick']['timestamp'])
        if tick_ts.tzinfo is None:
            tick_ts = tick_ts.replace(tzinfo=IST)
        now_ist = datetime.now(IST)
        age_seconds = (now_ist - tick_ts).total_seconds()
        print(f"  Most Recent Tick: {redis_data['most_recent_tick']['timestamp']} - Price: {redis_data['most_recent_tick']['price']}")
        print(f"  Tick Age: {age_seconds/60:.1f} minutes")
        
        if age_seconds < 300:
            print("  OK: Data is fresh (less than 5 minutes old)")
        else:
            print(f"  WARNING: Data is {age_seconds/3600:.1f} hours old (may be outside market hours)")
    
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
        print("SUCCESS: Live mode verified!")
        return True
    else:
        print("WARNING: Some endpoints failed")
        return False

def main():
    print("=" * 70)
    print("COMPREHENSIVE MODE VERIFICATION")
    print("=" * 70)
    print("\nThis script verifies the CURRENT mode")
    print("Make sure the API is running on port 8004\n")
    
    # Check current mode
    redis_data = get_redis_data()
    mode, mode_info = determine_mode(redis_data)
    
    print(f"Current Mode Detected: {mode}")
    if mode_info:
        print(f"Mode Info: {mode_info}\n")
    
    # Verify based on current mode
    if "HISTORICAL" in mode:
        print("Verifying HISTORICAL mode...\n")
        hist_ok = verify_historical_mode()
        print("\n" + "=" * 70)
        print("TO TEST LIVE MODE:")
        print("=" * 70)
        print("1. Stop historical replay")
        print("2. Run: python start_local.py --provider zerodha")
        print("3. Wait 5-10 seconds for data")
        print("4. Run this script again")
        print(f"\nHistorical Mode: {'PASSED' if hist_ok else 'FAILED'}")
    elif "LIVE" in mode:
        print("Verifying LIVE mode...\n")
        live_ok = verify_live_mode()
        print("\n" + "=" * 70)
        print("TO TEST HISTORICAL MODE:")
        print("=" * 70)
        print("1. Stop live collectors")
        print("2. Run: python start_local.py --provider historical --historical-source zerodha --historical-speed 0")
        print("3. Wait for replay to complete")
        print("4. Run this script again")
        print(f"\nLive Mode: {'PASSED' if live_ok else 'FAILED'}")
    else:
        print("WARNING: Could not determine mode")
        print("Please start either:")
        print("  - Historical: python start_local.py --provider historical --historical-source zerodha --historical-speed 0")
        print("  - Live: python start_local.py --provider zerodha")

if __name__ == "__main__":
    main()

