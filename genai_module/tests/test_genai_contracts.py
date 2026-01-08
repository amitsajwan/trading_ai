import inspect
from genai_module.contracts import LLMClient, LLMRequest, LLMResponse


def test_llm_request_defaults():
    req = LLMRequest(prompt="hi")
    assert req.max_tokens == 512
    assert req.temperature == 0.2


def test_llm_client_is_protocol():
    assert inspect.isclass(LLMClient)

