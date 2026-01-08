#!/usr/bin/env python3
"""Test AI21 API keys."""

import os
from dotenv import load_dotenv

load_dotenv()

def test_ai21_key(api_key, key_name):
    """Test a single AI21 API key."""
    try:
        from ai21 import AI21Client
        from ai21.models.chat import ChatMessage

        client = AI21Client(api_key=api_key)

        messages = [
            ChatMessage(role="user", content="Hello, test message"),
        ]

        response = client.chat.completions.create(
            messages=messages,
            model="jamba-large",
            max_tokens=50  # Small response for testing
        )

        # Check if we got a valid response
        if hasattr(response, 'choices') and response.choices:
            return True, "SUCCESS"
        else:
            return False, "Invalid response format"

    except Exception as e:
        return False, str(e)[:100]

def main():
    """Test all AI21 API keys."""
    print("Testing AI21 API keys...")
    print("=" * 50)

    valid_keys = 0
    total_keys = 0

    # Test primary key
    key = os.getenv('AI21_API_KEY')
    if key:
        total_keys += 1
        success, message = test_ai21_key(key, 'AI21_API_KEY')
        status = "OK" if success else "FAIL"
        print(f"{status} - AI21_API_KEY: {message}")
        if success:
            valid_keys += 1

    # Test additional keys
    for i in range(2, 10):
        key_name = f'AI21_API_KEY_{i}'
        key = os.getenv(key_name)
        if key:
            total_keys += 1
            success, message = test_ai21_key(key, key_name)
            status = "OK" if success else "FAIL"
            print(f"{status} - {key_name}: {message}")
            if success:
                valid_keys += 1
        else:
            break

    print("=" * 50)
    print(f"Valid keys: {valid_keys}/{total_keys}")

    if valid_keys >= 2:
        print("SUCCESS: AI21 keys working! Ready for load balancing.")
    elif valid_keys > 0:
        print("PARTIAL: Some keys working.")
    else:
        print("ERROR: No valid AI21 keys found.")

if __name__ == "__main__":
    main()



