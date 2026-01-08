#!/usr/bin/env python3
"""Test time synchronization and virtual time functionality."""

import sys
import os
from datetime import datetime, time, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def test_time_service():
    """Test TimeService virtual time functionality."""
    print("=" * 60)
    print("Testing TimeService")
    print("=" * 60)
    
    try:
        from core_kernel.src.core_kernel.time_service import (
            now as get_system_time,
            set_virtual_time,
            clear_virtual_time,
            is_virtual_time
        )
        
        # Test 1: Real time mode
        print("\n1. Real-time mode:")
        clear_virtual_time()
        real_time = get_system_time()
        is_virtual = is_virtual_time()
        print(f"   Time: {real_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Virtual: {is_virtual}")
        print(f"   [{'PASS' if not is_virtual else 'FAIL'}] Real-time mode working")
        
        # Test 2: Virtual time mode
        print("\n2. Virtual time mode:")
        virtual_dt = datetime(2026, 1, 6, 10, 0, 0)
        set_virtual_time(virtual_dt)
        virt_time = get_system_time()
        is_virtual = is_virtual_time()
        print(f"   Set: {virtual_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Got: {virt_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Virtual: {is_virtual}")
        
        # Allow for small timezone differences
        time_diff = abs((virt_time - virtual_dt).total_seconds())
        print(f"   Time diff: {time_diff} seconds")
        print(f"   [{'PASS' if is_virtual and time_diff < 60 else 'FAIL'}] Virtual time mode working")
        
        # Test 3: Clear virtual time
        print("\n3. Clear virtual time:")
        clear_virtual_time()
        is_virtual = is_virtual_time()
        print(f"   Virtual: {is_virtual}")
        print(f"   [{'PASS' if not is_virtual else 'FAIL'}] Virtual time cleared")
        
        return True
    except Exception as e:
        print(f"   [FAIL] TimeService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_market_hours_with_virtual_time():
    """Test market hours checking with virtual time."""
    print("\n" + "=" * 60)
    print("Testing Market Hours with Virtual Time")
    print("=" * 60)
    
    try:
        from core_kernel.src.core_kernel.time_service import set_virtual_time, clear_virtual_time
        from core_kernel.src.core_kernel.market_hours import is_market_open, get_market_status
        
        test_cases = [
            (datetime(2026, 1, 6, 10, 0, 0), True, "Monday 10:00 AM - market open"),
            (datetime(2026, 1, 6, 9, 15, 0), True, "Monday 9:15 AM - market opens"),
            (datetime(2026, 1, 6, 9, 14, 59), False, "Monday 9:14:59 AM - pre-market"),
            (datetime(2026, 1, 6, 15, 29, 59), True, "Monday 3:29:59 PM - still open"),
            (datetime(2026, 1, 6, 15, 30, 0), False, "Monday 3:30 PM - market closes (< not <=)"),
            (datetime(2026, 1, 6, 16, 0, 0), False, "Monday 4:00 PM - after hours"),
            (datetime(2026, 1, 10, 12, 0, 0), False, "Saturday 12:00 PM - weekend"),
            (datetime(2026, 1, 11, 12, 0, 0), False, "Sunday 12:00 PM - weekend"),
        ]
        
        passed = 0
        failed = 0
        
        print("\nTesting market hours detection:")
        for test_time, expected_open, description in test_cases:
            set_virtual_time(test_time)
            result = is_market_open(test_time)
            status_msg, status_desc = get_market_status(test_time)
            
            status = "PASS" if result == expected_open else "FAIL"
            if result == expected_open:
                passed += 1
            else:
                failed += 1
                
            print(f"   [{status}] {description}")
            print(f"         Expected: {expected_open}, Got: {result}")
            if status == "FAIL":
                print(f"         Status: {status_desc}")
        
        clear_virtual_time()
        
        print(f"\nResults: {passed} passed, {failed} failed")
        return failed == 0
        
    except Exception as e:
        print(f"   [FAIL] Market hours test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator_market_hours_check():
    """Test that orchestrator respects market hours."""
    print("\n" + "=" * 60)
    print("Testing Orchestrator Market Hours Integration")
    print("=" * 60)
    
    try:
        from core_kernel.src.core_kernel.time_service import set_virtual_time, clear_virtual_time, now as get_system_time
        from core_kernel.src.core_kernel.market_hours import is_market_open
        
        # Test during market hours
        print("\n1. During market hours (10:00 AM):")
        market_open_time = datetime(2026, 1, 6, 10, 0, 0)
        set_virtual_time(market_open_time)
        
        current_time = get_system_time()
        market_open = is_market_open(current_time)
        
        print(f"   Virtual time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Market open: {market_open}")
        print(f"   [{'PASS' if market_open else 'FAIL'}] Market should be open")
        
        # Test after market close
        print("\n2. After market close (3:30 PM):")
        market_close_time = datetime(2026, 1, 6, 15, 30, 0)
        set_virtual_time(market_close_time)
        
        current_time = get_system_time()
        market_open = is_market_open(current_time)
        
        print(f"   Virtual time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Market open: {market_open}")
        print(f"   [{'PASS' if not market_open else 'FAIL'}] Market should be closed")
        
        clear_virtual_time()
        return True
        
    except Exception as e:
        print(f"   [FAIL] Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_redis_time_sync():
    """Test Redis-based time synchronization."""
    print("\n" + "=" * 60)
    print("Testing Redis Time Synchronization")
    print("=" * 60)
    
    try:
        import redis
        from core_kernel.src.core_kernel.time_service import set_virtual_time, clear_virtual_time, is_virtual_time
        
        # Connect to Redis
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        r = redis.Redis(host=host, port=port, db=0)
        
        print(f"\n1. Connecting to Redis at {host}:{port}...")
        r.ping()
        print("   [PASS] Redis connection successful")
        
        # Test setting virtual time
        print("\n2. Setting virtual time via TimeService...")
        test_time = datetime(2026, 1, 6, 12, 30, 0)
        set_virtual_time(test_time)
        
        # Check Redis keys
        enabled = r.get("system:virtual_time:enabled")
        current = r.get("system:virtual_time:current")
        
        print(f"   Enabled flag: {enabled}")
        print(f"   Current time: {current}")
        print(f"   [{'PASS' if enabled and current else 'FAIL'}] Redis keys set correctly")
        
        # Test clearing virtual time
        print("\n3. Clearing virtual time...")
        clear_virtual_time()
        
        enabled = r.get("system:virtual_time:enabled")
        print(f"   Enabled flag after clear: {enabled}")
        print(f"   [{'PASS' if not enabled or enabled == b'0' else 'FAIL'}] Virtual time disabled in Redis")
        
        return True
        
    except Exception as e:
        print(f"   [FAIL] Redis sync test failed: {e}")
        print("   Note: This test requires Redis to be running")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TIME SYNCHRONIZATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("TimeService", test_time_service()))
    results.append(("Market Hours with Virtual Time", test_market_hours_with_virtual_time()))
    results.append(("Orchestrator Integration", test_orchestrator_market_hours_check()))
    results.append(("Redis Synchronization", test_redis_time_sync()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print()
    
    sys.exit(0 if passed == total else 1)

