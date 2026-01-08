#!/usr/bin/env python3
"""Test trading system during market hours vs off-hours."""

import asyncio
import os
from datetime import datetime, time
from core_kernel.config.settings import settings

# Use centralized time service and market hours module
try:
    from core_kernel.src.core_kernel.time_service import now as get_system_time
    from core_kernel.src.core_kernel.market_hours import is_market_open
except ImportError:
    # Fallback for tests run outside Docker
    def get_system_time() -> datetime:
        return datetime.now()
    
    def is_market_open(now: datetime = None) -> bool:
        """Check if Indian equity market is currently open."""
        if now is None:
            now = datetime.now()
        
        # Market is only open Monday-Friday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:15 AM to 3:30 PM IST
        market_open = time(9, 15, 0)
        market_close = time(15, 30, 0)
        
        current_time = now.time()
        return market_open <= current_time < market_close  # < not <= (market closes AT 3:30)

def get_current_mode():
    """Get current testing mode based on market hours."""
    now = get_system_time()
    if is_market_open(now):
        return "LIVE_MARKET", "[OPEN] Real market data available"
    else:
        return "OFF_HOURS", "[CLOSED] Using stored/offline data only"

async def run_market_hours_test():
    """Run appropriate tests based on market hours."""

    mode, description = get_current_mode()
    now = get_system_time()  # Use system time (supports virtual time)
    
    # Check if using virtual time
    try:
        from core_kernel.src.core_kernel.time_service import is_virtual_time
        virtual = is_virtual_time()
    except ImportError:
        virtual = False

    print("=" * 60)
    print(f"MARKET HOURS TEST - {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 60)
    print(f"Time Mode: {'VIRTUAL (Replay)' if virtual else 'REAL-TIME (Live)'}")
    print(f"Mode: {mode}")
    print(f"Status: {description}")
    print()

    if mode == "LIVE_MARKET":
        print("[OPEN] MARKET IS OPEN - Running live data tests")
        print()

        # Test live data collection
        print("1. Testing live NIFTY data collection...")
        try:
            from market_data.api import build_store
            store = build_store()  # In-memory for testing

            # This would normally connect to live Kite API
            print("   [OK] Data store initialized")
            print("   [NOTE] Live Kite API requires valid credentials")

        except Exception as e:
            print(f"   [ERROR] {e}")

        print()
        print("2. Testing agent analysis with live data...")
        try:
            from scripts.utils.show_agent_output import client, db
            coll = client[db.name]["agent_decisions"]

            latest = coll.find_one(sort=[("timestamp", -1)])
            if latest:
                print(f"   [OK] Latest analysis found: {latest.get('timestamp')}")
                print(f"   [DATA] Signal: {latest.get('final_signal', 'N/A')}")
            else:
                print("   [WARN] No recent agent analysis found")

        except Exception as e:
            print(f"   [ERROR] {e}")

    else:
        print("[CLOSED] MARKET IS CLOSED - Running offline simulation")
        print()

        # Test offline/paper trading
        print("1. Testing offline data simulation...")
        try:
            from market_data.api import build_store
            store = build_store()  # In-memory store
            print("   [OK] Offline data store ready")
        except Exception as e:
            print(f"   [ERROR] {e}")

        print()
        print("2. Testing paper trading simulation...")
        try:
            from scripts.utils.paper_trading import PaperTrading

            # Create paper trading account with 5 lakh
            paper = PaperTrading(initial_capital=500000)

            # Simulate a small trade (within 5 lakh capital)
            result = paper.place_order(
                signal="BUY",
                quantity=10,  # NIFTY contracts (smaller position)
                price=22000,
                stop_loss=21800,
                take_profit=22400
            )

            if result["status"] == "COMPLETE":
                print("   [OK] Paper trade executed successfully")
                print(f"   [TRADE] Trade ID: {result['order_id']}")
                print(f"   [CAPITAL] Remaining Capital: ₹{paper.current_capital:,.0f}")
            else:
                print(f"   [REJECTED] Trade rejected: {result.get('reason', 'Unknown')}")

        except Exception as e:
            print(f"   [ERROR] {e}")

    print()
    print("=" * 60)
    print("RECOMMENDED TESTING APPROACH")
    print("=" * 60)

    if mode == "LIVE_MARKET":
        print("[OPEN] During market hours (9:15 AM - 3:30 PM IST, Mon-Fri):")
        print("   * Use docker-compose up for full live testing")
        print("   * Monitor real agent decisions: python scripts/utils/show_agent_output.py")
        print("   * Check live data feeds: docker logs zerodha-ltp-collector-nifty")
        print("   * Test with small paper trades only")
    else:
        print("[CLOSED] During off-hours:")
        print("   * Use offline testing: pytest data_niftybank/tests/")
        print("   * Test paper trading: python setup_paper_trading.py")
        print("   * Run agent simulations with mock data")
        print("   * Validate risk management logic")

    print()
    print("[QUICK] Quick Test Commands:")
    print("   * Paper trading setup: python setup_paper_trading.py")
    print("   * Run all tests: pytest")
    print("   * Start services: docker-compose -f docker-compose.data.yml up -d")

if __name__ == "__main__":
    asyncio.run(run_market_hours_test())

