#!/usr/bin/env python3
"""Simple Groq API test."""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def test_groq_direct():
    """Test Groq API directly with HTTP request."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("No Groq API key found")
        return

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10.0
        )

        if response.status_code == 200:
            print("SUCCESS: Groq API key is valid!")
            result = response.json()
            print("Response received successfully")
        else:
            print(f"FAILED: HTTP {response.status_code}")
            print("Response:", response.text[:200])

    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    print("Testing Groq API key directly...")
    test_groq_direct()

