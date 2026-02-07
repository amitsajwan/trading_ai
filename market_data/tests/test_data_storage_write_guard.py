import redis
import json
import os
from market_data.data_storage_manager import DataStorageManager


def test_store_ohlc_bar_adds_metadata_and_sorted_set(tmp_path):
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    mgr = DataStorageManager(r)

    instrument = 'TEST_INSTR'
    timeframe = '1min'
    bar = {
        'timestamp': '2026-01-24T10:00:00+00:00',
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.5,
    }

    # Ensure clean state
    r.delete(f"ohlc_sorted:{instrument}:{timeframe}")
    keys = r.keys(f"ohlc:{instrument}:{timeframe}:*")
    for k in keys:
        r.delete(k)

    success = mgr.store_ohlc_bar(instrument, timeframe, bar, use_sorted_sets=True)
    assert success

    # Check sorted set populated
    count = r.zcount(f"ohlc_sorted:{instrument}:{timeframe}", '-inf', '+inf')
    assert int(count) >= 1

    # Check entry contains metadata
    results = r.zrange(f"ohlc_sorted:{instrument}:{timeframe}", -5, -1)
    found = False
    for entry in results:
        data = json.loads(entry)
        if data.get('timestamp') == bar['timestamp'] and data.get('_format_version') == '2.0':
            found = True
            assert '_stored_by' in data
            assert '_stored_at' in data
    assert found
