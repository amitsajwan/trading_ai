import os
import time
import pytest
import redis

from config import get_config


def redis_available(cfg):
    try:
        r = redis.Redis(**cfg.get_redis_config())
        r.ping()
        return True
    except Exception:
        return False


def test_collectors_write_keys_with_synthetic_fallback(monkeypatch):
    """Ensure LTP and Depth collectors work with synthetic fallback when no provider available."""
    # Mock ZerodhaProvider.from_credentials_file to return None (no credentials)
    from market_data.providers.zerodha import ZerodhaProvider
    monkeypatch.setattr(ZerodhaProvider, 'from_credentials_file', lambda: None)

    # Build provider via factory - should return None
    from market_data.providers.factory import get_provider
    provider = get_provider()
    assert provider is None  # No provider available

    cfg = get_config()
    if not redis_available(cfg):
        pytest.skip("Redis not available for integration test")

    r = redis.Redis(**cfg.get_redis_config())

    # LTP collector - should use synthetic fallback when kite=None
    from market_data.collectors.ltp_collector import LTPDataCollector, build_kite_client
    p = build_kite_client()
    assert p is None  # No provider available

    ltp_collector = LTPDataCollector(p, market_memory=None)
    ltp_collector.collect_once()

    price_key = cfg.redis_price_key
    last_price = r.get(f"{price_key}:last_price")
    latest_ts = r.get(f"{price_key}:latest_ts")
    quote = r.get(f"{price_key}:quote")

    assert last_price is not None
    assert latest_ts is not None
    assert quote is not None

    # Depth collector
    from market_data.collectors.depth_collector import DepthCollector
    depth_collector = DepthCollector(kite=p, redis_client=r)
    depth_collector.collect_once()

    # Use the collector's computed key (collector may use different default symbol than config)
    depth_key = f"depth:{depth_collector.key}"
    buy = r.get(f"{depth_key}:buy")
    sell = r.get(f"{depth_key}:sell")
    ts = r.get(f"{depth_key}:timestamp")

    assert buy is not None
    assert sell is not None
    assert ts is not None

    # Clean up keys (best effort)
    try:
        r.delete(f"{price_key}:last_price")
        r.delete(f"{price_key}:latest_ts")
        r.delete(f"{price_key}:quote")
        r.delete(f"{depth_key}:buy")
        r.delete(f"{depth_key}:sell")
        r.delete(f"{depth_key}:timestamp")
        r.delete(f"{depth_key}:total_bid_qty")
        r.delete(f"{depth_key}:total_ask_qty")
    except Exception:
        pass
