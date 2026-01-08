#!/usr/bin/env python3
"""Simple API key test script."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_openai():
    """Test OpenAI API key."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or api_key == 'YOUR_OPENAI_API_KEY':
        print("❌ OpenAI: No API key set")
        return False

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': 'ping'}],
            max_tokens=1
        )
        print("✅ OpenAI: API key is valid")
        return True
    except Exception as e:
        print(f"❌ OpenAI: {str(e)[:100]}")
        return False

def test_groq():
    """Test Groq API key."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key or api_key == 'YOUR_GROQ_API_KEY':
        print("❌ Groq: No API key set")
        return False

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'ping'}],
            max_tokens=1
        )
        print("✅ Groq: API key is valid")
        return True
    except Exception as e:
        print(f"❌ Groq: {str(e)[:100]}")
        return False

def test_google():
    """Test Google Gemini API key."""
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == 'YOUR_GOOGLE_API_KEY':
        print("❌ Google Gemini: No API key set")
        return False

    try:
        import google.genai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content('ping', generation_config={"max_output_tokens": 1})
        print("✅ Google Gemini: API key is valid")
        return True
    except Exception as e:
        print(f"❌ Google Gemini: {str(e)[:100]}")
        return False

def main():
    """Test all API keys."""
    print("Testing API Keys...")
    print("=" * 50)

    results = []
    results.append(test_openai())
    results.append(test_groq())
    results.append(test_google())

    print("\n" + "=" * 50)
    valid_count = sum(results)
    print(f"Valid API keys: {valid_count}/{len(results)}")

    if valid_count > 0:
        print("✅ At least one API key is working!")
        print("The LLM provider manager should now work.")
    else:
        print("❌ No valid API keys found.")
        print("Update your .env file with real API keys.")

if __name__ == "__main__":
    main()

