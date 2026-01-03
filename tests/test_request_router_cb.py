import pytest
from utils.request_router import RequestRouter


class DummyAPIManager:
    def get_available_providers(self, kind):
        return [('openai', {'key': 'x', 'model': 'm'})]


def test_circuit_breaker_opens_after_failures(monkeypatch):
    router = RequestRouter()
    # Shorten thresholds for test
    router.failure_threshold = 1
    router.cooldown_seconds = 60
    router._max_call_retries = 1

    # Monkeypatch api_manager
    router.api_manager = DummyAPIManager()

    # Make the provider always fail
    def fail_call(*args, **kwargs):
        raise Exception("simulated provider failure")
    monkeypatch.setattr(router, '_call_openai', fail_call)

    # First call should raise because provider fails and the circuit will open
    with pytest.raises(Exception):
        router.make_llm_request("hello")

    # Provider should now be marked as open (skipped)
    state = router._provider_failures.get('openai')
    assert state is not None
    assert state.get('open_until') is not None

    # Second call should skip provider and eventually raise All providers failed
    with pytest.raises(Exception) as excinfo:
        router.make_llm_request("hello")
    assert 'All providers failed' in str(excinfo.value)