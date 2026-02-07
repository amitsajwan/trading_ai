import pytest
from fastapi.testclient import TestClient
from engine_module.api_service import main_app

client = TestClient(main_app)

def test_list_agents():
    r = client.get('/api/engine/agents')
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any('name' in a for a in data)

def test_dependencies():
    r = client.get('/api/engine/agents/dependencies')
    assert r.status_code == 200
    data = r.json()
    assert 'nodes' in data and 'edges' in data

def test_get_agent_details():
    r = client.get('/api/engine/agents/TechnicalAgent/details')
    assert r.status_code == 200
    data = r.json()
    assert data.get('agent_name') == 'TechnicalAgent'

def test_update_agent_config():
    payload = { 'min_confidence': 0.55 }
    r = client.post('/api/engine/agents/TechnicalAgent/config', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get('success') is True
