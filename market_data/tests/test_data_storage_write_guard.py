import redis
import json
from market_data.data_storage_manager import DataStorageManager
from market_data.env_settings import redis_config

try:
    from redis_key_manager import get_redis_key
except Exception:
    def get_redis_key(key: str, *args, **kwargs):
        return key


def test_store_ohlc_bar_adds_metadata_and_sorted_set(tmp_path):
    redis_cfg = redis_config(decode_responses=True)
    redis_host = redis_cfg["host"]
    redis_port = redis_cfg["port"]
    r = redis.Redis(**redis_cfg)
    try:
        r.ping()
    except Exception:
        import pytest
        pytest.skip(f"redis on {redis_host}:{redis_port} is not available")
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
    sorted_key = f"ohlc_sorted:{instrument}:{timeframe}"
    mode_sorted_key = get_redis_key(sorted_key)
    r.delete(sorted_key)
    if mode_sorted_key != sorted_key:
        r.delete(mode_sorted_key)

    keys = r.keys(f"ohlc:{instrument}:{timeframe}:*")
    for k in keys:
        r.delete(k)

    success = mgr.store_ohlc_bar(instrument, timeframe, bar, use_sorted_sets=True)
    assert success

    # Check sorted set populated
    count = r.zcount(mode_sorted_key, '-inf', '+inf')
    if int(count) == 0 and mode_sorted_key != sorted_key:
        count = r.zcount(sorted_key, '-inf', '+inf')
    assert int(count) >= 1

    # Check entry contains metadata
    results = r.zrange(mode_sorted_key, -5, -1)
    if not results and mode_sorted_key != sorted_key:
        results = r.zrange(sorted_key, -5, -1)
    found = False
    for entry in results:
        data = json.loads(entry)
        if data.get('timestamp') == bar['timestamp'] and data.get('_format_version') == '2.0':
            found = True
            assert '_stored_by' in data
            assert '_stored_at' in data
    assert found
