import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import user_module.api_service as ua
from user_module.api_service import app as user_app
from user_module.api import TradeExecutionResult


@pytest.mark.asyncio
async def test_user_execute_endpoint_includes_signal_id(monkeypatch):
    # Patch execute_user_trade to avoid DB/risk calls and return success
    async def fake_execute_user_trade(*args, **kwargs):
        return TradeExecutionResult(success=True, trade_id="t1", order_id="o1", executed_price=100.0)

    monkeypatch.setattr('user_module.api.execute_user_trade', fake_execute_user_trade)

    # Ensure user_components exist so endpoint doesn't reject
    from types import SimpleNamespace
    ua.user_components = {"user_store": SimpleNamespace(db=SimpleNamespace(client=None))}

    transport = ASGITransport(app=user_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "user_id": "default_user",
            "instrument": "BANKNIFTY",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "signal_id": "sig_unit_123"
        }
        resp = await client.post("/api/trading/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("signal_id") == "sig_unit_123"
