from agents.base_agent import BaseAgent


class DummyLLMManager:
    def __init__(self):
        self.captured = {}
    def get_provider_for_agent(self, agent_name, parallel_group=None):
        return 'openai'
    def call_llm(self, system_prompt, user_message, temperature, max_tokens, provider_name):
        # Capture passed max_tokens and return a valid small JSON
        self.captured['max_tokens'] = max_tokens
        return '{"result": "ok", "items": []}'


class ConcreteAgent(BaseAgent):
    def _get_default_prompt(self):
        return ""
    def process(self, state):
        return state


def test_structured_max_tokens_scaled(monkeypatch):
    agent = ConcreteAgent(agent_name='test')
    dummy = DummyLLMManager()
    agent.llm_manager = dummy

    # Create a large expected format to force high token estimate
    response_format = {f'field_{i}': 0 for i in range(300)}

    # Call structured LLM method (it will parse the small JSON we return)
    res = agent._call_llm_structured('Please return JSON', response_format)

    assert isinstance(res, dict)
    # estimated_tokens = 300*50 + 500 = 15500, so captured should be >= that
    assert dummy.captured['max_tokens'] >= 15500
    assert dummy.captured['max_tokens'] >= agent.llm_manager.captured['max_tokens']