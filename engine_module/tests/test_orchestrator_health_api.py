from fastapi.testclient import TestClient
from engine_module.api_service import app, get_mongo_client

client = TestClient(app)

def test_orchestrator_health_endpoint():
    mongo = get_mongo_client()
    db = mongo["zerodha_trading"]
    # Insert test health doc
    db.orchestrator_health.update_one({'_id': 'current'}, {'$set': {'last_cycle': 1, 'decision': 'HOLD', 'confidence': 0.3}}, upsert=True)

    resp = client.get('/api/v1/orchestrator/health')
    assert resp.status_code == 200
    data = resp.json()
    assert data.get('last_cycle') == 1
    assert data.get('decision') == 'HOLD'
