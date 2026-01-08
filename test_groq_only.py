#!/usr/bin/env python3
"""Test Groq API key only."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_groq():
    """Test Groq API key."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("No Groq API key found")
        return False

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'ping'}],
            max_tokens=1
        )
        print("SUCCESS: Groq API key is valid!")
        print("Response:", response.choices[0].message.content)
        return True
    except Exception as e:
        print("FAILED: Groq API key is invalid")
        print("Error:", str(e)[:100])
        return False

if __name__ == "__main__":
    print("Testing Groq API key...")
    test_groq()

