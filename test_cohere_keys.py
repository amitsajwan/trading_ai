#!/usr/bin/env python3
"""Test Cohere API keys."""

import os
from dotenv import load_dotenv

load_dotenv()

def test_cohere_key(api_key, key_name):
    """Test a single Cohere API key."""
    try:
        import cohere

        co = cohere.Client(api_key=api_key)

        # Test with the specified model
        model = os.getenv("COHERE_MODEL", "command")
        print(f"Testing with model: {model}")

        response = co.generate(
            model=model,
            prompt="Hello, this is a test message.",
            max_tokens=50,
            temperature=0.3,
            num_generations=1
        )

        # Check if we got a valid response
        if hasattr(response, 'generations') and response.generations:
            return True, "SUCCESS"
        else:
            return False, "Invalid response format"

    except Exception as e:
        return False, str(e)[:100]

def main():
    """Test all Cohere API keys."""
    print("Testing Cohere API keys...")
    print("=" * 50)

    valid_keys = 0
    total_keys = 0

    # Test primary key
    key = os.getenv('COHERE_API_KEY')
    if key:
        total_keys += 1
        success, message = test_cohere_key(key, 'COHERE_API_KEY')
        status = "OK" if success else "FAIL"
        print(f"{status} - COHERE_API_KEY: {message}")
        if success:
            valid_keys += 1

    # Test additional keys
    for i in range(2, 10):
        key_name = f'COHERE_API_KEY_{i}'
        key = os.getenv(key_name)
        if key:
            total_keys += 1
            success, message = test_cohere_key(key, key_name)
            status = "OK" if success else "FAIL"
            print(f"{status} - {key_name}: {message}")
            if success:
                valid_keys += 1
        else:
            break

    print("=" * 50)
    print(f"Valid keys: {valid_keys}/{total_keys}")

    if valid_keys >= 2:
        print("SUCCESS: Cohere keys working! Ready for load balancing.")
    elif valid_keys > 0:
        print("PARTIAL: Some keys working.")
    else:
        print("ERROR: No valid Cohere keys found.")

if __name__ == "__main__":
    main()



