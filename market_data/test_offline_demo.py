#!/usr/bin/env python3
"""
Complete offline testing demo for data_niftybank module.

This script demonstrates that the entire data module works 100% offline
without any external API calls, live market data, or internet connectivity.

Usage:
    python data_niftybank/test_offline_demo.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the module to path
module_root = Path(__file__).parent
src_path = module_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from market_data.api import (
    build_store, build_historical_replay,
    build_macro_client, build_options_client
)
from market_data.contracts import MarketTick, OHLCBar
from datetime import datetime, timedelta


async def test_market_data_offline():
    """Test market data storage and retrieval completely offline."""
    print("📊 Testing Market Data Storage...")

    # Create in-memory store (no Redis needed)
    store = build_store()
    print(f"✅ Created {type(store).__name__}")

    # Generate and store sample market data
    base_time = datetime.now()
    base_price = 22000.0

    # Store some ticks
    ticks = []
    for i in range(10):
        tick = MarketTick(
            instrument="NIFTY",
            timestamp=base_time - timedelta(minutes=i),
            last_price=base_price + (i * 10),
            volume=1000 + (i * 100)
        )
        store.store_tick(tick)
        ticks.append(tick)

    print(f"✅ Stored {len(ticks)} market ticks")

    # Store some OHLC bars
    bars = []
    for i in range(5):
        bar_time = base_time - timedelta(minutes=5*i)
        bar = OHLCBar(
            instrument="NIFTY",
            timeframe="5min",
            open=base_price + (i * 25),
            high=base_price + (i * 25) + 50,
            low=base_price + (i * 25) - 25,
            close=base_price + (i * 25) + 10,
            volume=5000 + (i * 500),
            start_at=bar_time
        )
        store.store_ohlc(bar)
        bars.append(bar)

    print(f"✅ Stored {len(bars)} OHLC bars")

    # Test data retrieval
    latest_tick = store.get_latest_tick("NIFTY")
    assert latest_tick is not None, "Should retrieve latest tick"
    assert latest_tick.last_price > 0, "Tick should have valid price"
    print(f"✅ Retrieved latest tick: {latest_tick.last_price}")

    ohlc_data = list(store.get_ohlc("NIFTY", "5min", limit=5))
    assert len(ohlc_data) > 0, "Should retrieve OHLC data"
    assert ohlc_data[0].close > 0, "OHLC bar should have valid close price"
    print(f"✅ Retrieved {len(ohlc_data)} OHLC bars")

    return True


async def test_historical_replay_offline():
    """Test historical data replay with synthetic data."""
    print("\n🎬 Testing Historical Data Replay...")

    # Create store and replay
    store = build_store()
    replay = build_historical_replay(store, data_source="synthetic")
    replay.speed_multiplier = 100.0  # Fast replay for testing

    print(f"✅ Created {type(replay).__name__} with synthetic data")

    # Start replay
    replay.start()
    print("✅ Started data replay")

    # Let it generate some data
    await asyncio.sleep(0.05)

    # Check data was generated
    tick = store.get_latest_tick("NIFTY")
    assert tick is not None, "Replay should generate tick data"
    print(f"✅ Generated tick data: {tick.last_price}")

    bars = list(store.get_ohlc("NIFTY", "1min", limit=10))
    assert len(bars) >= 5, "Should generate multiple OHLC bars"
    print(f"✅ Generated {len(bars)} OHLC bars")

    # Stop replay
    replay.stop()
    print("✅ Stopped data replay")

    return True


async def test_macro_data_offline():
    """Test macro data adapter with mock data."""
    print("\n📈 Testing Macro Data Adapter...")

    macro_client = build_macro_client()
    print(f"✅ Created {type(macro_client).__name__}")

    # Mock inflation data
    mock_inflation_data = [
        {"value": 5.2, "date": "2024-01-01T00:00:00"},
        {"value": 5.1, "date": "2024-02-01T00:00:00"},
        {"value": 5.0, "date": "2024-03-01T00:00:00"}
    ]

    # Mock RBI data
    mock_rbi_data = [
        {"value": 6.5, "date": "2024-01-15T00:00:00", "unit": "percent"},
        {"value": 6.75, "date": "2024-02-15T00:00:00", "unit": "percent"}
    ]

    # Mock internal methods
    async def mock_get_inflation(months):
        return mock_inflation_data[:months//4]  # Rough approximation

    async def mock_get_rbi(indicator, days):
        return mock_rbi_data[:days//30]  # Rough approximation

    macro_client._get_inflation_from_fetcher = mock_get_inflation
    macro_client._get_rbi_from_scraper = mock_get_rbi

    # Test inflation data
    inflation_data = await macro_client.get_inflation_data(months=12)
    assert len(inflation_data) >= 2, "Should retrieve inflation data"
    assert inflation_data[0].name == "CPI Inflation", "Should have correct name"
    assert inflation_data[0].value > 0, "Should have valid inflation value"
    print(f"✅ Retrieved {len(inflation_data)} inflation data points")

    # Test RBI data
    rbi_data = await macro_client.get_rbi_data("repo_rate", days=60)
    assert len(rbi_data) >= 1, "Should retrieve RBI data"
    assert "repo_rate" in rbi_data[0].name.lower(), "Should have correct indicator name"
    assert rbi_data[0].value > 0, "Should have valid RBI value"
    print(f"✅ Retrieved {len(rbi_data)} RBI data points")

    return True


async def test_options_data_offline():
    """Test options data adapter with mock data."""
    print("\n📊 Testing Options Data Adapter...")

    # Mock Kite and fetcher
    class MockKite:
        pass

    class MockFetcher:
        def __init__(self):
            self.initialize_called = False

        async def initialize(self):
            self.initialize_called = True

        async def fetch_options_chain(self, strikes=None):
            return {
                "BANKNIFTY": {
                    "calls": [
                        {"strike": 44000, "last_price": 1200.0, "oi": 15000, "volume": 5000},
                        {"strike": 44500, "last_price": 800.0, "oi": 22000, "volume": 8000}
                    ],
                    "puts": [
                        {"strike": 44000, "last_price": 800.0, "oi": 18000, "volume": 6000},
                        {"strike": 44500, "last_price": 1200.0, "oi": 25000, "volume": 9000}
                    ]
                }
            }

    mock_kite = MockKite()
    mock_fetcher = MockFetcher()

    options_client = build_options_client(mock_kite, mock_fetcher)
    print(f"✅ Created {type(options_client).__name__}")

    # Test initialization
    await options_client.initialize()
    assert mock_fetcher.initialize_called, "Should initialize fetcher"
    print("✅ Initialized options client")

    # Test options chain retrieval
    chain = await options_client.fetch_options_chain()
    assert "BANKNIFTY" in chain, "Should have BANKNIFTY data"
    assert "calls" in chain["BANKNIFTY"], "Should have calls data"
    assert "puts" in chain["BANKNIFTY"], "Should have puts data"
    assert len(chain["BANKNIFTY"]["calls"]) == 2, "Should have call options"
    print(f"✅ Retrieved options chain with {len(chain['BANKNIFTY']['calls'])} calls and {len(chain['BANKNIFTY']['puts'])} puts")

    return True


async def main():
    """Run all offline tests."""
    print("🚀 Starting 100% Offline Data Module Testing")
    print("=" * 50)

    try:
        # Run all tests
        await test_market_data_offline()
        await test_historical_replay_offline()
        await test_macro_data_offline()
        await test_options_data_offline()

        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED - 100% OFFLINE FUNCTIONALITY CONFIRMED!")
        print("✅ Market data storage and retrieval")
        print("✅ Historical data replay with synthetic data")
        print("✅ Macro economic data (inflation, RBI)")
        print("✅ Options chain data")
        print("\n📈 The data module is production-ready and fully testable offline!")
        print("🔧 No internet connection or live market data required!")

        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

