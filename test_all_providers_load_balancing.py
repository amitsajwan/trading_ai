#!/usr/bin/env python3
"""Test load balancing for all providers (Groq + AI21 + Cohere)."""

import os
from dotenv import load_dotenv
from groq_load_balancer import GroqLoadBalancer
from ai21_load_balancer import AI21LoadBalancer
from cohere_load_balancer import CohereLoadBalancer

load_dotenv()

def test_all_providers_load_balancing():
    """Test load balancing across all providers."""

    print("Multi-Provider Load Balancing Test")
    print("=" * 60)

    # Initialize load balancers
    groq_balancer = GroqLoadBalancer()
    ai21_balancer = AI21LoadBalancer()
    cohere_balancer = CohereLoadBalancer()

    print(f"Groq: {len(groq_balancer.api_keys)} keys")
    print(f"AI21: {len(ai21_balancer.api_keys)} keys")
    print(f"Cohere: {len(cohere_balancer.api_keys)} keys")
    print()

    # Test messages
    test_prompts = [
        "Explain machine learning in simple terms",
        "What are the benefits of cloud computing?",
        "How does blockchain work?",
        "What is quantum computing?",
        "What are the advantages of renewable energy?"
    ]

    print("Testing load balancing across all providers...")
    print("-" * 60)

    results = []
    provider_cycle = ["groq", "ai21", "cohere"]

    for i, prompt in enumerate(test_prompts):
        provider_type = provider_cycle[i % len(provider_cycle)]

        try:
            if provider_type == "groq":
                balancer = groq_balancer
                result = balancer.call_groq(
                    system_prompt="You are a helpful technical assistant.",
                    user_message=prompt,
                    max_tokens=100
                )
            elif provider_type == "ai21":
                balancer = ai21_balancer
                result = balancer.call_ai21(prompt, max_tokens=100)
            elif provider_type == "cohere":
                balancer = cohere_balancer
                result = balancer.call_cohere(prompt, max_tokens=100)

            # Get key number for the balancer that was used
            if provider_type == "groq":
                key_num = (groq_balancer.key_index - 1) % len(groq_balancer.api_keys) + 1
            elif provider_type == "ai21":
                key_num = (ai21_balancer.key_index - 1) % len(ai21_balancer.api_keys) + 1
            elif provider_type == "cohere":
                key_num = (cohere_balancer.key_index - 1) % len(cohere_balancer.api_keys) + 1

            results.append({
                'call': i+1,
                'provider': provider_type.upper(),
                'key': key_num,
                'success': True,
                'response_length': len(result)
            })

            print(f"SUCCESS Call {i+1}: {provider_type.upper()} (Key #{key_num}) - {len(result)} chars")

        except Exception as e:
            results.append({
                'call': i+1,
                'provider': provider_type.upper(),
                'key': 'N/A',
                'success': False,
                'error': str(e)[:50]
            })
            print(f"FAILED Call {i+1}: {provider_type.upper()} - {str(e)[:50]}")

    print("-" * 60)

    # Summary
    successful_calls = sum(1 for r in results if r['success'])
    total_calls = len(results)

    groq_calls = sum(1 for r in results if r['provider'] == 'GROQ' and r['success'])
    ai21_calls = sum(1 for r in results if r['provider'] == 'AI21' and r['success'])
    cohere_calls = sum(1 for r in results if r['provider'] == 'COHERE' and r['success'])

    print(f"Results: {successful_calls}/{total_calls} calls successful")
    print(f"Groq: {groq_calls} successful calls")
    print(f"AI21: {ai21_calls} successful calls")
    print(f"Cohere: {cohere_calls} successful calls")

    if successful_calls == total_calls:
        print("SUCCESS: All providers working with load balancing!")
    elif successful_calls >= total_calls * 0.6:  # At least 60% success
        print("MOSTLY SUCCESS: Most providers working")
    else:
        print("ISSUES: Multiple providers failing")

    print("=" * 60)

if __name__ == "__main__":
    test_all_providers_load_balancing()



