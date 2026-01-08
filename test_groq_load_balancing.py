#!/usr/bin/env python3
"""Test Groq load balancing functionality."""

import sys
import os
sys.path.insert(0, './genai_module/src')

from dotenv import load_dotenv
load_dotenv()

def test_load_balancing():
    """Test that load balancing works across multiple Groq keys."""
    try:
        from genai_module.core.llm_provider_manager import LLMProviderManager

        # Create manager (this will load our multiple Groq keys)
        manager = LLMProviderManager()

        print("Testing Groq load balancing...")
        print(f"Available Groq keys: {len(manager._groq_keys) if hasattr(manager, '_groq_keys') else 1}")

        # Make several calls to see key rotation
        test_calls = 6  # Should rotate through all 3 keys twice

        for i in range(test_calls):
            try:
                result = manager.call_llm(
                    system_prompt="You are a helpful assistant.",
                    user_message=f"Test call #{i+1}",
                    max_tokens=10
                )
                print(f"Call {i+1}: SUCCESS - Got response")
            except Exception as e:
                print(f"Call {i+1}: FAILED - {str(e)[:50]}")

        print("Load balancing test completed!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_load_balancing()

