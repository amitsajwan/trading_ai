"""
Tests for RequestRouter handling when provider libraries are missing
"""
from utils.request_router import RequestRouter, ProviderUnavailableError
from datetime import datetime


class DummyAPIManager:
    def get_available_providers(self, kind):
        return [('cohere', {'key': 'dummy', 'model': 'x'})]

    def log_usage(self, provider, tokens):
        pass


def test_missing_library_marks_provider_unavailable():
    router = RequestRouter()
    router.api_manager = DummyAPIManager()

    def fake_cohere(*args, **kwargs):
        raise ProviderUnavailableError('Cohere lib missing')

    router._call_cohere = fake_cohere

    try:
        router.make_llm_request('prompt', max_tokens=10)
    except Exception:
        pass

    assert 'cohere' in router._provider_failures
    st = router._provider_failures['cohere']
    # open_until should be far in future (hours)
    assert st['open_until'] > datetime.now().timestamp() + 60*30
