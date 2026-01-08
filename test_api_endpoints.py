#!/usr/bin/env python3
"""
Test script to verify market data APIs work with historical replay.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add paths
sys.path.insert(0, './market_data/src')

from market_data.api import build_store, build_historical_replay
from market_data.api_service import (
    health_check, get_latest_tick, get_ohlc, get_price_data,
    get_raw_market_data, get_default_raw_market_data,
    get_market_depth, get_default_market_depth, get_store
)

async def test_apis():
    """Start historical replay and test API functions directly."""
    print("Starting market data API verification...")
    print("=" * 50)

    # Build store
    store = build_store()
    print("✓ Store created")

    # Mock the API service to use our test store instead of Redis
    import market_data.api_service
    original_get_store = market_data.api_service.get_store
    market_data.api_service.get_store = lambda: store
    market_data.api_service._store = store  # Also set the global variable

    # Start historical replay from 2026-01-07 09:15
    start_date = datetime(2026, 1, 7, 9, 15, 0)
    replay = build_historical_replay(store, data_source="synthetic", start_date=start_date)
    replay.speed_multiplier = 10.0  # Speed up for testing
    replay.start()
    print(f"✓ Historical replay started from {start_date}")

    # Wait for some data to be generated
    await asyncio.sleep(2.0)

    # Test API functions directly
    print("\nTesting API functions:")
    print("-" * 30)

    try:
        # Health check
        health = await health_check()
        print(f"✓ Health: {health.status}, Module: {health.module}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")

    try:
        # Market tick
        tick = await get_latest_tick("BANKNIFTY")
        print(f"✓ Market tick: {tick.instrument} @ {tick.last_price}")
    except Exception as e:
        print(f"✗ Market tick failed: {e}")

    try:
        # OHLC data
        ohlc = await get_ohlc("BANKNIFTY", timeframe="1min", limit=5)
        print(f"✓ OHLC data: {len(ohlc)} bars")
    except Exception as e:
        print(f"✗ OHLC data failed: {e}")

    try:
        # Price data
        price = await get_price_data("BANKNIFTY")
        print(f"✓ Price data: {price}")
    except Exception as e:
        print(f"✗ Price data failed: {e}")

    try:
        # Raw market data
        raw = await get_raw_market_data("BANKNIFTY", limit=10)
        print(f"✓ Raw market data: {raw['keys_found']} keys found")
    except Exception as e:
        print(f"✗ Raw market data failed: {e}")

    try:
        # Default raw market data
        raw_default = await get_default_raw_market_data(limit=10)
        print(f"✓ Default raw market data: {raw_default['keys_found']} keys found")
    except Exception as e:
        print(f"✗ Default raw market data failed: {e}")

    try:
        # Market depth
        depth = await get_market_depth("BANKNIFTY")
        print(f"✓ Market depth: {len(depth.get('buy', []))} bids, {len(depth.get('sell', []))} asks")
    except Exception as e:
        print(f"✗ Market depth failed: {e}")

    try:
        # Default market depth
        depth_default = await get_default_market_depth()
        print(f"✓ Default market depth: {len(depth_default.get('buy', []))} bids, {len(depth_default.get('sell', []))} asks")
    except Exception as e:
        print(f"✗ Default market depth failed: {e}")

    # Stop replay
    replay.stop()
    print("\n✓ Historical replay stopped")

    # Restore original get_store function
    market_data.api_service.get_store = original_get_store
    market_data.api_service._store = None

    print("\nAPI verification complete!")

if __name__ == "__main__":
    asyncio.run(test_apis())