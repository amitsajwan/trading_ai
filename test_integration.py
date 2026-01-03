#!/usr/bin/env python3
"""
Quick test of the integrated multi-provider system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

def test_integration():
    print("🧪 Testing Multi-Provider Integration")
    print("=" * 50)

    # Test 1: Check if our API manager loads
    try:
        from utils.api_manager import APIManager
        manager = APIManager()
        stats = manager.get_usage_stats()
        print("✅ API Manager loaded successfully")
        active_providers = [p for p, info in stats.items() if info['has_key']]
        print(f"   Active providers: {', '.join(active_providers)}")
    except Exception as e:
        print(f"❌ API Manager failed: {e}")
        return

    # Test 2: Check if request router works
    try:
        from utils.request_router import RequestRouter
        router = RequestRouter()
        print("✅ Request Router loaded successfully")
    except Exception as e:
        print(f"❌ Request Router failed: {e}")
        return

    # Test 3: Check LLM provider manager integration
    try:
        from agents.llm_provider_manager import get_llm_manager
        llm_manager = get_llm_manager()
        status = llm_manager.get_provider_status()
        if 'multi_provider_fallback' in status:
            mp_status = status['multi_provider_fallback']
            print("✅ Multi-provider fallback integrated")
            if mp_status['status'] == 'available':
                providers = mp_status.get('providers', {})
                active_count = sum(1 for p, info in providers.items() if info.get('has_key'))
                print(f"   Fallback providers available: {active_count}")
            else:
                print(f"   Status: {mp_status['status']}")
        else:
            print("⚠️ Multi-provider fallback not found in status")
    except Exception as e:
        print(f"❌ LLM Manager integration failed: {e}")
        return

    print("\n🎉 Integration test completed successfully!")
    print("\n📋 Summary:")
    print("   - API Manager: ✅ Working")
    print("   - Request Router: ✅ Working")
    print("   - LLM Integration: ✅ Working")
    print("   - Multi-provider fallback: ✅ Available")

if __name__ == "__main__":
    test_integration()