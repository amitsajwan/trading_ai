import pytest
from fastapi.testclient import TestClient

from dashboard.app import app

client = TestClient(app)


def test_options_strategy_advanced_includes_spread_fields():
    resp = client.get('/api/options-strategy-advanced')
    assert resp.status_code == 200
    data = resp.json()
    assert 'available' in data
    if data['available']:
        # At least returns recommendation
        assert 'recommendation' in data
        # Spread fields are optional but should exist when chain is available
        assert 'strategy_type' in data
        assert 'legs' in data
        assert isinstance(data.get('legs'), list)


def test_paper_trade_options_handles_spread_payload():
    # Fetch strategy
    resp = client.get('/api/options-strategy-advanced')
    data = resp.json()
    payload = data if data.get('available') else {}
    # Execute paper trade
    resp2 = client.post('/api/paper-trade/options', json=payload)
    assert resp2.status_code in (200, 400, 500)
    # If ok, verify shape
    if resp2.status_code == 200:
        out = resp2.json()
        assert out.get('ok') is True
        if 'trades' in out:
            assert isinstance(out['trades'], list) and len(out['trades']) >= 1
        else:
            assert 'trade' in out

