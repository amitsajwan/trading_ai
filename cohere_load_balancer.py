#!/usr/bin/env python3
"""Simple Cohere Load Balancer - For testing Cohere API keys with load balancing."""

import os
from dotenv import load_dotenv
from typing import List
import cohere

load_dotenv()

class CohereLoadBalancer:
    """Simple load balancer for multiple Cohere API keys."""

    def __init__(self):
        self.api_keys = self._load_cohere_keys()
        self.key_index = 0
        self.model = os.getenv("COHERE_MODEL", "command")
        print(f"Initialized Cohere Load Balancer with {len(self.api_keys)} API keys")
        print(f"Using model: {self.model}")

    def _load_cohere_keys(self) -> List[str]:
        """Load all Cohere API keys from environment."""
        keys = []

        # Primary key
        primary = os.getenv('COHERE_API_KEY')
        if primary:
            keys.append(primary)

        # Additional keys
        for i in range(2, 10):
            key = os.getenv(f'COHERE_API_KEY_{i}')
            if key:
                keys.append(key)
            else:
                break

        return keys

    def _get_next_key(self) -> str:
        """Round-robin key selection."""
        if not self.api_keys:
            raise ValueError("No Cohere API keys available")

        key = self.api_keys[self.key_index % len(self.api_keys)]
        self.key_index += 1
        return key

    def call_cohere(self, prompt: str, max_tokens: int = 1000) -> str:
        """Make a Cohere API call with load balancing."""
        api_key = self._get_next_key()

        co = cohere.Client(api_key=api_key)

        response = co.generate(
            model=self.model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.3,
            num_generations=1
        )

        # Extract the response text
        if hasattr(response, 'generations') and response.generations:
            return response.generations[0].text
        else:
            return "No response generated"

def test_cohere_load_balancing():
    """Test the Cohere load balancer."""
    balancer = CohereLoadBalancer()

    print("Testing Cohere load balancing...")
    print("=" * 50)

    # Test messages (lighter test due to rate limits)
    test_prompts = [
        "Hello, how are you?",
        "What is AI?"
    ]

    for i, prompt in enumerate(test_prompts):
        try:
            result = balancer.call_cohere(prompt, max_tokens=50)
            print(f"Call {i+1}: SUCCESS (key #{(balancer.key_index-1) % len(balancer.api_keys) + 1}) - {len(result)} chars")
        except Exception as e:
            print(f"Call {i+1}: FAILED - {str(e)[:50]}")

    print("=" * 50)
    print(f"Cohere load balancing test completed with {len(balancer.api_keys)} keys")

if __name__ == "__main__":
    test_cohere_load_balancing()



