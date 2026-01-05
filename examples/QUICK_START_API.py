"""
Quick Start Guide for API Management System
"""

# ============================================================================
# QUICK USAGE EXAMPLES
# ============================================================================

# 1. BASIC LLM REQUEST
# ----------------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv()

from utils.request_router import RequestRouter

router = RequestRouter()
result = router.make_llm_request(
    prompt="Explain Bitcoin in one sentence.",
    max_tokens=50,
    temperature=0.3
)

print(f"Provider: {result['provider']}")
print(f"Response: {result['response']['text']}")


# 2. CHECK USAGE STATUS
# ----------------------------------------------------------------------------
from utils.usage_monitor import UsageMonitor

monitor = UsageMonitor()
monitor.print_compact_report()  # Quick overview
monitor.print_usage_report()     # Full detailed report
monitor.check_alerts()           # Check for warnings


# 3. FORCE SPECIFIC PROVIDER
# ----------------------------------------------------------------------------
result = router.make_llm_request(
    prompt="What is cryptocurrency?",
    max_tokens=100,
    preferred_provider="groq"  # Try Groq first, fallback if unavailable
)


# 4. INTEGRATE INTO YOUR AGENTS
# ----------------------------------------------------------------------------
class YourAgent:
    def __init__(self):
        from utils.request_router import RequestRouter
        self.llm = RequestRouter()
    
    def analyze(self, data):
        prompt = f"Analyze this data: {data}"
        result = self.llm.make_llm_request(prompt=prompt, max_tokens=500)
        return result['response']['text']


# ============================================================================
# COMMAND LINE USAGE
# ============================================================================

# View usage report
# python utils/usage_monitor.py

# Run tests
# python test_api_system.py

# Export usage report
# python utils/usage_monitor.py --export report.txt

# Compact view
# python utils/usage_monitor.py --compact


# ============================================================================
# PROVIDER PRIORITY (Auto-selected in this order)
# ============================================================================
# 1. Cohere    - 5,000,000 tokens/month (BEST - ~500 days)
# 2. AI21      - 300,000 tokens/month   (~30 days)
# 3. Groq      - 14,400 requests/day    (Resets daily)
# 4. HuggingFace - 30,000 tokens/month  (~3 days)
# 5. OpenAI    - 5,000 tokens once      (~0.5 days)
# 6. Google    - 5,000 requests/month   (~0.5 days)
#
# TOTAL ESTIMATED: ~535 days with current usage


# ============================================================================
# KEY FEATURES
# ============================================================================
# ✅ Automatic provider selection based on priority
# ✅ Automatic fallback if a provider fails
# ✅ Usage tracking saved to api_usage.json
# ✅ Auto-reset daily/monthly limits
# ✅ Alerts at 75%, 90%, 95% usage
# ✅ Support for 6 different providers


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# Check what provider will be used next:
from utils.usage_monitor import UsageMonitor
monitor = UsageMonitor()
best = monitor.get_best_provider()
print(f"Best provider: {best}")

# View detailed stats:
stats = router.get_stats()
for provider, info in stats.items():
    print(f"{provider}: {info['usage']}/{info['limit']} tokens")

# Reset a provider (for testing):
from utils.api_manager import APIManager
manager = APIManager()
manager.reset_provider_usage("groq")


# ============================================================================
# INSTALLATION
# ============================================================================
# pip install cohere groq openai google-genai requests python-dotenv


# ============================================================================
# FILES
# ============================================================================
# utils/api_manager.py    - Core API management
# utils/request_router.py - Request routing
# utils/usage_monitor.py  - Usage monitoring
# test_api_system.py      - Test suite
# api_usage.json          - Usage tracking (auto-created)
# .env                    - API keys configuration
