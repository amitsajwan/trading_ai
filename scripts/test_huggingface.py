"""Test Hugging Face LLM connection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from config.settings import settings

class TestAgent(BaseAgent):
    """Test agent for Hugging Face."""
    def _get_default_prompt(self):
        return "You are a helpful assistant."
    
    def process(self, state):
        return state

def main():
    print("=" * 60)
    print("Testing Hugging Face LLM Connection")
    print("=" * 60)
    print(f"Provider: {settings.llm_provider}")
    print(f"Model: {settings.llm_model}")
    print(f"API Key: {'Set' if settings.huggingface_api_key else 'Not Set'}")
    print("=" * 60)
    
    try:
        agent = TestAgent("test_agent")
        print("\nTesting LLM call...")
        response = agent._call_llm("Say 'Hello, Hugging Face!' in one sentence.")
        print(f"\nResponse: {response}")
        print("\nSUCCESS: Hugging Face is working!")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

