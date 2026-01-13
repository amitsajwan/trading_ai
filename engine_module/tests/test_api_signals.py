import pytest
from unittest.mock import Mock
from datetime import datetime

from engine_module.api_service import get_signals


class FakeMongo:
    def __init__(self, docs):
        self._docs = docs
    def __getitem__(self, name):
        return self
    def find(self, q):
        return self
    def sort(self, *args, **kwargs):
        # ignore sort args and return self for chaining
        return self
    def limit(self, n):
        return self._docs


def test_get_signals_returns_metadata(monkeypatch):
    now = datetime.now().isoformat()
    doc = {
        "_id": "oid123",
        "condition_id": "cond123",
        "instrument": "BANKNIFTY",
        "action": "BUY",
        "confidence": 0.6,
        "entry_price": 45200.0,
        "execution_mode": "CONDITIONAL",
        "parsed_conditions": [{"indicator": "rsi_14", "operator": ">", "threshold": 30}],
        "reason_hash": "abc123",
        "indicator": "rsi_14",
        "threshold": 30.0,
        "additional_conditions": [],
        "status": "pending",
        "metadata": {"signal_source": "orchestrator_decision"},
        "created_at": now
    }

    fake_db = FakeMongo([doc])

    def fake_get_mongo_client():
        return {"zerodha_trading": fake_db}

    monkeypatch.setattr('engine_module.api_service.get_mongo_client', lambda: fake_get_mongo_client())

    res = pytest.run(asyncio=True) if False else None
    # Call the coroutine directly
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    signals = loop.run_until_complete(get_signals('BANKNIFTY', limit=10))

    assert len(signals) == 1
    s = signals[0]
    assert s.entry_price == 45200.0
    assert s.execution_mode == 'CONDITIONAL'
    assert s.parsed_conditions[0]['indicator'] == 'rsi_14'
    assert s.reason_hash == 'abc123'
    assert s.indicator == 'rsi_14'
    assert s.threshold == 30.0
    assert s.status == 'pending'
    assert isinstance(s.metadata, dict)
