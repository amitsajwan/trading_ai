from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from genai_module import api_endpoints


class DummyProviderConfig:
    def __init__(self, name, status="available", requests_today=10, requests_this_minute=1, tokens_today=1000, daily_token_quota=10000):
        self.name = name
        self.status = type("S", (), {"value": status})()
        self.requests_today = requests_today
        self.requests_this_minute = requests_this_minute
        self.tokens_today = tokens_today
        self.daily_token_quota = daily_token_quota
        self.last_error = None
        self.last_error_time = None


class DummyMgr:
    def __init__(self):
        self.providers = {
            "groq": DummyProviderConfig("groq", requests_today=5, tokens_today=100),
            "openai": DummyProviderConfig("openai", status="rate_limited", requests_today=20, tokens_today=200)
        }
        self.provider_clients = {}
        self.current_provider = "groq"

    def get_provider_status(self):
        return {
            "groq": {
                "status": "available",
                "priority": 0,
                "requests_today": 5,
                "requests_this_minute": 1,
                "rate_limit_per_minute": 30,
                "rate_limit_per_day": 100000,
                "tokens_today": 100,
                "daily_token_quota": 10000,
                "last_error": None,
                "last_error_time": None,
                "is_current": True
            },
            "openai": {
                "status": "rate_limited",
                "priority": 5,
                "requests_today": 20,
                "requests_this_minute": 60,
                "rate_limit_per_minute": 60,
                "rate_limit_per_day": 1000000,
                "tokens_today": 200,
                "daily_token_quota": None,
                "last_error": "429 Too Many Requests",
                "last_error_time": None,
                "is_current": False
            }
        }

    def check_provider_health(self, provider_name, timeout=5):
        # Simple simulation: openai is unhealthy
        return provider_name != "openai"


@pytest.fixture
def app(monkeypatch):
    app = FastAPI()
    dummy = DummyMgr()

    def _get_mgr():
        return dummy

    monkeypatch.setattr(api_endpoints, "get_llm_manager", _get_mgr)
    app.include_router(api_endpoints.router)
    return app


def test_list_providers(app):
    client = TestClient(app)
    resp = client.get("/genai/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "groq" in data
    assert data["groq"]["status"] == "available"


def test_provider_health_endpoint(app):
    client = TestClient(app)
    healthy = client.get("/genai/providers/groq/health")
    assert healthy.status_code == 200
    assert healthy.json()["healthy"] is True

    unhealthy = client.get("/genai/providers/openai/health")
    assert unhealthy.status_code == 200
    assert unhealthy.json()["healthy"] is False


def test_trigger_check_endpoint(app):
    client = TestClient(app)
    r = client.post("/genai/providers/groq/check")
    assert r.status_code == 200
    assert r.json()["healthy"] is True


def test_usage_endpoint(app):
    client = TestClient(app)
    r = client.get("/genai/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["total_requests_today"] == 25
    assert "groq" in body["providers"]
