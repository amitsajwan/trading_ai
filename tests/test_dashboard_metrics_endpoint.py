"""
Test for /api/metrics/llm endpoint
"""
from fastapi.testclient import TestClient
from dashboard_pro import app


def test_llm_metrics_endpoint():
    client = TestClient(app)
    response = client.get('/api/metrics/llm')
    assert response.status_code == 200
    data = response.json()
    assert 'providers' in data
    assert 'summary' in data
    assert isinstance(data['providers'], list)
    # Each provider should have expected keys
    for p in data['providers']:
        assert 'name' in p
        assert 'status' in p
        assert 'tokens_today' in p
        assert 'daily_limit' in p
