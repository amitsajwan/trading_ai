import json
import pytest

from types import SimpleNamespace

from user_module.api import execute_user_trade


class FakeRedis:
    def __init__(self):
        self.published = []

    def publish(self, channel, message):
        self.published.append((channel, message))


class FakeTradeStore:
    def __init__(self):
        self.recorded = []

    async def record_trade(self, trade):
        self.recorded.append(trade)
        return True


class FakePortfolioStore:
    async def get_positions(self, user_id):
        return [SimpleNamespace(instrument='TEST:1234', side='BUY', quantity=1, entry_price=100)]


class FakeComponents(dict):
    def __init__(self):
        super().__init__()
        self['trade_store'] = FakeTradeStore()
        self['portfolio_store'] = FakePortfolioStore()


@pytest.mark.asyncio
async def test_execute_user_trade_publishes(monkeypatch):
    fake_redis = FakeRedis()

    def fake_get_redis_client():
        return fake_redis

    # Prepare fake components returned by build_user_module
    class FakeExecutor:
        async def execute_trade(self, trade_request):
            return SimpleNamespace(success=True, trade_id='t1', order_id='o1', executed_price=100)

    class FakeRiskManager:
        async def validate_trade_risk(self, user_id, trade_request):
            return {"approved": True, "reasons": []}

    def fake_build_user_module(mongo_client):
        return {
            'trade_store': FakeTradeStore(),
            'portfolio_store': FakePortfolioStore(),
            'portfolio_risk_manager': FakeRiskManager(),
            'trade_executor': FakeExecutor(),
        }

    monkeypatch.setattr('user_module.api.build_user_module', fake_build_user_module)

    import sys, types
    fake_module = types.SimpleNamespace(get_redis_client=fake_get_redis_client)
    sys.modules['engine_module.api_service'] = fake_module

    # Call execute_user_trade with minimal args and ensure publish occurred
    res = await execute_user_trade(None, 'user1', 'TEST:1234', 'BUY', 1)

    assert res.success, 'Trade execution expected to succeed in test environment'

    # Ensure fake redis got published messages
    assert any(ch.startswith('engine:trade') for ch, _ in fake_redis.published), f"No publish found, published={fake_redis.published}"
    payloads = [json.loads(msg) for _, msg in fake_redis.published]
    assert payloads and 'trade_executed' in payloads[0]
