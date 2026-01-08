#!/usr/bin/env python3
"""Simple AI21 Load Balancer - For testing AI21 API keys with load balancing."""

import os
from dotenv import load_dotenv
from typing import List
from ai21 import AI21Client
from ai21.models.chat import ChatMessage

load_dotenv()

class AI21LoadBalancer:
    """Simple load balancer for multiple AI21 API keys."""

    def __init__(self):
        self.api_keys = self._load_ai21_keys()
        self.key_index = 0
        print(f"Initialized AI21 Load Balancer with {len(self.api_keys)} API keys")

    def _load_ai21_keys(self) -> List[str]:
        """Load all AI21 API keys from environment."""
        keys = []

        # Primary key
        primary = os.getenv('AI21_API_KEY')
        if primary:
            keys.append(primary)

        # Additional keys
        for i in range(2, 10):
            key = os.getenv(f'AI21_API_KEY_{i}')
            if key:
                keys.append(key)
            else:
                break

        return keys

    def _get_next_key(self) -> str:
        """Round-robin key selection."""
        if not self.api_keys:
            raise ValueError("No AI21 API keys available")

        key = self.api_keys[self.key_index % len(self.api_keys)]
        self.key_index += 1
        return key

    def call_ai21(self, user_message: str, max_tokens: int = 1000) -> str:
        """Make an AI21 API call with load balancing."""
        api_key = self._get_next_key()

        client = AI21Client(api_key=api_key)

        messages = [
            ChatMessage(role="user", content=user_message),
        ]

        response = client.chat.completions.create(
            messages=messages,
            model="jamba-large",
            max_tokens=max_tokens
        )

        # Extract the response text
        if hasattr(response, 'choices') and response.choices:
            return response.choices[0].message.content
        else:
            return "No response generated"

def test_ai21_load_balancing():
    """Test the AI21 load balancer."""
    balancer = AI21LoadBalancer()

    print("Testing AI21 load balancing...")
    print("=" * 50)

    # Make several calls to test load balancing
    test_messages = [
        "Hello, how are you?",
        "What is AI?",
        "Tell me a joke",
        "What is the weather like?",
        "Explain quantum computing"
    ]

    for i, message in enumerate(test_messages):
        try:
            result = balancer.call_ai21(message, max_tokens=100)
            print(f"Call {i+1}: SUCCESS (key #{(balancer.key_index-1) % len(balancer.api_keys) + 1}) - Response length: {len(result)} chars")
        except Exception as e:
            print(f"Call {i+1}: FAILED - {str(e)[:50]}")

    print("=" * 50)
    print(f"AI21 load balancing test completed with {len(balancer.api_keys)} keys")

if __name__ == "__main__":
    test_ai21_load_balancing()



