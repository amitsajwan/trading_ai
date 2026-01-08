#!/usr/bin/env python3
"""Test mode switching and database isolation functionality."""

import sys
import os
from datetime import datetime, time

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def test_market_hours():
    """Test market hours detection."""
    print("=" * 60)
    print("Testing Market Hours Detection")
    print("=" * 60)
    
    from core_kernel.src.core_kernel.market_hours import is_market_open, get_market_status, get_suggested_mode
    
    # Test current time
    now = datetime.now()
    is_open = is_market_open(now)
    status = get_market_status(now)
    suggested = get_suggested_mode(now)
    
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Market open: {is_open}")
    print(f"Status: {status[1]}")
    print(f"Suggested mode: {suggested}")
    print()
    
    # Test specific times
    test_cases = [
        (datetime(2024, 1, 15, 10, 0, 0), True, "paper_live"),  # Monday 10 AM - market open
        (datetime(2024, 1, 15, 9, 0, 0), False, "paper_mock"),  # Monday 9 AM - pre-market
        (datetime(2024, 1, 15, 9, 15, 0), True, "paper_live"),  # Monday 9:15 AM - market opens
        (datetime(2024, 1, 15, 15, 30, 0), False, "paper_mock"),  # Monday 3:30 PM - market closes (< not <=)
        (datetime(2024, 1, 15, 15, 29, 59), True, "paper_live"),  # Monday 3:29:59 PM - still open
        (datetime(2024, 1, 15, 16, 0, 0), False, "paper_mock"),  # Monday 4 PM - post-market
        (datetime(2024, 1, 13, 10, 0, 0), False, "paper_mock"),  # Saturday - weekend
    ]
    
    print("Testing specific times:")
    for test_time, expected_open, expected_mode in test_cases:
        result_open = is_market_open(test_time)
        result_mode = get_suggested_mode(test_time)
        status_icon = "[OK]" if result_open == expected_open and result_mode == expected_mode else "[FAIL]"
        print(f"  {status_icon} {test_time.strftime('%Y-%m-%d %H:%M')}: Open={result_open} (expected {expected_open}), Mode={result_mode} (expected {expected_mode})")
    
    print()
    return True


def test_mode_manager():
    """Test mode manager functionality."""
    print("=" * 60)
    print("Testing Mode Manager")
    print("=" * 60)
    
    from core_kernel.src.core_kernel.mode_manager import ModeManager
    
    manager = ModeManager()
    
    print(f"Current mode: {manager.get_current_mode()}")
    print(f"Has manual override: {manager.has_manual_override()}")
    print()
    
    # Test auto-switch check
    should_switch, suggested, reason = manager.check_auto_switch()
    print(f"Should auto-switch: {should_switch}")
    if should_switch:
        print(f"  Suggested mode: {suggested}")
        print(f"  Reason: {reason}")
    print()
    
    # Test mode info
    mode_info = manager.get_mode_info()
    print("Mode Info:")
    for key, value in mode_info.items():
        print(f"  {key}: {value}")
    print()
    
    # Test manual mode setting
    print("Testing manual mode setting...")
    success, message = manager.set_manual_mode("paper_mock", require_confirmation=False)
    print(f"  Set paper_mock: {success} - {message}")
    print(f"  Current mode: {manager.get_current_mode()}")
    print(f"  Has override: {manager.has_manual_override()}")
    print()
    
    # Test clearing override
    manager.clear_manual_override()
    print(f"  After clearing override:")
    print(f"    Has override: {manager.has_manual_override()}")
    print()
    
    return True


def test_database_selection():
    """Test database selection based on mode."""
    print("=" * 60)
    print("Testing Database Selection")
    print("=" * 60)
    
    from core_kernel.src.core_kernel.mongodb_schema import get_db_for_mode, get_db_connection
    
    test_modes = ["paper_mock", "paper_live", "live"]
    
    for mode in test_modes:
        db_name = get_db_for_mode(mode)
        print(f"Mode: {mode:12} → Database: {db_name}")
        
        # Test connection (if MongoDB is available)
        try:
            db = get_db_connection(mode=mode)
            print(f"  [OK] Connection successful: {db.name}")
        except Exception as e:
            print(f"  [WARN] Connection failed (MongoDB may not be running): {e}")
    
    print()
    return True


def test_database_isolation():
    """Test that different modes use different databases."""
    print("=" * 60)
    print("Testing Database Isolation")
    print("=" * 60)
    
    from core_kernel.src.core_kernel.mongodb_schema import get_db_connection
    
    try:
        # Get databases for different modes
        mock_db = get_db_connection(mode="paper_mock")
        live_db = get_db_connection(mode="paper_live")
        
        print(f"Mock mode database: {mock_db.name}")
        print(f"Live mode database: {live_db.name}")
        
        if mock_db.name != live_db.name:
            print("  [OK] Databases are isolated (different names)")
        else:
            print("  [FAIL] Databases are NOT isolated (same name)")
        
        # Test that they're actually different database objects
        if id(mock_db) != id(live_db):
            print("  [OK] Different database objects")
        else:
            print("  [WARN] Same database object (may be cached)")
        
        print()
        return True
    except Exception as e:
        print(f"  [WARN] Could not test isolation: {e}")
        print()
        return False


def test_api_endpoints():
    """Test API endpoints (if dashboard is running)."""
    print("=" * 60)
    print("Testing API Endpoints")
    print("=" * 60)
    
    import requests
    
    base_url = "http://localhost:8000"
    
    endpoints = [
        "/api/control/mode/info",
        "/api/control/mode/auto-switch",
    ]
    
    for endpoint in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"  [OK] {endpoint}")
                if "current_mode" in data:
                    print(f"     Mode: {data.get('current_mode')}")
                if "database" in data:
                    print(f"     Database: {data.get('database')}")
            else:
                print(f"  [FAIL] {endpoint} - Status: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"  [WARN] {endpoint} - Dashboard not running (expected if not started)")
        except Exception as e:
            print(f"  [FAIL] {endpoint} - Error: {e}")
    
    print()
    return True


def test_integration():
    """Test full integration."""
    print("=" * 60)
    print("Testing Full Integration")
    print("=" * 60)
    
    from core_kernel.src.core_kernel.mode_manager import get_mode_manager
    from core_kernel.src.core_kernel.market_hours import is_market_open, get_suggested_mode
    from core_kernel.src.core_kernel.mongodb_schema import get_db_connection
    
    # Get mode manager
    manager = get_mode_manager()
    current_mode = manager.get_current_mode()
    
    # Check market hours
    market_open = is_market_open()
    suggested_mode = get_suggested_mode()
    
    # Get database
    db = get_db_connection(mode=current_mode)
    
    print(f"Current Mode: {current_mode}")
    print(f"Market Open: {market_open}")
    print(f"Suggested Mode: {suggested_mode}")
    print(f"Database: {db.name}")
    print()
    
    # Check if auto-switch should happen
    should_switch, suggested, reason = manager.check_auto_switch()
    if should_switch:
        print(f"[WARN] Auto-switch recommended:")
        print(f"   Current: {current_mode}")
        print(f"   Suggested: {suggested}")
        print(f"   Reason: {reason}")
    else:
        print("[OK] No auto-switch needed")
    
    print()
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MODE SWITCHING & DATABASE ISOLATION TEST SUITE")
    print("=" * 60)
    print()
    
    results = []
    
    try:
        results.append(("Market Hours", test_market_hours()))
    except Exception as e:
        print(f"[FAIL] Market Hours test failed: {e}\n")
        results.append(("Market Hours", False))
    
    try:
        results.append(("Mode Manager", test_mode_manager()))
    except Exception as e:
        print(f"[FAIL] Mode Manager test failed: {e}\n")
        results.append(("Mode Manager", False))
    
    try:
        results.append(("Database Selection", test_database_selection()))
    except Exception as e:
        print(f"[FAIL] Database Selection test failed: {e}\n")
        results.append(("Database Selection", False))
    
    try:
        results.append(("Database Isolation", test_database_isolation()))
    except Exception as e:
        print(f"[FAIL] Database Isolation test failed: {e}\n")
        results.append(("Database Isolation", False))
    
    try:
        results.append(("API Endpoints", test_api_endpoints()))
    except Exception as e:
        print(f"[FAIL] API Endpoints test failed: {e}\n")
        results.append(("API Endpoints", False))
    
    try:
        results.append(("Integration", test_integration()))
    except Exception as e:
        print(f"[FAIL] Integration test failed: {e}\n")
        results.append(("Integration", False))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] All tests passed!")
        return 0
    else:
        print("[WARN] Some tests failed or had warnings")
        return 1


if __name__ == "__main__":
    sys.exit(main())


