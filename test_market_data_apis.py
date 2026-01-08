#!/usr/bin/env python3
"""
Test script to start historical replay from 2026-01-07 09:15 and verify APIs.
"""

import asyncio
import time
from datetime import datetime
import sys
import os

# Add paths
sys.path.insert(0, './market_data/src')
sys.path.insert(0, './news_module/src')

from market_data.api import build_store, build_historical_replay

async def test_apis():
    """Start historical replay and test APIs."""
    print("Starting market data verification...")
    print("=" * 50)

    # Build store
    store = build_store()
    print("✓ Store created")

    # Start historical replay from 2026-01-07 09:15
    start_date = datetime(2026, 1, 7, 9, 15, 0)
    replay = build_historical_replay(store, data_source="synthetic", start_date=start_date)
    replay.speed_multiplier = 10.0  # Speed up for testing
    replay.start()
    print(f"✓ Historical replay started from {start_date}")

    # Wait for some data to be generated
    await asyncio.sleep(1.0)

    # Test store has data
    latest_tick = store.get_latest_tick("BANKNIFTY")
    if latest_tick:
        print(f"✓ Latest tick: {latest_tick.instrument} @ {latest_tick.last_price}")
    else:
        print("✗ No tick data found")

    # Test OHLC data
    ohlc_bars = list(store.get_ohlc("BANKNIFTY", "1min", limit=5))
    if ohlc_bars:
        print(f"✓ OHLC bars: {len(ohlc_bars)} bars")
        for bar in ohlc_bars[:2]:
            print(f"  {bar.start_at}: O={bar.open:.2f} H={bar.high:.2f} L={bar.low:.2f} C={bar.close:.2f} V={bar.volume}")
    else:
        print("✗ No OHLC data found")

    # Stop replay
    replay.stop()
    print("✓ Historical replay stopped")

    print("\nAPI verification complete!")

if __name__ == "__main__":
    asyncio.run(test_apis())