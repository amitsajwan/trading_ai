#!/usr/bin/env python3
"""
Test script to verify Bitcoin configuration and LLM integration.
This script checks:
1. Instrument configuration (Bitcoin vs Bank Nifty)
2. Prompt placeholder substitution
3. LLM provider availability
4. Agent initialization
"""

import sys
import os
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

def test_instrument_configuration():
    """Test 1: Verify instrument is configured for Bitcoin."""
    print("\n" + "="*60)
    print("TEST 1: Instrument Configuration")
    print("="*60)
    
    try:
        from config.settings import settings
        
        print(f"✓ Instrument Name: {settings.instrument_name}")
        print(f"✓ Instrument Symbol: {settings.instrument_symbol}")
        print(f"✓ Instrument Exchange: {settings.instrument_exchange}")
        print(f"✓ Market 24/7: {settings.market_24_7}")
        print(f"✓ Macro Data Enabled: {settings.macro_data_enabled}")
        
        # Check if it's Bitcoin (not Bank Nifty)
        is_bitcoin = (
            "bitcoin" in settings.instrument_name.lower() or
            "btc" in settings.instrument_symbol.lower()
        )
        is_bank_nifty = (
            "bank nifty" in settings.instrument_name.lower() or
            "banknifty" in settings.instrument_symbol.lower()
        )
        
        if is_bitcoin:
            print("\n✅ SUCCESS: System configured for Bitcoin")
            return True
        elif is_bank_nifty:
            print("\n❌ FAIL: System still configured for Bank Nifty")
            print("   → Update INSTRUMENT_NAME and INSTRUMENT_SYMBOL in .env")
            return False
        else:
            print(f"\n⚠️  WARNING: Unknown instrument: {settings.instrument_name}")
            return True
            
    except Exception as e:
        print(f"\n❌ FAIL: Error loading settings: {e}")
        return False


def test_prompt_substitution():
    """Test 2: Verify prompts use dynamic instrument names."""
    print("\n" + "="*60)
    print("TEST 2: Prompt Placeholder Substitution")
    print("="*60)
    
    try:
        from agents.technical_agent import TechnicalAnalysisAgent
        from agents.sentiment_agent import SentimentAnalysisAgent
        from config.settings import settings
        
        # Test technical agent
        tech_agent = TechnicalAnalysisAgent()
        tech_prompt = tech_agent.system_prompt[:200]
        print(f"\n✓ Technical Agent Prompt (first 200 chars):")
        print(f"  {tech_prompt}...")
        
        # Test sentiment agent
        sent_agent = SentimentAnalysisAgent()
        sent_prompt = sent_agent.system_prompt[:200]
        print(f"\n✓ Sentiment Agent Prompt (first 200 chars):")
        print(f"  {sent_prompt}...")
        
        # Check if prompts contain the actual instrument name
        expected_instrument = settings.instrument_name
        
        if expected_instrument in tech_prompt and expected_instrument in sent_prompt:
            print(f"\n✅ SUCCESS: Prompts use '{expected_instrument}' (not hardcoded)")
            return True
        elif "Bank Nifty" in tech_prompt or "Bank Nifty" in sent_prompt:
            print(f"\n❌ FAIL: Prompts still contain hardcoded 'Bank Nifty'")
            print("   → Check if placeholder substitution is working")
            return False
        else:
            print(f"\n⚠️  WARNING: Could not verify instrument name in prompts")
            return True
            
    except Exception as e:
        print(f"\n❌ FAIL: Error initializing agents: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_provider_status():
    """Test 3: Check LLM provider availability."""
    print("\n" + "="*60)
    print("TEST 3: LLM Provider Status")
    print("="*60)
    
    try:
        from agents.llm_provider_manager import get_llm_manager
        
        manager = get_llm_manager()
        status = manager.get_provider_status()
        
        print(f"\n✓ Found {len(status)} configured providers:")
        
        available_count = 0
        for name, info in status.items():
            status_emoji = {
                "available": "✅",
                "rate_limited": "⏳",
                "error": "❌",
                "unavailable": "❌"
            }.get(info['status'], "❓")
            
            print(f"  {status_emoji} {name.upper():<12} | Status: {info['status']:<12} | Priority: {info['priority']}")
            
            if info['status'] == 'available':
                available_count += 1
                if info.get('is_current'):
                    print(f"     └─ 🎯 Currently selected provider")
        
        if available_count > 0:
            print(f"\n✅ SUCCESS: {available_count} provider(s) available")
            return True
        else:
            print(f"\n❌ FAIL: No LLM providers available")
            print("   → Add API key to .env (GROQ_API_KEY, GOOGLE_API_KEY, etc.)")
            print("   → OR install Ollama: https://ollama.com/download")
            return False
            
    except Exception as e:
        print(f"\n❌ FAIL: Error checking LLM providers: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_call():
    """Test 4: Try a simple LLM call."""
    print("\n" + "="*60)
    print("TEST 4: LLM Call Test")
    print("="*60)
    
    try:
        from agents.llm_provider_manager import get_llm_manager
        from config.settings import settings
        
        manager = get_llm_manager()
        
        # Simple test prompt
        system_prompt = f"You are a helpful assistant for {settings.instrument_name} trading."
        user_message = f"In one sentence, what is {settings.instrument_name}?"
        
        print(f"\n✓ Attempting LLM call...")
        print(f"  System: {system_prompt[:60]}...")
        print(f"  User: {user_message}")
        
        response = manager.call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.3,
            max_tokens=100
        )
        
        print(f"\n✓ LLM Response:")
        print(f"  {response[:200]}...")
        
        # Check if response mentions the instrument
        instrument_name = settings.instrument_name.lower()
        if instrument_name in response.lower():
            print(f"\n✅ SUCCESS: LLM responded with context about {settings.instrument_name}")
            return True
        else:
            print(f"\n⚠️  WARNING: LLM response doesn't mention {settings.instrument_name}")
            print("   (This might be ok, depends on the response)")
            return True
            
    except Exception as e:
        print(f"\n❌ FAIL: LLM call failed: {e}")
        error_str = str(e)
        
        if "API key" in error_str or "api_key" in error_str:
            print("   → Add a valid API key to .env")
        elif "No available LLM providers" in error_str:
            print("   → Configure at least one LLM provider")
        elif "rate limit" in error_str.lower():
            print("   → Rate limited - try another provider")
        
        return False


def test_prompt_files():
    """Test 5: Check prompt files use placeholders."""
    print("\n" + "="*60)
    print("TEST 5: Prompt File Placeholder Check")
    print("="*60)
    
    try:
        from pathlib import Path
        
        prompts_dir = Path(__file__).parent / "config" / "prompts"
        prompt_files = list(prompts_dir.glob("*.txt"))
        
        print(f"\n✓ Found {len(prompt_files)} prompt files:")
        
        issues = []
        for prompt_file in prompt_files:
            content = prompt_file.read_text()
            has_placeholder = "{instrument_name}" in content
            has_hardcoded = "Bank Nifty" in content or "BANKNIFTY" in content
            
            if has_placeholder and not has_hardcoded:
                print(f"  ✅ {prompt_file.name:<30} | Uses placeholder")
            elif has_placeholder and has_hardcoded:
                print(f"  ⚠️  {prompt_file.name:<30} | Has both placeholder AND hardcoded")
                issues.append(prompt_file.name)
            elif not has_placeholder and has_hardcoded:
                print(f"  ❌ {prompt_file.name:<30} | Still hardcoded")
                issues.append(prompt_file.name)
            else:
                print(f"  ❓ {prompt_file.name:<30} | No instrument reference")
        
        if issues:
            print(f"\n⚠️  WARNING: {len(issues)} file(s) may have issues:")
            for issue in issues:
                print(f"     - {issue}")
            return False
        else:
            print(f"\n✅ SUCCESS: All prompt files use placeholders correctly")
            return True
            
    except Exception as e:
        print(f"\n❌ FAIL: Error checking prompt files: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 BITCOIN TRADING SYSTEM - LLM & CONFIGURATION TEST")
    print("="*60)
    print("\nThis script verifies:")
    print("  1. Instrument is configured for Bitcoin (not Bank Nifty)")
    print("  2. Prompts use dynamic instrument names")
    print("  3. LLM providers are available")
    print("  4. LLM calls work correctly")
    print("  5. Prompt files use placeholders")
    
    results = {}
    
    # Run tests
    results['config'] = test_instrument_configuration()
    results['substitution'] = test_prompt_substitution()
    results['providers'] = test_llm_provider_status()
    results['llm_call'] = test_llm_call()
    results['prompt_files'] = test_prompt_files()
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status:<10} | {test_name.replace('_', ' ').title()}")
    
    print(f"\n{'='*60}")
    print(f"📈 RESULTS: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 SUCCESS! System is fully configured for Bitcoin trading.")
        print("\nNext steps:")
        print("  1. Start the trading system: python3 start_trading_system.py")
        print("  2. Check logs for Bitcoin analysis (not Bank Nifty)")
        print("  3. Consider installing Ollama for local LLM")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        print("\nCommon fixes:")
        print("  1. Add LLM API key to .env (GROQ_API_KEY or GOOGLE_API_KEY)")
        print("  2. Verify .env has INSTRUMENT_NAME=Bitcoin")
        print("  3. Install dependencies: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
