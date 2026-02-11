#!/usr/bin/env python3
"""Test MockKiteTicker directly."""

import sys
import os
import time

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'market_data', 'src'))

# Import
import importlib.util
spec = importlib.util.spec_from_file_location("mock_kite_websocket", os.path.join(os.path.dirname(__file__), 'market_data', 'src', 'market_data', 'sources', 'mock_kite_websocket.py'))
mock_kite_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock_kite_module)
MockKiteTicker = mock_kite_module.MockKiteTicker

def test_callback(ws, ticks):
    print(f"✅ CALLBACK CALLED: {len(ticks)} ticks")
    for tick in ticks:
        print(f"  Tick: {tick['instrument_token']} @ {tick['last_price']}")

print("Creating MockKiteTicker...")
ticker = MockKiteTicker(tick_interval=0.5)

print("Setting callback...")
ticker.on_ticks = test_callback

print("Subscribing...")
ticker.subscribe([256265])

print("Connecting...")
ticker.connect(threaded=True)

print("Waiting 3 seconds...")
time.sleep(3)

print("Closing...")
ticker.close()

print("Test complete.")