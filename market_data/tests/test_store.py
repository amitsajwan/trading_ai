from datetime import datetime, timedelta, timezone

from market_data.contracts import MarketTick, OHLCBar
from market_data.store import InMemoryMarketStore


def test_store_tick_and_get_latest():
    store = InMemoryMarketStore()
    tick = MarketTick(
        instrument="BANKNIFTY",
        timestamp=datetime.now(timezone.utc),
        last_price=45000.0,
        volume=25,
    )

    store.store_tick(tick)

    latest = store.get_latest_tick("BANKNIFTY")
    assert latest is tick
    assert latest.last_price == 45000.0


def test_store_ohlc_respects_limit():
    store = InMemoryMarketStore(max_bars=2)
    base_time = datetime.now(timezone.utc)
    bars = [
        OHLCBar("BANKNIFTY", "1m", 1, 2, 0.5, 1.5, 10, base_time),
        OHLCBar("BANKNIFTY", "1m", 2, 3, 1.5, 2.5, 20, base_time + timedelta(minutes=1)),
        OHLCBar("BANKNIFTY", "1m", 3, 4, 2.5, 3.5, 30, base_time + timedelta(minutes=2)),
    ]

    for bar in bars:
        store.store_ohlc(bar)

    result = list(store.get_ohlc("BANKNIFTY", "1m"))
    assert len(result) == 2
    assert result[0] is bars[1]
    assert result[1] is bars[2]

