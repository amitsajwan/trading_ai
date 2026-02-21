import json
from datetime import datetime, timedelta

from market_data.technical_indicators_service import (
    TechnicalIndicators,
    TechnicalIndicatorsService,
)


class _FakeRedis:
    def __init__(self):
        self.kv = {}
        self.published = []
        self.counters = {}

    def setex(self, key, ttl, value):
        self.kv[key] = str(value)

    def delete(self, key):
        self.kv.pop(key, None)

    def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def publish(self, channel, payload):
        self.published.append((channel, payload))


def _make_ohlc_rows(count=30, base=100.0):
    now = datetime.utcnow()
    rows = []
    for i in range(count):
        t = now - timedelta(minutes=(count - i))
        rows.append(
            {
                "timestamp": t.isoformat(),
                "open": base + i * 0.5,
                "high": base + i * 0.5 + 1.0,
                "low": base + i * 0.5 - 1.0,
                "close": base + i * 0.5 + 0.2,
                "volume": 1000 + i,
                "oi": 50000 + i * 10,
            }
        )
    return rows


def test_apply_derived_state_sets_rsi_volatility_and_levels():
    svc = TechnicalIndicatorsService()
    ti = TechnicalIndicators(
        timestamp=datetime.utcnow().isoformat(),
        instrument="BANKNIFTY",
        current_price=100.0,
    )
    ti.rsi_14 = 75.0
    ti.atr_14 = 0.1
    ti.pivot_s1 = 98.0
    ti.pivot_r1 = 102.0

    svc._apply_derived_state(ti, current_price=100.0)

    assert ti.rsi_status == "OVERBOUGHT"
    assert ti.volatility_level == "LOW"
    assert ti.support_level == 98.0
    assert ti.resistance_level == 102.0


def test_calculate_indicators_publishes_batch_recalculate_metadata():
    fake = _FakeRedis()
    svc = TechnicalIndicatorsService(redis_client=fake)
    svc.initialize_with_ohlc_data("BANKNIFTY", _make_ohlc_rows(35, base=45000.0))

    _ = svc.calculate_indicators("BANKNIFTY")

    assert fake.published, "expected at least one publish"
    _, raw = fake.published[-1]
    envelope = json.loads(raw)
    payload = envelope.get("payload", {})
    assert envelope.get("stream") == "Y2"
    assert payload.get("update_type") == "batch_recalculate"
    assert payload.get("indicator_update_type") == "batch_recalculate"
    assert payload.get("indicator_stream") == "Y2"
    assert payload.get("source") == "calculate_indicators"


def test_update_candle_publishes_candle_metadata():
    fake = _FakeRedis()
    svc = TechnicalIndicatorsService(redis_client=fake)
    for row in _make_ohlc_rows(30, base=45000.0):
        candle = {
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "oi": row["oi"],
            "start_at": row["timestamp"],
            "timestamp": row["timestamp"],
        }
        svc.update_candle("BANKNIFTY", candle)

    _, raw = fake.published[-1]
    envelope = json.loads(raw)
    payload = envelope.get("payload", {})
    assert envelope.get("stream") == "Y2"
    assert payload.get("update_type") == "candle"
    assert payload.get("indicator_update_type") == "candle"
    assert payload.get("indicator_stream") == "Y2"
    assert payload.get("source") == "candle"

