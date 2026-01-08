#!/usr/bin/env python3
"""Simple Groq Load Balancer - Minimal implementation for testing."""

import os
import httpx
from dotenv import load_dotenv
from typing import List, Optional
import random

load_dotenv()

class GroqLoadBalancer:
    """Simple load balancer for multiple Groq API keys."""

    def __init__(self):
        self.api_keys = self._load_groq_keys()
        self.key_index = 0
        print(f"Initialized with {len(self.api_keys)} Groq API keys")

    def _load_groq_keys(self) -> List[str]:
        """Load all Groq API keys from environment."""
        keys = []

        # Primary key
        primary = os.getenv('GROQ_API_KEY')
        if primary:
            keys.append(primary)

        # Additional keys
        for i in range(2, 10):
            key = os.getenv(f'GROQ_API_KEY_{i}')
            if key:
                keys.append(key)
            else:
                break

        return keys

    def _get_next_key(self) -> str:
        """Round-robin key selection."""
        if not self.api_keys:
            raise ValueError("No Groq API keys available")

        key = self.api_keys[self.key_index % len(self.api_keys)]
        self.key_index += 1
        return key

    def call_groq(self, system_prompt: str, user_message: str, max_tokens: int = 1000) -> str:
        """Make a Groq API call with load balancing."""
        api_key = self._get_next_key()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens
        }

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60.0
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

def test_load_balancing():
    """Test the load balancer."""
    balancer = GroqLoadBalancer()

    print("Testing Groq load balancing...")
    print("=" * 50)

    # Make several calls to test load balancing
    for i in range(6):
        try:
            result = balancer.call_groq(
                system_prompt="You are a helpful assistant.",
                user_message=f"Test call #{i+1}",
                max_tokens=50
            )
            print(f"Call {i+1}: SUCCESS (key #{(balancer.key_index-1) % len(balancer.api_keys) + 1})")
        except Exception as e:
            print(f"Call {i+1}: FAILED - {str(e)[:50]}")

    print("=" * 50)
    print(f"Load balancing test completed with {len(balancer.api_keys)} keys")

if __name__ == "__main__":
    test_load_balancing()



