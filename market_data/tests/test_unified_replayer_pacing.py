from datetime import datetime, timedelta

from market_data.adapters.unified_replayer import UnifiedHistoricalReplayer
from market_data.store import InMemoryMarketStore


class _FakeKite:
    def instruments(self, exchange):
        if exchange == "NSE":
            return [{"tradingsymbol": "NIFTYBANK", "name": "NIFTY BANK", "instrument_token": 260105}]
        return []

    def historical_data(self, instrument_token, from_date, to_date, interval, continuous=False, oi=True):
        base = datetime(2026, 2, 11, 9, 15)
        return [
            {
                "date": base,
                "open": 50000,
                "high": 50010,
                "low": 49990,
                "close": 50005,
                "volume": 100,
            },
            {
                "date": base + timedelta(minutes=1),
                "open": 50005,
                "high": 50020,
                "low": 50000,
                "close": 50015,
                "volume": 120,
            },
        ]


def test_zerodha_load_events_uses_points_mode_for_paced_replay():
    store = InMemoryMarketStore()
    replayer = UnifiedHistoricalReplayer(
        store=store,
        data_source="zerodha",
        speed=1.0,
        kite=_FakeKite(),
        instrument_symbol="NIFTY BANK",
        from_date=datetime(2026, 2, 11).date(),
        to_date=datetime(2026, 2, 11).date(),
        interval="minute",
    )

    mode, payload = replayer._load_events()

    assert mode == "points"
    assert len(payload) == 2

    # Loading should not eagerly write bars/ticks before replay loop runs
    assert list(store.get_ohlc("NIFTYBANK", "1min", limit=10)) == []
    assert store.get_latest_tick("NIFTYBANK") is None
