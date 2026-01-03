from monitoring.system_health import SystemHealthChecker
import requests


def test_check_endpoint_opens_circuit(monkeypatch):
    checker = SystemHealthChecker()
    checker.failure_threshold = 1
    checker.cooldown_seconds = 60

    # Make requests.get always raise
    def fail_get(url, timeout):
        raise requests.exceptions.RequestException("fail")
    monkeypatch.setattr('requests.get', fail_get)

    res = checker.check_endpoint('http://example.com')
    assert res['status'] == 'unhealthy'

    # Next check should return circuit_open (degraded)
    res2 = checker.check_endpoint('http://example.com')
    assert res2['status'] == 'degraded' and 'circuit_open' in res2['message']
