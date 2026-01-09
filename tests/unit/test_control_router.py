import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from dashboard.app import app

client = TestClient(app)


def test_control_status():
    res = client.get("/api/control/status")
    assert res.status_code == 200
    data = res.json()
    assert "mode" in data
    assert "balance" in data


def test_mode_switch_and_clear():
    res = client.post("/api/control/mode/switch", json={"mode": "paper_mock"})
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert data.get("mode") == "paper_mock"

    res = client.post("/api/control/mode/clear-override")
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True


def test_balance_endpoints():
    res = client.get("/api/control/balance")
    assert res.status_code == 200
    before = res.json().get("balance")

    res = client.post("/api/control/balance/set", json={"balance": 12345.0})
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert data.get("balance") == 12345.0

    res = client.get("/api/control/balance")
    assert res.json().get("balance") == 12345.0
