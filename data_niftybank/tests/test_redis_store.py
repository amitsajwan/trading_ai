from datetime import datetime, timedelta, timezone

import pytest

from data_niftybank.contracts import MarketTick, OHLCBar
from data_niftybank.adapters.redis_store import RedisMarketStore


class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.zsets = {}

    def ping(self):
        return True

    def setex(self, key, ttl, value):  # noqa: ARG002
        self.kv[key] = value

    def get(self, key):
        return self.kv.get(key)

    def zadd(self, key, mapping):
        entries = self.zsets.setdefault(key, [])
        for member, score in mapping.items():
            entries.append((float(score), member))
        # Keep sorted by score
        entries.sort(key=lambda x: x[0])

    def zrange(self, key, start, end):
        entries = self.zsets.get(key, [])
        # Python slicing semantics with inclusive end similar to Redis end index
        if end == -1:
            slice_end = None
        else:
            slice_end = end + 1
        return [member for _, member in entries[start:slice_end]]

    def zremrangebyscore(self, key, min_score, max_score):
        entries = self.zsets.get(key, [])
        self.zsets[key] = [item for item in entries if not (min_score <= item[0] <= max_score)]


def test_store_and_get_latest_tick_roundtrip():
    redis = FakeRedis()
    store = RedisMarketStore(redis)
    tick = MarketTick(
        instrument="BANKNIFTY",
        timestamp=datetime.now(timezone.utc),
        last_price=45050.5,
        volume=10,
    )

    store.store_tick(tick)

    latest = store.get_latest_tick("BANKNIFTY")
    assert latest is not None
    assert latest.instrument == "BANKNIFTY"
    assert latest.last_price == pytest.approx(45050.5)
    assert redis.kv.get("price:BANKNIFTY:latest") == str(45050.5)


def test_store_ohlc_and_retrieve_sorted():
    redis = FakeRedis()
    store = RedisMarketStore(redis)
    base = datetime.now(timezone.utc)
    bars = [
        OHLCBar("BANKNIFTY", "1m", 1, 2, 0.5, 1.5, 10, base),
        OHLCBar("BANKNIFTY", "1m", 2, 3, 1.5, 2.5, 20, base + timedelta(minutes=1)),
        OHLCBar("BANKNIFTY", "1m", 3, 4, 2.5, 3.5, 30, base + timedelta(minutes=2)),
    ]

    for bar in bars:
        store.store_ohlc(bar)

    fetched = list(store.get_ohlc("BANKNIFTY", "1m", limit=2))
    # Should return the last two bars in time order
    assert len(fetched) == 2
    assert fetched[0].open == 2
    assert fetched[1].open == 3
