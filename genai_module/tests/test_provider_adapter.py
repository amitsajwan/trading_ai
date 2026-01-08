import asyncio

from genai_module.adapters.provider_manager import ProviderManagerClient
from genai_module.contracts import LLMRequest


class FakeManager:
    def __init__(self):
        self.calls = []

    def generate_text(self, prompt, max_tokens=512, temperature=0.2, model_override=None):  # noqa: D401
        self.calls.append({
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "model": model_override,
        })
        return f"echo:{prompt}", 5, 0.0

    def validate_primary_provider(self):
        return True


async def _run():
    mgr = FakeManager()
    client = ProviderManagerClient(mgr, default_model="groq:llama-3.1-8b-instant")
    req = LLMRequest(prompt="hi", max_tokens=16, temperature=0.1)
    resp = await client.generate(req)
    assert resp.content == "echo:hi"
    assert resp.tokens_used == 5
    assert resp.cost == 0.0
    ok = await client.validate()
    assert ok is True
    assert mgr.calls[0]["model"] == "groq:llama-3.1-8b-instant"


def test_provider_adapter_sync_wraps_blocking_calls():
    asyncio.run(_run())

