import pytest


def test_decision_snapshot_route_exists():
    from dashboard_pro import app
    paths = {getattr(r, 'path', None) for r in app.router.routes}
    assert "/api/decision-snapshot" in paths, "decision-snapshot endpoint not registered"


def test_decision_snapshot_endpoint_basic_response():
    from dashboard_pro import app
    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi.testclient unavailable")
    client = TestClient(app)
    resp = client.get("/api/decision-snapshot")
    # Endpoint may be 200 (cached/built) or 503 (no Redis/Kite); both prove route exists
    assert resp.status_code in (200, 503)
    assert isinstance(resp.json(), dict)
