"""Simple test script to verify local LLM (Ollama) is working."""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import asyncio
from config.settings import settings

# Faster models for quick testing (ordered by speed)
FAST_MODELS = [
    "tinyllama",           # ~1.1B - Fastest (~1-2s)
    "llama3.2:1b",        # ~1B - Very fast (~1-2s)
    "phi3:mini",          # ~3.8B - Fast (~2-5s)
    "llama3.2:3b",        # ~3B - Fast (~2-5s)
    "llama3.1:8b",        # ~8B - Medium (~5-15s)
]

def find_fastest_model(available_models):
    """Find the fastest available model from FAST_MODELS list."""
    available_set = set(available_models)
    
    # Check FAST_MODELS in order (fastest first)
    for fast_model in FAST_MODELS:
        # Check exact match
        if fast_model in available_set:
            return fast_model
        # Check partial match (e.g., "llama3.2:3b" matches "llama3.2:3b-instruct")
        for model in available_models:
            if model.startswith(fast_model.split(':')[0]):  # Match base name
                # Prefer smaller models
                if '1b' in model or 'tiny' in model.lower():
                    return model
    
    # If no fast model found, return first available
    return available_models[0] if available_models else None

def test_ollama_connection():
    """Test if Ollama is running and accessible."""
    print("=" * 60)
    print("Testing Ollama Connection")
    print("=" * 60)
    
    base_url = settings.ollama_base_url or "http://localhost:11434"
    
    try:
        print(f"\n1. Checking if Ollama is running at {base_url}...")
        response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        
        if response.status_code == 200:
            print("   ✅ Ollama is running!")
            models_data = response.json().get('models', [])
            available_models = [m.get('name', '') for m in models_data]
            
            if available_models:
                print(f"   ✅ Found {len(available_models)} model(s):")
                for model in available_models[:5]:
                    print(f"      - {model}")
                
                # Find fastest model
                fastest = find_fastest_model(available_models)
                if fastest and fastest != available_models[0]:
                    print(f"\n   💡 Fastest model for testing: {fastest}")
                
                return True, available_models
            else:
                print("   ⚠️  Ollama is running but no models found!")
                print("   💡 Quick test model: ollama pull tinyllama")
                print("   💡 Or: ollama pull llama3.2:3b")
                return False, []
        else:
            print(f"   ❌ Ollama returned status {response.status_code}")
            return False, []
            
    except httpx.ConnectError:
        print(f"   ❌ Cannot connect to Ollama at {base_url}")
        print("   💡 Make sure Ollama is running:")
        print("      - Start Ollama: ollama serve")
        print("      - Or check if it's running on a different port")
        return False, []
    except Exception as e:
        print(f"   ❌ Error checking Ollama: {e}")
        return False, []

def test_simple_llm_call(model_name: str = None, available_models: list = None):
    """Test a simple LLM call."""
    print("\n" + "=" * 60)
    print("Testing Simple LLM Call")
    print("=" * 60)
    
    # Get model name - prefer fastest available
    if not model_name:
        if available_models:
            model_name = find_fastest_model(available_models)
        else:
            model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    # Show speed estimate
    speed_note = ""
    if "tiny" in model_name.lower() or "1b" in model_name:
        speed_note = " (very fast: ~1-2s)"
    elif "3b" in model_name or "phi3" in model_name.lower():
        speed_note = " (fast: ~2-5s)"
    elif "8b" in model_name:
        speed_note = " (medium: ~5-15s, first call may be 30-60s)"
    
    print(f"\n2. Testing LLM call with model: {model_name}{speed_note}")
    print("   Sending test prompt: 'Say hello in one sentence'")
    
    try:
        from openai import OpenAI
        import httpx
        
        base_url = settings.ollama_base_url or "http://localhost:11434"
        ollama_api_url = f"{base_url}/v1" if not base_url.endswith("/v1") else base_url
        
        client = OpenAI(
            api_key="ollama",
            base_url=ollama_api_url,
            timeout=httpx.Timeout(60.0, connect=10.0)
        )
        
        print("   ⏳ Waiting for response (this may take 10-30 seconds)...")
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Say hello in one sentence. Just say hello, nothing else."}
            ],
            temperature=0.7,
            max_tokens=50
        )
        
        result = response.choices[0].message.content.strip()
        
        print(f"   ✅ LLM responded!")
        print(f"   Response: {result}")
        
        if result and len(result) > 0:
            print("\n   ✅ Basic LLM call works!")
            return True
        else:
            print("\n   ⚠️  LLM responded but response is empty")
            return False
            
    except Exception as e:
        error_str = str(e)
        print(f"   ❌ LLM call failed: {error_str}")
        
        if "timeout" in error_str.lower():
            print("\n   💡 Tip: Ollama might be slow. Try:")
            print("      - Check if Ollama is processing: ollama ps")
            print("      - Restart Ollama: ollama serve")
        elif "404" in error_str or "model" in error_str.lower():
            print(f"\n   💡 Tip: Model '{model_name}' might not be available.")
            print(f"      - Pull the model: ollama pull {model_name}")
            print(f"      - Or check available models: ollama list")
        elif "connection" in error_str.lower():
            print("\n   💡 Tip: Check if Ollama is running:")
            print("      - Start Ollama: ollama serve")
            print(f"      - Check URL: {base_url}")
        
        return False

def test_structured_output(model_name: str = None, available_models: list = None):
    """Test structured output (what agents use)."""
    print("\n" + "=" * 60)
    print("Testing Structured Output (Agent-style)")
    print("=" * 60)
    
    if not model_name:
        if available_models:
            model_name = find_fastest_model(available_models)
        else:
            model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    print(f"\n3. Testing structured JSON output with model: {model_name}")
    print("   This simulates what agents do...")
    
    try:
        from openai import OpenAI
        import httpx
        import json
        
        base_url = settings.ollama_base_url or "http://localhost:11434"
        ollama_api_url = f"{base_url}/v1" if not base_url.endswith("/v1") else base_url
        
        client = OpenAI(
            api_key="ollama",
            base_url=ollama_api_url,
            timeout=httpx.Timeout(60.0, connect=10.0)
        )
        
        prompt = """Respond with JSON format:
{
  "status": "success",
  "message": "test"
}"""
        
        print("   ⏳ Waiting for structured response (this may take 15-45 seconds)...")
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=200
        )
        
        result = response.choices[0].message.content.strip()
        
        # Try to parse JSON
        try:
            # Remove markdown code blocks if present
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            
            result = result.strip()
            parsed = json.loads(result)
            
            print(f"   ✅ Structured output works!")
            print(f"   Parsed JSON: {json.dumps(parsed, indent=2)}")
            return True
            
        except json.JSONDecodeError:
            print(f"   ⚠️  LLM responded but JSON parsing failed")
            print(f"   Response: {result[:200]}")
            print("\n   💡 Tip: Model might need better prompting for JSON")
            return False
            
    except Exception as e:
        print(f"   ❌ Structured output test failed: {e}")
        return False

def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(description="Test local LLM (Ollama)")
    parser.add_argument(
        "--model",
        type=str,
        help="Specific model to test (e.g., tinyllama, llama3.2:3b)"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fastest available model (recommended for quick testing)"
    )
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("Local LLM (Ollama) Verification")
    print("=" * 60)
    print("\nThis script tests if your local LLM is working correctly.")
    print("Run this before the full verification to catch LLM issues early.\n")
    
    # Test 1: Connection
    connection_ok, models = test_ollama_connection()
    
    if not connection_ok:
        print("\n" + "=" * 60)
        print("❌ FAILED: Cannot connect to Ollama")
        print("=" * 60)
        print("\nFix this before running full verification:")
        print("1. Start Ollama: ollama serve")
        print("2. Pull a fast model: ollama pull tinyllama")
        print("   Or: ollama pull llama3.2:3b")
        print("3. Run this test again")
        return False
    
    # Test 2: Simple call
    if args.model:
        model_name = args.model
        if model_name not in models:
            print(f"\n⚠️  Model '{model_name}' not found. Available models:")
            for m in models:
                print(f"   - {m}")
            print(f"\nUsing fastest available model instead...")
            model_name = find_fastest_model(models)
    elif args.fast or not args.model:
        # Use fastest available
        model_name = find_fastest_model(models) if models else os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    else:
        model_name = models[0] if models else os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    simple_call_ok = test_simple_llm_call(model_name, models)
    
    if not simple_call_ok:
        print("\n" + "=" * 60)
        print("❌ FAILED: Basic LLM call doesn't work")
        print("=" * 60)
        print("\nFix this before running full verification:")
        print("1. Check Ollama logs for errors")
        print("2. Try restarting Ollama: ollama serve")
        print("3. Verify model exists: ollama list")
        return False
    
    # Test 3: Structured output (optional but recommended)
    structured_ok = test_structured_output(model_name, models)
    
    # Show model recommendations
    if connection_ok and models:
        print("\n" + "=" * 60)
        print("💡 Model Recommendations")
        print("=" * 60)
        print("\nFor faster testing, use one of these models:")
        print("   - tinyllama (~1-2s per call)")
        print("   - llama3.2:1b (~1-2s per call)")
        print("   - llama3.2:3b (~2-5s per call)")
        print("\nTo pull a fast model:")
        print("   ollama pull tinyllama")
        print("\nTo test with a specific model:")
        print("   python scripts/test_local_llm.py --model tinyllama")
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    print(f"\n✅ Connection: {'PASS' if connection_ok else 'FAIL'}")
    print(f"✅ Simple Call: {'PASS' if simple_call_ok else 'FAIL'}")
    print(f"{'✅' if structured_ok else '⚠️ '} Structured Output: {'PASS' if structured_ok else 'WARNING (optional)'}")
    
    if connection_ok and simple_call_ok:
        print("\n✅ Local LLM is working! You can proceed with full verification.")
        print("   Run: python scripts/verify_all_components.py")
        return True
    else:
        print("\n❌ Local LLM has issues. Fix them before running full verification.")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

