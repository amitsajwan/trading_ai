import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from dashboard.app import app

client = TestClient(app)


def test_market_list_and_symbol():
    res = client.get("/api/market-data")
    assert res.status_code == 200
    data = res.json()
    assert "instruments" in data

    res = client.get("/api/market/data/NIFTY BANK")
    assert res.status_code == 200
    sdata = res.json()
    assert "price" in sdata


def test_invalid_symbol():
    res = client.get("/api/market/data/INVALID_SYM")
    assert res.status_code == 404
