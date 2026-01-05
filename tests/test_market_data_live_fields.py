import json
from datetime import datetime, timedelta

import pytest


class FakeRedis:
    def __init__(self, data):
        self._data = data

    def get(self, key):
        return self._data.get(key)

    def keys(self, pattern):
        # naive: return all keys matching prefix before '*'
        prefix = pattern.split('*')[0]
        return [k for k in self._data.keys() if k.startswith(prefix)]


class FakeMarketMemory:
    def __init__(self, redis_data):
        self._redis_available = True
        self.redis_client = FakeRedis(redis_data)

    def get_current_price(self, instrument):
        return 60500.0


@pytest.fixture
def app_client(monkeypatch):
    import dashboard.app as appmod

    # Force instrument symbol
    class S:
        instrument_symbol = "NIFTY BANK"
        mongodb_db_name = "test"

    monkeypatch.setattr(appmod, "settings", S(), raising=False)

    # Seed Redis keys for live volume/vwap and minimal tick for fallback
    now = datetime.now()
    instrument_key = "NIFTYBANK"  # NIFTY BANK -> NIFTYBANK
    redis_data = {
        f"price:{instrument_key}:latest_ts": now.isoformat(),
        f"volume:{instrument_key}:latest": "123456",
        f"vwap:{instrument_key}:latest": "60420.5",
        f"tick:{instrument_key}:{now.isoformat()}": json.dumps({
            "timestamp": now.isoformat(),
            "last_price": 60500,
        }),
    }
    monkeypatch.setattr(appmod, "marketmemory", FakeMarketMemory(redis_data), raising=False)

    # Avoid DB usages
    def _db_raise():
        raise RuntimeError("db off")

    monkeypatch.setattr(appmod, "_safe_db", _db_raise, raising=True)

    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi.testclient unavailable")
    return TestClient(appmod.app)


def test_market_data_uses_live_volume_vwap(app_client):
    resp = app_client.get("/api/market-data")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("currentprice") == 60500.0
    assert data.get("volume24h") == 123456.0
    assert data.get("vwap") == 60420.5
