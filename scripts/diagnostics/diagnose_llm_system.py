#!/usr/bin/env python3
"""
Comprehensive diagnostic script for Local LLM and Trading System health check.
Run this to diagnose issues with LLM providers and agent configuration.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def print_header(text, char="="):
    """Print formatted header."""
    width = 70
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}\n")


def print_status(name, status, message=""):
    """Print status line."""
    icon = "✅" if status else "❌"
    extra = f" - {message}" if message else ""
    print(f"  {icon} {name}{extra}")


def check_env_file():
    """Check .env file and key configurations."""
    print_header("1. Environment Configuration")
    
    env_path = Path(".env")
    if not env_path.exists():
        print_status(".env file", False, "NOT FOUND")
        print("\n  ⚠️  Create .env file with:")
        print("     - LLM_PROVIDER (ollama, groq, gemini, etc.)")
        print("     - INSTRUMENT_SYMBOL (BTC-USD, NIFTY BANK, etc.)")
        print("     - INSTRUMENT_NAME (Bitcoin, Bank Nifty, etc.)")
        return None
    
    print_status(".env file", True, "Found")
    
    # Read and parse .env
    config = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    
    # Check critical configs
    critical_keys = [
        "LLM_PROVIDER",
        "INSTRUMENT_SYMBOL",
        "INSTRUMENT_NAME",
        "DATA_SOURCE",
    ]
    
    for key in critical_keys:
        value = config.get(key, "NOT SET")
        is_set = key in config and config[key]
        print_status(key, is_set, value if is_set else "NOT SET (using defaults)")
    
    return config


def check_ollama():
    """Check Ollama local LLM availability."""
    print_header("2. Ollama (Local LLM)")
    
    try:
        import httpx
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        try:
            response = httpx.get(f"{base_url}/api/tags", timeout=3)
            if response.status_code == 200:
                models = response.json().get("models", [])
                print_status("Ollama service", True, f"Running at {base_url}")
                print(f"\n  Available models ({len(models)}):")
                for model in models:
                    name = model.get("name", "Unknown")
                    size = model.get("size", 0) / (1024**3)  # Convert to GB
                    print(f"    - {name} ({size:.1f} GB)")
                return True
            else:
                print_status("Ollama service", False, f"Status code: {response.status_code}")
                return False
        except httpx.ConnectError:
            print_status("Ollama service", False, "NOT RUNNING")
            print("\n  ⚠️  To start Ollama:")
            print("     1. Install: curl -fsSL https://ollama.com/install.sh | sh")
            print("     2. Start: ollama serve")
            print("     3. Pull model: ollama pull llama3.1:8b")
            return False
    except ImportError:
        print_status("httpx package", False, "NOT INSTALLED (pip install httpx)")
        return False


def check_cloud_providers():
    """Check cloud LLM provider configurations."""
    print_header("3. Cloud LLM Providers")
    
    providers = {
        "Groq": "GROQ_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "Google Gemini": "GOOGLE_API_KEY",
        "OpenRouter": "OPENROUTER_API_KEY",
        "Together AI": "TOGETHER_API_KEY",
        "HuggingFace": "HUGGINGFACE_API_KEY",
    }
    
    available = []
    for name, env_var in providers.items():
        key = os.getenv(env_var)
        if key:
            masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "****"
            print_status(name, True, f"Key configured ({masked_key})")
            available.append(name)
        else:
            print_status(name, False, f"{env_var} not set")
    
    return available


def check_llm_manager():
    """Test the LLM provider manager."""
    print_header("4. LLM Provider Manager Test")
    
    try:
        from agents.llm_provider_manager import LLMProviderManager
        
        manager = LLMProviderManager()
        providers = manager.providers
        
        print(f"  Initialized {len(providers)} provider(s):\n")
        
        for name, config in providers.items():
            status_icon = "✅" if config.status.value == "available" else "❌"
            print(f"    {status_icon} {name}:")
            print(f"       Model: {config.model}")
            print(f"       Priority: {config.priority}")
            print(f"       Status: {config.status.value}")
            if config.last_error:
                print(f"       Error: {config.last_error[:60]}...")
            print()
        
        current = manager.current_provider
        print(f"  Current provider: {current or 'NONE'}")
        return manager
        
    except Exception as e:
        print_status("LLM Manager", False, str(e)[:60])
        return None


def test_llm_call(manager):
    """Test actual LLM call."""
    print_header("5. LLM Call Test")
    
    if not manager:
        print("  ⚠️  Skipping - No LLM manager available")
        return False
    
    try:
        print("  Testing LLM call...")
        response = manager.call_llm(
            system_prompt="You are a helpful assistant.",
            user_message="Say 'LLM is working!' in exactly 5 words.",
            max_tokens=50,
            temperature=0.1
        )
        print_status("LLM Call", True)
        print(f"\n  Response: {response[:100]}...")
        return True
    except Exception as e:
        print_status("LLM Call", False, str(e)[:100])
        return False


def check_prompts():
    """Check if prompts are properly parameterized."""
    print_header("6. Agent Prompts - Decoupling Check")
    
    prompts_dir = Path("config/prompts")
    if not prompts_dir.exists():
        print_status("Prompts directory", False, "NOT FOUND")
        return
    
    prompt_files = list(prompts_dir.glob("*.txt"))
    print(f"  Found {len(prompt_files)} prompt files:\n")
    
    hardcoded_issues = []
    for prompt_file in prompt_files:
        content = prompt_file.read_text()
        issues = []
        
        # Check for hardcoded instrument names
        if "Bank Nifty" in content:
            issues.append("Hardcoded 'Bank Nifty'")
        if "NIFTY BANK" in content:
            issues.append("Hardcoded 'NIFTY BANK'")
        if "RBI" in content and "crypto" not in content.lower():
            issues.append("RBI-specific (may need crypto equivalent)")
        
        status = len(issues) == 0
        if issues:
            print_status(prompt_file.name, False, ", ".join(issues))
            hardcoded_issues.append(prompt_file.name)
        else:
            print_status(prompt_file.name, True, "Parameterized")
    
    if hardcoded_issues:
        print("\n  ⚠️  These prompts have hardcoded references:")
        print("     Consider using {instrument_name} placeholder instead")


def check_redis():
    """Check Redis connection."""
    print_header("7. Redis (Cache)")
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=2)
        r.ping()
        print_status("Redis", True, "Running on localhost:6379")
        
        # Check for old data
        keys = r.keys("*")
        print(f"  Keys in Redis: {len(keys)}")
        
        # Check for Bank Nifty specific data
        bn_keys = [k for k in keys if b"NIFTY" in k.upper() or b"BANK" in k.upper()]
        if bn_keys:
            print(f"\n  ⚠️  Found {len(bn_keys)} Bank Nifty related keys")
            print("     This might be old cached data!")
        
        return True
    except Exception as e:
        print_status("Redis", False, str(e)[:50])
        return False


def check_instrument_config():
    """Check current instrument configuration from settings."""
    print_header("8. Instrument Configuration (Runtime)")
    
    try:
        from config.settings import settings
        
        configs = [
            ("Instrument Symbol", settings.instrument_symbol),
            ("Instrument Name", settings.instrument_name),
            ("Exchange", settings.instrument_exchange),
            ("Data Source", settings.data_source),
            ("News Query", settings.news_query),
            ("Market 24/7", settings.market_24_7),
            ("LLM Provider", settings.llm_provider),
            ("LLM Model", settings.llm_model),
        ]
        
        for name, value in configs:
            # Check if it's a default Bank Nifty value
            is_default_bn = "NIFTY" in str(value).upper() or "Bank" in str(value)
            status = not is_default_bn if name != "News Query" else True
            print_status(name, status, str(value)[:50])
        
        return settings
    except Exception as e:
        print_status("Settings", False, str(e)[:60])
        return None


def generate_recommendations():
    """Generate fix recommendations."""
    print_header("RECOMMENDATIONS", char="*")
    
    print("""
  Based on the diagnostic, here are the recommended fixes:

  1. CREATE/UPDATE .env FILE:
     ----------------------------
     # LLM Configuration
     LLM_PROVIDER=ollama  # or groq, gemini
     OLLAMA_BASE_URL=http://localhost:11434
     OLLAMA_MODEL=llama3.1:8b
     
     # BTC Configuration
     INSTRUMENT_SYMBOL=BTC-USD
     INSTRUMENT_NAME=Bitcoin
     INSTRUMENT_EXCHANGE=CRYPTO
     DATA_SOURCE=CRYPTO
     NEWS_QUERY=Bitcoin OR BTC OR cryptocurrency
     NEWS_KEYWORDS=Bitcoin,BTC,cryptocurrency
     MARKET_24_7=true
     MACRO_DATA_ENABLED=false

  2. START OLLAMA (if using local LLM):
     ollama serve
     ollama pull llama3.1:8b

  3. CLEAR OLD CACHED DATA:
     redis-cli FLUSHDB  # Clears Redis cache

  4. RESTART TRADING SYSTEM:
     python scripts/start_all.py

  5. UPDATE PROMPTS (for full decoupling):
     Replace hardcoded 'Bank Nifty' with '{instrument_name}'
     in prompt files under config/prompts/
""")


def main():
    """Run all diagnostics."""
    print("\n" + "=" * 70)
    print("  GenAI Trading System - LLM & Configuration Diagnostic")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)
    
    results = {}
    
    # Run all checks
    results["env"] = check_env_file()
    results["ollama"] = check_ollama()
    results["cloud_providers"] = check_cloud_providers()
    results["llm_manager"] = check_llm_manager()
    
    # Only test LLM if manager is available
    if results["llm_manager"]:
        results["llm_test"] = test_llm_call(results["llm_manager"])
    
    check_prompts()
    results["redis"] = check_redis()
    results["settings"] = check_instrument_config()
    
    # Summary
    print_header("SUMMARY", char="=")
    
    issues = []
    if not results.get("ollama") and not results.get("cloud_providers"):
        issues.append("No LLM provider available (neither Ollama nor cloud)")
    if not results.get("env"):
        issues.append("No .env configuration file")
    if results.get("settings"):
        if "NIFTY" in results["settings"].instrument_symbol.upper():
            issues.append("Still using default Bank Nifty configuration")
    
    if issues:
        print("  Issues found:")
        for issue in issues:
            print(f"    ❌ {issue}")
    else:
        print("  ✅ No critical issues found!")
    
    generate_recommendations()
    
    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
