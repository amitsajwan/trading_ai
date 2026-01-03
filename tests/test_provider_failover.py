import types
from agents.llm_provider_manager import LLMProviderManager, ProviderConfig, ProviderStatus


def test_provider_failover_and_token_accounting(monkeypatch):
    mgr = LLMProviderManager()
    # Stop health thread to avoid race in test
    mgr._stop_health_thread.set()

    # Prepare providers
    p1 = ProviderConfig(name='openai', priority=0)
    p2 = ProviderConfig(name='groq', priority=1)
    mgr.providers = {'openai': p1, 'groq': p2}
    mgr.current_provider = 'openai'

    # Bad client for openai that raises
    bad_client = types.SimpleNamespace()
    bad_client.chat = types.SimpleNamespace()
    def bad_create(**kwargs):
        raise Exception('simulated failure')
    bad_client.chat.completions = types.SimpleNamespace(create=bad_create)

    # Good client for groq that returns a simple response
    good_client = types.SimpleNamespace()
    def good_groq_create(**kwargs):
        # Groq returns an object with choices[0].message.content
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='good_response'))])
    good_client.chat = types.SimpleNamespace()
    good_client.chat.completions = types.SimpleNamespace(create=good_groq_create)

    mgr.provider_clients = {'openai': bad_client, 'groq': good_client}

    # Call LLM - manager should handle openai failure and try groq
    resp = mgr.call_llm(system_prompt='sys', user_message='u', max_tokens=10)

    # Ensure openai status was marked error/unavailable and groq tokens recorded
    assert mgr.providers['openai'].status in [ProviderStatus.ERROR, ProviderStatus.UNAVAILABLE, ProviderStatus.RATE_LIMITED]
    assert mgr.providers['groq'].requests_today >= 1
    assert getattr(mgr.providers['groq'], 'tokens_today', 0) >= 1
    # Response may come from groq or fallback; ensure at least tokens were accounted for