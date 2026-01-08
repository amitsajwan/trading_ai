#!/usr/bin/env python3
"""Test LLM API keys and provider availability."""

import os
import sys
import asyncio
import logging
from typing import Dict, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genai_module.core.llm_provider_manager import LLMProviderManager, ProviderStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test API keys provided by user
TEST_KEYS = {
    'HUGGINGFACE_API_KEY': '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',
    'GOOGLE_API_KEY': 'AIzaSyCEYoOsbt-FXzyV3Kh9i_fwmhvF3EsZSME',
    'GROQ_API_KEY': 'GROQ_API_KEY_REDACTED',
    'COHERE_API_KEY': 'xXWGFBOCljq4vp5YNKJz7XTHAcPCv3e7lPDNsFHj',
    'OPENAI_API_KEY': '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',
    'AI21_API_KEY': 'e7616a6d-78bd-47dc-b076-539bacd710d9'
}

def test_provider(manager: LLMProviderManager, provider_name: str) -> Dict:
    """Test a specific provider."""
    result = {
        'provider': provider_name,
        'status': 'unknown',
        'working': False,
        'error': None,
        'response_time': None
    }

    try:
        import time
        start_time = time.time()

        # Try a simple test call
        test_prompt = "Say 'Hello' in exactly 1 word."
        response = manager.call_llm("", test_prompt, provider_name=provider_name, max_tokens=10)

        end_time = time.time()
        result['response_time'] = round(end_time - start_time, 2)

        if response and len(response.strip()) > 0:
            result['status'] = 'working'
            result['working'] = True
            result['response'] = response.strip()[:50] + '...' if len(response) > 50 else response.strip()
        else:
            result['status'] = 'no_response'
            result['error'] = 'Empty response'

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)

    return result

def test_all_providers():
    """Test all configured providers."""
    print("TESTING LLM API PROVIDERS")
    print("=" * 50)

    # Set test environment variables
    original_env = {}
    for key, value in TEST_KEYS.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        # Initialize manager with test keys
        manager = LLMProviderManager()

        print(f"Configured providers: {list(manager.providers.keys())}")
        print()

        results = []
        working_providers = []

        for provider_name in manager.providers.keys():
            print(f"Testing {provider_name}...")
            result = test_provider(manager, provider_name)
            results.append(result)

            status_icon = "[OK]" if result['working'] else "[FAIL]"
            print(f"   {status_icon} {provider_name}: {result['status']}")
            if result['working']:
                print(f"      Response: {result.get('response', 'N/A')}")
                print(f"      Time: {result.get('response_time', 'N/A')}s")
                working_providers.append(provider_name)
            else:
                print(f"      Error: {result.get('error', 'Unknown')}")

            print()

        print("SUMMARY")
        print("=" * 50)
        print(f"Working providers ({len(working_providers)}): {', '.join(working_providers) if working_providers else 'None'}")

        if working_providers:
            print(f"RECOMMENDATION: Use {working_providers[0]} as primary provider")
            print("Set SINGLE_PROVIDER=true and PRIMARY_PROVIDER=" + working_providers[0])
        else:
            print("No working providers found - check API keys")

        return results

    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

if __name__ == "__main__":
    test_all_providers()

