# Multi-Provider API Management System

## Overview
A comprehensive system to manage multiple LLM API providers with automatic fallback, usage tracking, and cost optimization. Designed to maximize the lifespan of free-tier API keys.

## Features
- ✅ **Multi-Provider Support**: Cohere, AI21, Groq, HuggingFace, OpenAI, Google Gemini
- ✅ **Automatic Fallback**: Switches to next provider if one fails or reaches limit
- ✅ **Priority-Based Routing**: Uses most cost-effective providers first
- ✅ **Usage Tracking**: Persistent tracking of token usage across sessions
- ✅ **Smart Reset**: Automatically resets daily/monthly limits
- ✅ **Real-time Monitoring**: View usage stats and estimates anytime
- ✅ **Alerts**: Warnings when approaching API limits

## Provider Priority (Free Tier)

1. **Cohere** (Priority 1) - 5,000,000 tokens/month - BEST VALUE
2. **AI21** (Priority 2) - 300,000 tokens/month
3. **Groq** (Priority 3) - 14,400 requests/day (resets daily)
4. **HuggingFace** (Priority 4) - 30,000 tokens/month
5. **OpenAI** (Priority 5) - 5,000 tokens (one-time free credit)
6. **Google** (Priority 6) - 5,000 requests/month (NLP tasks)

## Installation

### Required Dependencies
```bash
pip install python-dotenv
pip install cohere
pip install groq
pip install openai
pip install google-genai
pip install requests
```

### Environment Setup
All API keys are configured in `.env` file:
```bash
# Already configured in your .env:
COHERE_API_KEY='xXWGFBOCljq4vp5YNKJz7XTHAcPCv3e7lPDNsFHj'
AI21_API_KEY='e7616a6d-78bd-47dc-b076-539bacd710d9'
GROQ_API_KEY='GROQ_API_KEY_REDACTED'
OPENAI_API_KEY='sk-proj-...'
HUGGINGFACE_API_KEY='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'
GOOGLE_API_KEY='AIzaSyCEYoOsbt-FXzyV3Kh9i_fwmhvF3EsZSME'
```

## Usage

### Basic Usage

```python
from utils.request_router import RequestRouter

# Initialize router
router = RequestRouter()

# Make a request (auto-selects best provider)
result = router.make_llm_request(
    prompt="Explain Bitcoin in one sentence.",
    max_tokens=50,
    temperature=0.3
)

print(f"Provider: {result['provider']}")
print(f"Response: {result['response']['text']}")
print(f"Tokens: {result['tokens_used']}")
```

### With Preferred Provider

```python
# Force a specific provider (with fallback)
result = router.make_llm_request(
    prompt="What is cryptocurrency?",
    max_tokens=100,
    preferred_provider="groq"  # Will use Groq if available
)
```

### Monitor Usage

```python
from utils.usage_monitor import UsageMonitor

# Create monitor
monitor = UsageMonitor()

# Show full report
monitor.print_usage_report(avg_tokens_per_day=10000)

# Check alerts
monitor.check_alerts()

# Show compact status
monitor.print_compact_report()

# Export report to file
monitor.export_usage_report("usage_report.txt")
```

### Command Line Usage

```bash
# Run full test suite
python test_api_system.py

# Run specific test
python test_api_system.py --test single
python test_api_system.py --test report

# Monitor usage
python utils/usage_monitor.py

# Monitor with custom token estimate
python utils/usage_monitor.py --avg-tokens 15000

# Compact report
python utils/usage_monitor.py --compact

# Export report
python utils/usage_monitor.py --export my_report.txt
```

## How It Works

### 1. Request Flow
```
User Request
    ↓
Request Router
    ↓
API Manager (select best provider based on priority & availability)
    ↓
Provider API Call (Cohere → AI21 → Groq → HuggingFace → OpenAI)
    ↓
Response + Usage Logging
    ↓
Save to api_usage.json
```

### 2. Provider Selection Logic
1. Check if provider has API key
2. Check if provider has remaining quota
3. Select highest priority available provider
4. If preferred provider specified, try it first
5. On failure, automatically fallback to next provider

### 3. Usage Tracking
- Tracks token usage per provider
- Saves to `api_usage.json` after each request
- Automatically resets based on provider reset period:
  - Daily: Groq
  - Monthly: Cohere, AI21, HuggingFace, Google
  - Once: OpenAI (free credit)

## Estimated Lifespan

With **10,000 tokens/day** usage:
- **Cohere**: ~500 days (5M tokens/month)
- **AI21**: ~30 days (300K tokens/month)
- **Groq**: Unlimited (resets daily at 14.4K requests/day)
- **HuggingFace**: ~3 days (30K tokens/month)
- **OpenAI**: ~0.5 days (5K tokens one-time)
- **Google**: ~500 days for NLP tasks (5K requests/month)

**Total Estimated Runtime**: ~500+ days (with Groq's daily reset providing continuous backup)

## Integration with Existing System

### Update Your Agent/LLM Calls

Replace existing LLM calls with the router:

```python
# OLD CODE:
from groq import Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
response = client.chat.completions.create(...)

# NEW CODE:
from utils.request_router import RequestRouter
router = RequestRouter()
result = router.make_llm_request(
    prompt=your_prompt,
    max_tokens=1000,
    temperature=0.3
)
text = result['response']['text']
```

### In Your Agents

```python
# In agents/base_agent.py or similar
class BaseAgent:
    def __init__(self):
        from utils.request_router import RequestRouter
        self.llm_router = RequestRouter()
    
    def call_llm(self, prompt, max_tokens=1000):
        result = self.llm_router.make_llm_request(
            prompt=prompt,
            max_tokens=max_tokens
        )
        return result['response']['text']
```

## Files Created

1. **utils/api_manager.py** - Core API management & tracking
2. **utils/request_router.py** - Request routing & provider calls
3. **utils/usage_monitor.py** - Usage monitoring & reporting
4. **test_api_system.py** - Test suite
5. **api_usage.json** - Usage tracking database (auto-created)

## Configuration

All limits are configurable in `.env`:

```bash
# Usage Limits (tokens/requests per month)
HUGGINGFACE_LIMIT=30000
GOOGLE_LIMIT=5000
GROQ_LIMIT=14400
COHERE_LIMIT=5000000
OPENAI_LIMIT=5000
AI21_LIMIT=300000
```

## Best Practices

1. **Monitor Regularly**: Run `python utils/usage_monitor.py` daily
2. **Set Alerts**: The system auto-alerts at 75%, 90%, 95% usage
3. **Prioritize Wisely**: Cohere and Groq are your best free options
4. **Save OpenAI**: Only use OpenAI as last resort (limited free credit)
5. **Track Usage**: Check `api_usage.json` to see historical patterns

## Troubleshooting

### Provider Not Working
```python
# Check provider status
from utils.usage_monitor import UsageMonitor
monitor = UsageMonitor()
monitor.print_usage_report()
```

### Reset Usage (Testing)
```python
from utils.api_manager import APIManager
manager = APIManager()
manager.reset_provider_usage("groq")  # Reset specific provider
```

### Missing Dependencies
```bash
# Install all at once
pip install cohere groq openai google-genai requests python-dotenv
```

## Advanced Features

### Custom Provider Configuration
Edit `utils/api_manager.py` to add new providers or modify limits:

```python
self.providers = {
    "your_provider": {
        "key": os.getenv("YOUR_PROVIDER_KEY"),
        "limit": 100000,
        "priority": 1,  # Lower = higher priority
        "type": "llm",
        "reset_period": "monthly"
    }
}
```

### Export Usage Reports
```python
monitor = UsageMonitor()
monitor.export_usage_report("weekly_report.txt")
```

## Security Notes

- API keys are stored in `.env` (never commit to git)
- Usage data saved locally in `api_usage.json`
- No external logging or tracking
- All API calls use HTTPS

## Support

For issues or questions:
1. Check `api_usage.json` for current state
2. Run `python test_api_system.py --test report`
3. Review provider documentation for API limits

---

**Status**: ✅ Fully Implemented and Ready to Use

**Estimated Lifespan**: 500+ days of continuous operation with current free-tier limits
