import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from dashboard.app import app

client = TestClient(app)


def test_trading_cycle_and_signals():
    # Patch httpx.AsyncClient used by the trading router to return mocked responses
    from unittest.mock import patch

    class DummyClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, *args, **kwargs):
            class R:
                status_code = 200
                def json(self):
                    return {"decision": "BUY", "confidence": 0.8}
            return R()
        async def get(self, *args, **kwargs):
            class R:
                status_code = 200
                def __init__(self, payload):
                    self._payload = payload
                def json(self):
                    return self._payload

            # Inspect requested URL to return appropriate shape
            if args and isinstance(args[0], str) and "/by-id/" in args[0]:
                payload = {
                    "signal_id": "sig1",
                    "id": "sig1",
                    "condition_id": "sig1",
                    "instrument": "BANKNIFTY",
                    "action": "BUY",
                    "confidence": 0.8,
                    "reasoning": "RSI > 32",
                    "timestamp": "2026-01-09T10:00:00"
                }
                return R(payload)

            return R([{
                "signal_id": "sig1",
                "id": "sig1",
                "instrument": "BANKNIFTY",
                "action": "BUY",
                "confidence": 0.8,
                "reasoning": "RSI > 32",
                "timestamp": "2026-01-09T10:00:00"
            }])

    with patch('httpx.AsyncClient', return_value=DummyClient()):
        res = client.post("/api/trading/cycle")
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True

        res = client.get("/api/trading/signals")
        assert res.status_code == 200
        signals = res.json().get("signals")
        assert isinstance(signals, list)
        assert len(signals) >= 1


def test_trading_conditions_and_execute():
    # Patch httpx.AsyncClient used by the trading router and user module calls
    from unittest.mock import patch

    class DummyClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, *args, **kwargs):
            # Different endpoints are called; for analyze and execute, return success
            class R:
                status_code = 200
                def json(self):
                    return {"success": True, "decision": "BUY", "confidence": 0.8, "executed": True}
            return R()
        async def get(self, *args, **kwargs):
            class R:
                status_code = 200
                def __init__(self, payload):
                    self._payload = payload
                def json(self):
                    return self._payload

            if args and isinstance(args[0], str) and "/by-id/" in args[0]:
                payload = {
                    "signal_id": "sig1",
                    "id": "sig1",
                    "condition_id": "sig1",
                    "instrument": "BANKNIFTY",
                    "action": "BUY",
                    "confidence": 0.8,
                    "reasoning": "RSI > 32",
                    "timestamp": "2026-01-09T10:00:00"
                }
                return R(payload)

            # default list response
            return R([{
                "signal_id": "sig1",
                "id": "sig1",
                "condition_id": "sig1",
                "instrument": "BANKNIFTY",
                "action": "BUY",
                "confidence": 0.8,
                "reasoning": "RSI > 32",
                "timestamp": "2026-01-09T10:00:00"
            }])

    with patch('httpx.AsyncClient', return_value=DummyClient()):
        res = client.post("/api/trading/cycle")
        assert res.status_code == 200
        sigs = client.get("/api/trading/signals").json().get("signals")
        sid = sigs[-1].get("id")

        res = client.get(f"/api/trading/conditions/{sid}")
        assert res.status_code == 200
        cond = res.json()
        assert "conditions_met" in cond or "error" in cond

        res = client.post(f"/api/trading/execute/{sid}")
        assert res.status_code == 200
        exec_res = res.json()
        assert exec_res.get("success") is True


def test_execute_includes_signal_id():
    # Ensure dashboard forwards signal_id to user_module when executing
    from unittest.mock import patch

    posted = {"posts": []}

    class CapturingClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, *args, **kwargs):
            # Capture POST payloads
            posted["posts"].append({"url": args[0] if args else None, "json": kwargs.get("json"), "params": kwargs.get("params")})
            class R:
                status_code = 200
                def json(self):
                    return {"success": True, "trade_id": "t1", "order_id": "o1", "executed_price": 100.0}
            return R()
        async def get(self, *args, **kwargs):
            # Return a signal when asked by id
            class R:
                status_code = 200
                def __init__(self, payload):
                    self._payload = payload
                def json(self):
                    return self._payload
            if args and isinstance(args[0], str) and "/by-id/" in args[0]:
                payload = {
                    "signal_id": "sig1",
                    "id": "sig1",
                    "condition_id": "sig1",
                    "instrument": "BANKNIFTY",
                    "action": "BUY",
                    "confidence": 0.8,
                    "reasoning": "RSI > 32",
                    "timestamp": "2026-01-09T10:00:00"
                }
                return R(payload)
            return R([{
                "signal_id": "sig1",
                "id": "sig1",
                "condition_id": "sig1",
                "instrument": "BANKNIFTY",
                "action": "BUY",
                "confidence": 0.8,
                "reasoning": "RSI > 32",
                "timestamp": "2026-01-09T10:00:00"
            }])

    with patch('httpx.AsyncClient', return_value=CapturingClient()):
        res = client.post("/api/trading/execute/sig1")
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        # Among captured posts, one should be the user_module execute POST that includes signal_id
        assert len(posted["posts"]) >= 1
        user_post = next((p for p in posted["posts"] if p["url"].endswith('/api/trading/execute')), None)
        assert user_post is not None
        assert user_post["json"].get("signal_id") == "sig1"
