#!/usr/bin/env python3
"""
Quick System Status Check

Run anytime to check if live mode is healthy.

Usage:
    python check_status.py
"""

import redis
import subprocess
import sys
from datetime import datetime

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

BANKNIFTY_MIN = 50000
BANKNIFTY_MAX = 70000


def check_services():
    """Check if required services are running."""
    required = [
        "zerodha-redis",
        "zerodha-market-data-api",
        "zerodha-market-data-dashboard",
        "zerodha-websocket-tick-collector-banknifty",
        "zerodha-ltp-collector-banknifty"
    ]
    
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    running = result.stdout.lower()
    all_running = True
    
    for service in required:
        name = service.replace("zerodha-", "")
        if service.lower() in running:
            print(f"  {GREEN}✓{RESET} {name}")
        else:
            print(f"  {RED}✗{RESET} {name} (NOT RUNNING)")
            all_running = False
    
    return all_running


def check_price():
    """Check if price is realistic."""
    try:
        r = redis.Redis(host='localhost', port=6380, decode_responses=True)
        price_str = r.get("indicators:BANKNIFTY26FEBFUT:current_price")
        
        if not price_str:
            print(f"  {RED}✗{RESET} No price in Redis")
            return False
        
        price = float(price_str)
        
        if price < BANKNIFTY_MIN:
            print(f"  {RED}✗{RESET} Price: ₹{price:,.2f} (TOO LOW - likely mock data!)")
            return False
        elif price > BANKNIFTY_MAX:
            print(f"  {YELLOW}⚠{RESET} Price: ₹{price:,.2f} (HIGH - verify market)")
            return True
        else:
            print(f"  {GREEN}✓{RESET} Price: ₹{price:,.2f} (realistic range)")
            return True
    except Exception as e:
        print(f"  {RED}✗{RESET} Cannot check price: {e}")
        return False


def check_websocket():
    """Check WebSocket connection."""
    try:
        result = subprocess.run(
            ["docker", "logs", "zerodha-websocket-tick-collector-banknifty", "--tail", "20"],
            capture_output=True,
            text=True,
            timeout=5
        )
        logs = result.stdout + result.stderr
        
        if "connected=False" in logs or "403" in logs:
            print(f"  {RED}✗{RESET} WebSocket disconnected")
            return False
        elif "Processed tick" in logs:
            print(f"  {GREEN}✓{RESET} WebSocket connected and processing")
            return True
        else:
            print(f"  {YELLOW}⚠{RESET} WebSocket status unclear")
            return True
    except Exception as e:
        print(f"  {RED}✗{RESET} Cannot check WebSocket: {e}")
        return False


def check_dashboard():
    """Check if dashboard is accessible."""
    try:
        import requests
        response = requests.get("http://localhost:8008", timeout=5)
        if response.status_code == 200:
            print(f"  {GREEN}✓{RESET} Dashboard accessible (http://localhost:8008)")
            return True
        else:
            print(f"  {RED}✗{RESET} Dashboard returned {response.status_code}")
            return False
    except Exception as e:
        print(f"  {RED}✗{RESET} Dashboard not accessible: {e}")
        return False


def check_mock_interference():
    """Check for mock services."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        containers = result.stdout.lower()
        
        if "mock-publisher" in containers or "mock-options" in containers:
            print(f"  {RED}✗{RESET} Mock services detected!")
            return False
        elif "historical-replay" in containers:
            print(f"  {YELLOW}⚠{RESET} Historical replay running")
            return False
        else:
            print(f"  {GREEN}✓{RESET} No interference detected")
            return True
    except Exception as e:
        print(f"  {YELLOW}⚠{RESET} Cannot check: {e}")
        return True


def main():
    """Run all checks."""
    print()
    print("=" * 60)
    print(f"{BOLD}SYSTEM STATUS CHECK{RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    checks = [
        ("Services Running", check_services),
        ("Price Sanity", check_price),
        ("WebSocket Connection", check_websocket),
        ("Dashboard Accessible", check_dashboard),
        ("No Interference", check_mock_interference),
    ]
    
    results = []
    
    for name, check_func in checks:
        print(f"{BLUE}{name}:{RESET}")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"  {RED}✗{RESET} Error: {e}")
            results.append(False)
        print()
    
    # Summary
    print("=" * 60)
    if all(results):
        print(f"{GREEN}{BOLD}✅ SYSTEM HEALTHY - ALL CHECKS PASSED{RESET}")
        print("=" * 60)
        print()
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}❌ SYSTEM ISSUES DETECTED{RESET}")
        print("=" * 60)
        print()
        print(f"Run {YELLOW}python start_live_validated.py{RESET} to diagnose and fix.")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
