import json
from datetime import datetime, timedelta

import pytest


class FakeRedis:
    def __init__(self, data):
        self._data = data

    def get(self, key):
        return self._data.get(key)

    def keys(self, pattern):
        prefix = pattern.split('*')[0]
        return [k for k in self._data.keys() if k.startswith(prefix)]


class FakeMarketMemory:
    def __init__(self, redis_data):
        self._redis_available = True
        self.redis_client = FakeRedis(redis_data)


@pytest.fixture
def app_client(monkeypatch):
    import dashboard.app as appmod

    class S:
        instrument_symbol = "NIFTY BANK"

    monkeypatch.setattr(appmod, "settings", S(), raising=False)

    now = datetime.now()
    recent = now - timedelta(seconds=60)
    instrument_key = "NIFTYBANK"
    tick_key = f"tick:{instrument_key}:{recent.isoformat()}"
    redis_data = {
        f"price:{instrument_key}:latest_ts": recent.isoformat(),
        tick_key: json.dumps({
            "timestamp": recent.isoformat(),
            "last_price": 60500,
            "depth": {"buy": [{"price": 60490, "quantity": 100}], "sell": [{"price": 60510, "quantity": 120}]}
        }),
    }
    monkeypatch.setattr(appmod, "marketmemory", FakeMarketMemory(redis_data), raising=False)

    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi.testclient unavailable")
    return TestClient(appmod.app)


def test_health_reports_ok_when_fresh(app_client):
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("ltp_fresh") is True
    assert data.get("depth_recent") is True
