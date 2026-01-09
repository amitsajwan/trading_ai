import pytest
from unittest.mock import patch

# Local fake Redis to capture set/get and pubsub
class FakeRedis:
    def __init__(self):
        self.store = {}
        self.published = []

    def setex(self, key, ttl, value):
        self.store[key] = (value, ttl)

    def get(self, key):
        v = self.store.get(key)
        return v[0] if v else None

    def publish(self, channel, message):
        self.published.append((channel, message))


def test_cross_detection_uses_persisted_previous_value(monkeypatch):
    """Ensure CROSSES_ABOVE/BELOW reads previous value from Redis and updates it."""
    # Ensure project root is importable (tests may run with different cwd)
    import os, sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from engine_module.signal_monitor import SignalMonitor, TradingCondition, ConditionOperator

    fake_redis = FakeRedis()

    # Pre-seed previous value lower than threshold (e.g., RSI previously 29)
    fake_redis.setex("indicators_prev:BANKNIFTY:rsi_14", 3600, "29")
    print('DEBUG: fake_redis.store after seed=', fake_redis.store)

    # Monkeypatch get_redis_client to return our fake redis (api_service is the source)
    # Depending on import layout the function may live at `engine_module.api_service` or `engine_module.src.engine_module.api_service`.
    try:
        monkeypatch.setattr('engine_module.api_service.get_redis_client', lambda: fake_redis)
    except Exception:
        monkeypatch.setattr('engine_module.src.engine_module.api_service.get_redis_client', lambda: fake_redis)

    # Create monitor (it will call get_redis_client internally)
    monitor = SignalMonitor()
    print('DEBUG: fake_redis.store after monitor init=', fake_redis.store)
    print('DEBUG: monitor._redis_client repr=', repr(monitor._redis_client))
    print('DEBUG: monitor._redis_client is fake_redis?', monitor._redis_client is fake_redis)
    print('DEBUG: monitor._redis_client.store attr=', getattr(monitor._redis_client, 'store', None))

    # Create a condition that checks RSI crosses above 30
    cond = TradingCondition(
        condition_id="test_cross_001",
        instrument="BANKNIFTY",
        indicator="rsi_14",
        operator=ConditionOperator.CROSSES_ABOVE,
        threshold=30.0,
        action="BUY",
        position_size=1.0,
    )

    # Evaluate condition with current indicators (rsi now 31)
    indicators = {"rsi_14": 31.0}

    # Extra debug prints
    key = f"indicators_prev:{cond.instrument}:{cond.indicator}"
    print('DEBUG: pre-redis-get=', monitor._redis_client.get(key) if monitor._redis_client else None)
    print('DEBUG: cond.threshold=', cond.threshold)
    print('DEBUG: current value=', indicators.get(cond.indicator))

    result = monitor._evaluate_condition(cond, indicators)

    # Debugging prints to understand failure (if any)
    print('DEBUG: redis_store=', getattr(fake_redis, 'store', None))
    print('DEBUG: result=', result)

    assert result is True, f"Cross detection should trigger when previous (29) < 30 and current (31) > 30 (got {result})"

    # Ensure Redis was updated with the new previous value
    pv = fake_redis.get("indicators_prev:BANKNIFTY:rsi_14")
    assert float(pv) == 31.0


def test_technical_service_publishes_indicators(monkeypatch):
    """Ensure TechnicalIndicatorsService publishes to Redis after update_candle."""
    # Ensure project root is importable
    import os, sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    market_src_path = os.path.join(project_root, 'market_data', 'src')
    if market_src_path not in sys.path:
        sys.path.insert(0, market_src_path)

    from market_data.technical_indicators_service import TechnicalIndicatorsService

    fake_redis = FakeRedis()

    # Instantiate service with our fake redis
    svc = TechnicalIndicatorsService(redis_client=fake_redis)

    # Create a simple candle to trigger calculation/publish
    candle = {
        'start_at': '2026-01-09T10:00:00',
        'open': 45000.0,
        'high': 45100.0,
        'low': 44900.0,
        'close': 45050.0,
        'volume': 1000
    }

    # Call update_candle which should publish
    svc.update_candle('BANKNIFTY', candle)

    # Verify a publication was made to "indicators:BANKNIFTY"
    published = [p for p in fake_redis.published if p[0].startswith('indicators:BANKNIFTY')]
    assert len(published) == 1, "Should publish one indicators message"

    # Payload should contain rsi_14 or macd keys (or current_price)
    import json
    channel, message = published[0]
    payload = json.loads(message)
    assert 'instrument' in payload and payload['instrument'] == 'BANKNIFTY'
    assert 'rsi_14' in payload or 'current_price' in payload or 'macd_value' in payload
