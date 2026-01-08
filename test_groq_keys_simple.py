#!/usr/bin/env python3
"""Test all Groq API keys (simple version)."""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def test_groq_key(api_key, key_name):
    """Test a single Groq API key."""
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
            return True, "SUCCESS"
        else:
            return False, f"HTTP {response.status_code}"

    except Exception as e:
        return False, str(e)[:50]

def main():
    """Test all Groq API keys."""
    print("Testing all Groq API keys...")
    print("=" * 50)

    valid_keys = 0
    total_keys = 0

    # Test primary key
    key = os.getenv('GROQ_API_KEY')
    if key:
        total_keys += 1
        success, message = test_groq_key(key, 'GROQ_API_KEY')
        status = "OK" if success else "FAIL"
        print(f"{status} - GROQ_API_KEY: {message}")
        if success:
            valid_keys += 1

    # Test additional keys
    for i in range(2, 10):
        key_name = f'GROQ_API_KEY_{i}'
        key = os.getenv(key_name)
        if key:
            total_keys += 1
            success, message = test_groq_key(key, key_name)
            status = "OK" if success else "FAIL"
            print(f"{status} - {key_name}: {message}")
            if success:
                valid_keys += 1
        else:
            break

    print("=" * 50)
    print(f"Valid keys: {valid_keys}/{total_keys}")

    if valid_keys >= 3:
        print("SUCCESS: All Groq keys working! Ready for load balancing.")
    elif valid_keys > 0:
        print("PARTIAL: Some keys working. Will use available keys.")
    else:
        print("ERROR: No valid Groq keys found.")

if __name__ == "__main__":
    main()



