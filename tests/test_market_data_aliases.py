import json
from datetime import datetime
import pytest


class FakeRedis:
    def __init__(self, data):
        self._data = data

    def get(self, key):
        return self._data.get(key)


class FakeMarketMemory:
    def __init__(self, data):
        self._redis_available = True
        self.redis_client = FakeRedis(data)

    def get_current_price(self, instrument):
        return 60500.0


@pytest.fixture
def app_client(monkeypatch):
    import dashboard.app as appmod

    class S:
        instrument_symbol = "NIFTY BANK"
        mongodb_db_name = "test"
        market_24_7 = True

    monkeypatch.setattr(appmod, "settings", S(), raising=False)

    now = datetime.now()
    instrument_key = "NIFTYBANK"
    redis_data = {
        f"price:{instrument_key}:latest_ts": now.isoformat(),
        f"volume:{instrument_key}:latest": "123456",
        f"vwap:{instrument_key}:latest": "60420.5",
        f"oi:{instrument_key}:latest": "98765",
        f"tick:{instrument_key}:{now.isoformat()}": json.dumps({
            "timestamp": now.isoformat(),
            "last_price": 60500,
        }),
    }
    monkeypatch.setattr(appmod, "marketmemory", FakeMarketMemory(redis_data), raising=False)

    def _db_raise():
        raise RuntimeError("db off")

    monkeypatch.setattr(appmod, "_safe_db", _db_raise, raising=True)

    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi.testclient unavailable")
    return TestClient(appmod.app)


def test_aliases_present_and_equal(app_client):
    resp = app_client.get("/api/market-data")
    assert resp.status_code == 200
    data = resp.json()

    # Base + aliases should exist and be equal
    assert data["current_price"] == data["currentPrice"] == data["currentprice"] == 60500.0
    assert data["volume_24h"] == data["volume24h"] == 123456.0
    assert data["vwap"] == 60420.5

    fut = data.get("futures", {})
    assert fut["oi"] == 98765.0
    # average_price aliases
    assert fut["average_price"] == fut["averagePrice"] == fut["averageprice"] == 60420.5


def test_data_source_redis_when_live_price(app_client):
    resp = app_client.get("/api/market-data")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_source"] == "Redis"
