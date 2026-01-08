#!/usr/bin/env python3
"""Test load balancing for multiple providers (Groq + AI21)."""

import os
from dotenv import load_dotenv
from groq_load_balancer import GroqLoadBalancer
from ai21_load_balancer import AI21LoadBalancer

load_dotenv()

def test_multi_provider_load_balancing():
    """Test load balancing across Groq and AI21 providers."""

    print("Multi-Provider Load Balancing Test")
    print("=" * 60)

    # Initialize load balancers
    groq_balancer = GroqLoadBalancer()
    ai21_balancer = AI21LoadBalancer()

    print(f"Groq: {len(groq_balancer.api_keys)} keys")
    print(f"AI21: {len(ai21_balancer.api_keys)} keys")
    print()

    # Test messages
    test_prompts = [
        "Explain machine learning in simple terms",
        "What are the benefits of cloud computing?",
        "How does blockchain work?",
        "What is quantum computing?"
    ]

    print("Testing load balancing across providers...")
    print("-" * 60)

    results = []

    for i, prompt in enumerate(test_prompts):
        try:
            # Alternate between providers
            if i % 2 == 0:
                # Use Groq
                response = groq_balancer.call_groq(
                    system_prompt="You are a helpful technical assistant.",
                    user_message=prompt,
                    max_tokens=150
                )
                provider = "Groq"
                key_num = (groq_balancer.key_index - 1) % len(groq_balancer.api_keys) + 1
            else:
                # Use AI21
                response = ai21_balancer.call_ai21(
                    user_message=prompt,
                    max_tokens=150
                )
                provider = "AI21"
                key_num = (ai21_balancer.key_index - 1) % len(ai21_balancer.api_keys) + 1

            results.append({
                'call': i+1,
                'provider': provider,
                'key': key_num,
                'success': True,
                'response_length': len(response)
            })

            print(f"SUCCESS Call {i+1}: {provider} (Key #{key_num}) - {len(response)} chars")

        except Exception as e:
            results.append({
                'call': i+1,
                'provider': 'ERROR',
                'key': 'N/A',
                'success': False,
                'error': str(e)[:50]
            })
            print(f"FAILED Call {i+1}: {str(e)[:50]}")

    print("-" * 60)

    # Summary
    successful_calls = sum(1 for r in results if r['success'])
    total_calls = len(results)

    groq_calls = sum(1 for r in results if r['provider'] == 'Groq' and r['success'])
    ai21_calls = sum(1 for r in results if r['provider'] == 'AI21' and r['success'])

    print(f"Results: {successful_calls}/{total_calls} calls successful")
    print(f"Groq: {groq_calls} successful calls")
    print(f"AI21: {ai21_calls} successful calls")

    if successful_calls == total_calls:
        print("SUCCESS: All providers working with load balancing!")
    else:
        print("PARTIAL: Some calls failed")

    print("=" * 60)

if __name__ == "__main__":
    test_multi_provider_load_balancing()

