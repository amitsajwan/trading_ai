"""Integration test for Redis store roundtrip."""
import os
import pytest
from datetime import datetime, timezone

from data_niftybank.api import build_store
from data_niftybank.contracts import MarketTick, OHLCBar


def _get_redis_client():
    """Get Redis client if available (from env or default)."""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


@pytest.mark.integration
@pytest.mark.skipif(not _get_redis_client(), reason="Redis not available")
def test_redis_store_tick_roundtrip():
    """Integration test: tick storage and retrieval via Redis."""
    client = _get_redis_client()
    store = build_store(redis_client=client)
    
    tick = MarketTick(
        instrument="BANKNIFTY",
        timestamp=datetime.now(timezone.utc),
        last_price=45123.50,
        volume=1000,
    )
    
    store.store_tick(tick)
    
    latest = store.get_latest_tick("BANKNIFTY")
    
    assert latest is not None
    assert latest.instrument == "BANKNIFTY"
    assert latest.last_price == pytest.approx(45123.50)
    assert latest.volume == 1000


@pytest.mark.integration
@pytest.mark.skipif(not _get_redis_client(), reason="Redis not available")
def test_redis_store_ohlc_roundtrip():
    """Integration test: OHLC storage and retrieval via Redis."""
    client = _get_redis_client()
    store = build_store(redis_client=client)
    
    bar = OHLCBar(
        instrument="BANKNIFTY",
        timeframe="1m",
        open=45000,
        high=45100,
        low=44950,
        close=45050,
        volume=500,
        start_at=datetime.now(timezone.utc),
    )
    
    store.store_ohlc(bar)
    
    bars = list(store.get_ohlc("BANKNIFTY", "1m", limit=1))
    
    assert len(bars) >= 1
    latest_bar = bars[-1]
    assert latest_bar.instrument == "BANKNIFTY"
    assert latest_bar.close == pytest.approx(45050)
    assert latest_bar.volume == 500
