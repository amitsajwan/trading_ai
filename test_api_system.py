"""
Test Script for Multi-Provider API Management System
Tests the API routing, fallback, and usage tracking
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from utils.request_router import RequestRouter
from utils.usage_monitor import UsageMonitor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_single_request():
    """Test a single LLM request"""
    print("\n" + "="*70)
    print("TEST 1: Single LLM Request")
    print("="*70)
    
    router = RequestRouter()
    monitor = UsageMonitor()
    
    # Show initial state
    print("\n📊 Initial State:")
    monitor.print_compact_report()
    
    # Make a test request
    try:
        print("\n🔄 Making test request...")
        result = router.make_llm_request(
            prompt="Explain Bitcoin in one sentence.",
            max_tokens=50,
            temperature=0.3
        )
        
        print(f"\n✅ SUCCESS!")
        print(f"   Provider: {result['provider']}")
        print(f"   Model: {result['model']}")
        print(f"   Tokens Used: {result['tokens_used']}")
        print(f"   Response: {result['response']['text'][:200]}...")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
    
    # Show updated state
    print("\n📊 Updated State:")
    monitor.print_compact_report()


def test_multiple_requests():
    """Test multiple LLM requests to see fallback"""
    print("\n" + "="*70)
    print("TEST 2: Multiple LLM Requests (Testing Fallback)")
    print("="*70)
    
    router = RequestRouter()
    monitor = UsageMonitor()
    
    test_prompts = [
        "What is cryptocurrency?",
        "Explain blockchain technology.",
        "What are smart contracts?",
        "Define DeFi.",
        "What is Bitcoin halving?"
    ]
    
    results = []
    for i, prompt in enumerate(test_prompts, 1):
        try:
            print(f"\n🔄 Request {i}/{len(test_prompts)}: {prompt[:30]}...")
            result = router.make_llm_request(
                prompt=prompt,
                max_tokens=100,
                temperature=0.3
            )
            results.append({
                "prompt": prompt,
                "provider": result['provider'],
                "tokens": result['tokens_used'],
                "success": True
            })
            print(f"   ✅ Success with {result['provider']} ({result['tokens_used']} tokens)")
        except Exception as e:
            results.append({
                "prompt": prompt,
                "error": str(e),
                "success": False
            })
            print(f"   ❌ Failed: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 RESULTS SUMMARY:")
    print("="*70)
    successful = sum(1 for r in results if r['success'])
    print(f"   Total Requests: {len(results)}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {len(results) - successful}")
    
    if successful > 0:
        providers_used = {}
        for r in results:
            if r['success']:
                provider = r['provider']
                providers_used[provider] = providers_used.get(provider, 0) + 1
        
        print("\n   Providers Used:")
        for provider, count in providers_used.items():
            print(f"      {provider}: {count} requests")
    
    # Show usage
    monitor.print_compact_report()


def test_provider_preference():
    """Test preferred provider selection"""
    print("\n" + "="*70)
    print("TEST 3: Preferred Provider Selection")
    print("="*70)
    
    router = RequestRouter()
    
    # Get available providers
    available = router.api_manager.get_available_providers("llm")
    print(f"\n📋 Available Providers: {[p[0] for p in available]}")
    
    if len(available) > 1:
        # Try requesting with specific provider
        preferred = available[1][0]  # Second provider
        print(f"\n🎯 Requesting with preferred provider: {preferred}")
        
        try:
            result = router.make_llm_request(
                prompt="What is AI?",
                max_tokens=50,
                temperature=0.3,
                preferred_provider=preferred
            )
            print(f"   ✅ Used provider: {result['provider']}")
            assert result['provider'] == preferred, "Wrong provider used!"
        except Exception as e:
            print(f"   ❌ Failed: {e}")
    else:
        print("   ⚠️ Only one provider available, skipping preference test")


def test_usage_tracking():
    """Test usage tracking and persistence"""
    print("\n" + "="*70)
    print("TEST 4: Usage Tracking & Persistence")
    print("="*70)
    
    router = RequestRouter()
    monitor = UsageMonitor()
    
    # Check if usage file exists
    usage_file = Path("api_usage.json")
    if usage_file.exists():
        print(f"\n📁 Usage file found: {usage_file}")
        import json
        with open(usage_file, 'r') as f:
            data = json.load(f)
        print(f"   Last Reset: {data.get('last_reset', 'N/A')}")
        print(f"   Providers Tracked: {len(data.get('providers', {}))}")
    else:
        print("\n📝 No usage file found (will be created on first use)")
    
    # Make a request to update tracking
    try:
        print("\n🔄 Making request to update tracking...")
        result = router.make_llm_request(
            prompt="Test tracking",
            max_tokens=20,
            temperature=0.3
        )
        print(f"   ✅ Request completed with {result['provider']}")
        
        # Verify file was updated
        if usage_file.exists():
            print(f"   ✅ Usage file updated")
        else:
            print(f"   ⚠️ Usage file not created")
            
    except Exception as e:
        print(f"   ❌ Request failed: {e}")


def test_full_report():
    """Test full usage report"""
    print("\n" + "="*70)
    print("TEST 5: Full Usage Report")
    print("="*70)
    
    monitor = UsageMonitor()
    
    # Show full report
    monitor.print_usage_report(avg_tokens_per_day=10000)
    
    # Check for alerts
    monitor.check_alerts()
    
    # Show best provider
    best = monitor.get_best_provider()
    if best:
        print(f"\n🏆 Best Available Provider: {best}")
    else:
        print("\n⚠️ No providers available")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 MULTI-PROVIDER API MANAGEMENT SYSTEM - TEST SUITE")
    print("="*70)
    
    tests = [
        ("Single Request", test_single_request),
        ("Multiple Requests", test_multiple_requests),
        ("Provider Preference", test_provider_preference),
        ("Usage Tracking", test_usage_tracking),
        ("Full Report", test_full_report)
    ]
    
    for name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            logger.error(f"Test '{name}' failed with error: {e}", exc_info=True)
    
    print("\n" + "="*70)
    print("✅ TEST SUITE COMPLETED")
    print("="*70 + "\n")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test API Management System")
    parser.add_argument(
        "--test",
        type=str,
        choices=["single", "multiple", "preference", "tracking", "report", "all"],
        default="all",
        help="Which test to run"
    )
    
    args = parser.parse_args()
    
    if args.test == "single":
        test_single_request()
    elif args.test == "multiple":
        test_multiple_requests()
    elif args.test == "preference":
        test_provider_preference()
    elif args.test == "tracking":
        test_usage_tracking()
    elif args.test == "report":
        test_full_report()
    else:
        run_all_tests()


if __name__ == "__main__":
    main()
