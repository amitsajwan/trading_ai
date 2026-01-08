#!/usr/bin/env python3
"""Test all Groq API keys."""

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
            return False, f"HTTP {response.status_code}: {response.text[:100]}"

    except Exception as e:
        return False, str(e)[:100]

def main():
    """Test all Groq API keys."""
    print("Testing all Groq API keys...")
    print("=" * 50)

    valid_keys = []

    # Test primary key
    key = os.getenv('GROQ_API_KEY')
    if key:
        success, message = test_groq_key(key, 'GROQ_API_KEY')
        status = "✅" if success else "❌"
        print(f"{status} GROQ_API_KEY: {message}")
        if success:
            valid_keys.append(('GROQ_API_KEY', key))

    # Test additional keys
    for i in range(2, 10):
        key_name = f'GROQ_API_KEY_{i}'
        key = os.getenv(key_name)
        if key:
            success, message = test_groq_key(key, key_name)
            status = "✅" if success else "❌"
            print(f"{status} {key_name}: {message}")
            if success:
                valid_keys.append((key_name, key))
        else:
            break

    print("=" * 50)
    print(f"Valid keys: {len(valid_keys)}/{len([k for k in os.environ.keys() if k.startswith('GROQ_API_KEY')])}")

    if len(valid_keys) >= 3:
        print("🎉 All Groq keys are working! Load balancing is ready.")
    elif len(valid_keys) > 0:
        print("⚠️  Some keys are working. Load balancing will use available keys.")
    else:
        print("❌ No valid Groq keys found.")

if __name__ == "__main__":
    main()



