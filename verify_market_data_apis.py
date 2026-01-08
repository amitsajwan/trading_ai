"""Verify all Market Data API endpoints have data.

This script tests all exposed endpoints to ensure data is available.
Works for both historical and live modes.
"""
import requests
import json
import time
import sys
from typing import Dict, Any, Optional

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

BASE_URL = "http://localhost:8004"
INSTRUMENT = "BANKNIFTY"

def print_result(endpoint: str, status: str, details: str = ""):
    """Print formatted result."""
    if status == "✅":
        print(f"   {status} {endpoint}: {details}")
    elif status == "❌":
        print(f"   {status} {endpoint}: {details}")
    else:
        print(f"   {status} {endpoint}: {details}")

def check_health() -> bool:
    """Check /health endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            deps = data.get("dependencies", {})
            redis_status = deps.get("redis", "unknown")
            data_avail = deps.get("data_availability", "unknown")
            
            if status == "healthy" and redis_status == "healthy":
                print_result("/health", "✅", f"Status: {status}, Redis: {redis_status}, Data: {data_avail}")
                return True
            else:
                print_result("/health", "⚠️", f"Status: {status}, Redis: {redis_status}, Data: {data_avail}")
                return False
        else:
            print_result("/health", "❌", f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print_result("/health", "❌", f"Error: {e}")
        return False

def check_tick(instrument: str) -> bool:
    """Check /api/v1/market/tick/{instrument} endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/market/tick/{instrument}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data.get("last_price")
            timestamp = data.get("timestamp")
            if price and price > 0:
                print_result(f"/api/v1/market/tick/{instrument}", "✅", 
                            f"Price: {price}, Timestamp: {timestamp}")
                return True
            else:
                print_result(f"/api/v1/market/tick/{instrument}", "❌", 
                            f"No valid price data: {data}")
                return False
        else:
            print_result(f"/api/v1/market/tick/{instrument}", "❌", 
                        f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_result(f"/api/v1/market/tick/{instrument}", "❌", f"Error: {e}")
        return False

def check_ohlc(instrument: str) -> bool:
    """Check /api/v1/market/ohlc/{instrument} endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/market/ohlc/{instrument}?timeframe=minute&limit=10", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                first_bar = data[0]
                print_result(f"/api/v1/market/ohlc/{instrument}", "✅", 
                            f"Found {len(data)} bars, Latest: O={first_bar.get('open')}, H={first_bar.get('high')}, L={first_bar.get('low')}, C={first_bar.get('close')}")
                return True
            else:
                print_result(f"/api/v1/market/ohlc/{instrument}", "❌", 
                            f"No OHLC bars returned: {data}")
                return False
        else:
            print_result(f"/api/v1/market/ohlc/{instrument}", "❌", 
                        f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_result(f"/api/v1/market/ohlc/{instrument}", "❌", f"Error: {e}")
        return False

def check_price(instrument: str) -> bool:
    """Check /api/v1/market/price/{instrument} endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/market/price/{instrument}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data.get("price")
            if price and price > 0:
                print_result(f"/api/v1/market/price/{instrument}", "✅", 
                            f"Price: {price}, Source: {data.get('source', 'unknown')}")
                return True
            else:
                print_result(f"/api/v1/market/price/{instrument}", "❌", 
                            f"No valid price: {data}")
                return False
        else:
            print_result(f"/api/v1/market/price/{instrument}", "❌", 
                        f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_result(f"/api/v1/market/price/{instrument}", "❌", f"Error: {e}")
        return False

def check_raw_data(instrument: str) -> bool:
    """Check /api/v1/market/raw/{instrument} endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/market/raw/{instrument}?limit=10", timeout=5)
        if response.status_code == 200:
            data = response.json()
            keys_found = data.get("keys_found", 0)
            if keys_found > 0:
                print_result(f"/api/v1/market/raw/{instrument}", "✅", 
                            f"Found {keys_found} keys in Redis")
                return True
            else:
                print_result(f"/api/v1/market/raw/{instrument}", "❌", 
                            f"No keys found: {data}")
                return False
        else:
            print_result(f"/api/v1/market/raw/{instrument}", "❌", 
                        f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_result(f"/api/v1/market/raw/{instrument}", "❌", f"Error: {e}")
        return False

def check_options_chain(instrument: str) -> bool:
    """Check /api/v1/options/chain/{instrument} endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/options/chain/{instrument}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            strikes = data.get("strikes", [])
            if len(strikes) > 0:
                print_result(f"/api/v1/options/chain/{instrument}", "✅", 
                            f"Found {len(strikes)} strikes, Expiry: {data.get('expiry', 'N/A')}")
                return True
            else:
                print_result(f"/api/v1/options/chain/{instrument}", "⚠️", 
                            f"No strikes available (may require market hours)")
                return False  # Not critical, but note it
        else:
            print_result(f"/api/v1/options/chain/{instrument}", "⚠️", 
                        f"HTTP {response.status_code} (options may require market hours)")
            return False  # Not critical
    except Exception as e:
        print_result(f"/api/v1/options/chain/{instrument}", "⚠️", f"Error: {e} (options may require market hours)")
        return False  # Not critical

def check_technical_indicators(instrument: str) -> bool:
    """Check /api/v1/technical/indicators/{instrument} endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/technical/indicators/{instrument}?timeframe=minute", timeout=10)
        if response.status_code == 200:
            data = response.json()
            indicators = data.get("indicators", {})
            if indicators and len(indicators) > 0:
                # Check for key indicators
                has_rsi = "rsi_14" in indicators
                has_sma = "sma_20" in indicators
                print_result(f"/api/v1/technical/indicators/{instrument}", "✅", 
                            f"Found {len(indicators)} indicators, RSI: {has_rsi}, SMA: {has_sma}")
                return True
            else:
                print_result(f"/api/v1/technical/indicators/{instrument}", "⚠️", 
                            f"No indicators calculated yet (may need more data)")
                return False  # Not critical, indicators need time to calculate
        else:
            print_result(f"/api/v1/technical/indicators/{instrument}", "⚠️", 
                        f"HTTP {response.status_code} (indicators may need more data)")
            return False  # Not critical
    except Exception as e:
        print_result(f"/api/v1/technical/indicators/{instrument}", "⚠️", f"Error: {e} (indicators may need more data)")
        return False  # Not critical

def check_market_depth(instrument: str) -> bool:
    """Check /api/v1/market/depth/{instrument} endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/market/depth/{instrument}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            buy_depth = data.get("buy", [])
            sell_depth = data.get("sell", [])
            if len(buy_depth) > 0 or len(sell_depth) > 0:
                print_result(f"/api/v1/market/depth/{instrument}", "✅", 
                            f"Buy levels: {len(buy_depth)}, Sell levels: {len(sell_depth)}")
                return True
            else:
                print_result(f"/api/v1/market/depth/{instrument}", "⚠️", 
                            f"No depth data (may require live market hours)")
                return False  # Not critical
        else:
            print_result(f"/api/v1/market/depth/{instrument}", "⚠️", 
                        f"HTTP {response.status_code} (depth may require live market hours)")
            return False  # Not critical
    except Exception as e:
        print_result(f"/api/v1/market/depth/{instrument}", "⚠️", f"Error: {e} (depth may require live market hours)")
        return False  # Not critical

def main():
    """Run all API verifications."""
    print("=" * 60)
    print("🔍 Market Data API Verification")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Instrument: {INSTRUMENT}")
    print()
    
    # Wait for API to be ready
    print("⏳ Waiting for Market Data API to be ready...")
    max_wait = 30
    waited = 0
    while waited < max_wait:
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print("✅ Market Data API is ready")
                break
        except:
            pass
        time.sleep(1)
        waited += 1
        if waited % 5 == 0:
            print(f"   Still waiting... ({waited}s)")
    
    if waited >= max_wait:
        print("❌ Market Data API not ready after 30 seconds")
        return False
    
    print()
    print("Testing all endpoints...")
    print()
    
    results = {}
    
    # Critical endpoints (must have data)
    results["health"] = check_health()
    results["tick"] = check_tick(INSTRUMENT)
    results["price"] = check_price(INSTRUMENT)
    results["raw"] = check_raw_data(INSTRUMENT)
    results["ohlc"] = check_ohlc(INSTRUMENT)
    
    print()
    print("Testing optional endpoints...")
    print()
    
    # Optional endpoints (nice to have)
    results["options"] = check_options_chain(INSTRUMENT)
    results["indicators"] = check_technical_indicators(INSTRUMENT)
    results["depth"] = check_market_depth(INSTRUMENT)
    
    print()
    print("=" * 60)
    print("📊 Verification Summary")
    print("=" * 60)
    
    critical_passed = sum(1 for k in ["health", "tick", "price", "raw", "ohlc"] if results.get(k, False))
    critical_total = 5
    optional_passed = sum(1 for k in ["options", "indicators", "depth"] if results.get(k, False))
    optional_total = 3
    
    print(f"Critical Endpoints: {critical_passed}/{critical_total} passed")
    print(f"Optional Endpoints: {optional_passed}/{optional_total} passed")
    print()
    
    if critical_passed == critical_total:
        print("✅ All critical endpoints have data!")
        return True
    else:
        print(f"⚠️  {critical_total - critical_passed} critical endpoint(s) missing data")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

