"""
Tests for RequestRouter handling of 429 rate limits
"""
import time
from datetime import datetime
from utils.request_router import RequestRouter, RateLimitError


class DummyAPIManager:
    def get_available_providers(self, kind):
        # Return a single provider 'ai21'
        return [('ai21', {'key': 'dummy', 'model': 'j2-large'})]

    def log_usage(self, provider, tokens):
        pass


def test_rate_limit_marks_provider_open():
    router = RequestRouter()
    # Inject dummy api_manager
    router.api_manager = DummyAPIManager()

    # Monkeypatch the ai21 caller to raise RateLimitError
    def fake_ai21(*args, **kwargs):
        raise RateLimitError('Rate limited by AI21', reset_seconds=2)

    router._call_ai21 = fake_ai21

    # Call make_llm_request and expect exception after attempts
    try:
        router.make_llm_request('hello world', max_tokens=10)
    except Exception as e:
        pass

    # Provider should be in _provider_failures with open_until set
    assert 'ai21' in router._provider_failures
    st = router._provider_failures['ai21']
    assert st.get('open_until', 0) > datetime.now().timestamp() - 1


def test_rate_limit_respects_reset_seconds():
    router = RequestRouter()
    router.api_manager = DummyAPIManager()

    def fake_ai21(*args, **kwargs):
        raise RateLimitError('Rate limited by AI21', reset_seconds=3)

    router._call_ai21 = fake_ai21

    try:
        router.make_llm_request('hello', max_tokens=10)
    except Exception:
        pass

    st = router._provider_failures.get('ai21')
    assert st is not None
    now = datetime.now().timestamp()
    assert st['open_until'] > now
    # It should be roughly now + reset_seconds (3s)
    assert st['open_until'] - now <= 10
