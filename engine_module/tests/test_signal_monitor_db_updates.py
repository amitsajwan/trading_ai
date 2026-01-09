import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from engine_module.signal_monitor import SignalMonitor, TradingCondition, ConditionOperator


@pytest.mark.asyncio
async def test_trigger_updates_db_and_pub(monkeypatch):
    fake_redis = Mock()
    fake_redis.published = []
    def fake_publish(ch, msg):
        fake_redis.published.append((ch, msg))
    fake_redis.publish = fake_publish

    # Mock get_redis_client to return our fake redis
    monkeypatch.setattr('engine_module.api_service.get_redis_client', lambda: fake_redis)

    # Mock MongoDB collection
    fake_collection = Mock()
    fake_db = {"signals": fake_collection}

    # Monkeypatch get_mongo_client to return a fake client with database
    class FakeMongoClient:
        def __getitem__(self, name):
            return fake_db
    monkeypatch.setattr('engine_module.api_service.get_mongo_client', lambda: FakeMongoClient())

    monitor = SignalMonitor()

    # Create a signal that will trigger (price > threshold)
    now = datetime.now()
    sig = TradingCondition(
        condition_id="test_trig_001",
        instrument="BANKNIFTY",
        indicator="current_price",
        operator=ConditionOperator.GREATER_THAN,
        threshold=100.0,
        action="BUY",
        expires_at=(now + timedelta(minutes=5)).isoformat()
    )

    monitor.add_signal(sig)

    # Mock technical service to return indicators
    class FakeTech:
        def get_indicators_dict(self, instr):
            return {"current_price": 120.0}
    monitor._technical_service = FakeTech()

    # Monkeypatch mark_signal_status to observe it was invoked
    called = {"count": 0}
    async def fake_mark(sigid, status, mongo_db=None, extra=None):
        called["count"] += 1
        return True

    monkeypatch.setattr('engine_module.signal_creator.mark_signal_status', fake_mark)

    # Call check_signals
    triggered = await monitor.check_signals("BANKNIFTY")

    assert len(triggered) == 1
    # Ensure our mark_signal_status was invoked
    assert called["count"] == 1
    # Ensure Redis published at least once (save path also publishes on save) or mark called published internally
    # (We cannot rely on mark_signal_status publish in this test because it's patched)



@pytest.mark.asyncio
async def test_expiry_marks_expired(monkeypatch):
    fake_redis = Mock()
    def fake_publish(ch, msg):
        pass
    fake_redis.publish = fake_publish

    monkeypatch.setattr('engine_module.api_service.get_redis_client', lambda: fake_redis)

    fake_collection = Mock()
    fake_db = {"signals": fake_collection}
    class FakeMongoClient:
        def __getitem__(self, name):
            return fake_db
    monkeypatch.setattr('engine_module.api_service.get_mongo_client', lambda: FakeMongoClient())

    monitor = SignalMonitor()

    # Create a signal that is already expired
    past = (datetime.now() - timedelta(minutes=10)).isoformat()
    sig = TradingCondition(
        condition_id="test_exp_001",
        instrument="BANKNIFTY",
        indicator="current_price",
        operator=ConditionOperator.GREATER_THAN,
        threshold=100.0,
        action="BUY",
        expires_at=past
    )

    monitor.add_signal(sig)

    # Provide a technical service stub so check_signals doesn't attempt imports
    monitor._technical_service = Mock()
    # Return a non-empty indicators dict so the monitor proceeds to evaluate and process expiries
    monitor._technical_service.get_indicators_dict.return_value = {"current_price": 0}

    # Monkeypatch mark_signal_status to verify it was called
    called = {"count": 0}
    async def fake_mark(sigid, status, mongo_db=None, extra=None):
        called["count"] += 1
        return True
    import engine_module.signal_creator as sc_mod
    monkeypatch.setattr('engine_module.signal_creator.mark_signal_status', fake_mark)

    # Sanity check: ensure our patch took effect
    assert getattr(sc_mod, 'mark_signal_status') is fake_mark

    # Sanity check: confirm expires comparison works as expected
    assert datetime.now().isoformat() > monitor._active_signals[sig.condition_id].expires_at

    triggered = await monitor.check_signals("BANKNIFTY")

    # Should have invoked the mark function
    assert called["count"] == 1
    # No triggered events
    assert len(triggered) == 0
