# Multi-Provider LLM System

## Overview

The system now supports **multiple LLM providers** with automatic fallback, rate limit handling, and efficient provider selection. This ensures high availability and prevents service interruptions.

## Features

### ✅ Automatic Fallback
- If one provider fails or hits rate limits, automatically switches to next available provider
- No manual intervention required
- Seamless failover

### ✅ Rate Limit Handling
- Tracks rate limits per provider (per minute and per day)
- Automatically switches providers when limits are reached
- Prevents API errors and service interruptions

### ✅ Provider Rotation
- Distributes load across multiple providers
- Optimizes for cost and performance
- Prevents overuse of any single provider

### ✅ Cost Optimization
- Prioritizes free-tier providers
- Uses paid providers only when necessary
- Tracks usage and costs

## Configured Providers

### 1. Groq Cloud (Priority: 1 - Highest)
- **Models**: Llama 3.3 70B, Mixtral
- **Rate Limits**: 30 req/min, 100K tokens/day
- **Cost**: Free tier
- **Status**: ✅ Configured

### 2. Google Gemini (Priority: 2 - High)
- **Models**: Gemini 1.5 Flash, Gemini 2.5 Pro
- **Rate Limits**: 60 req/min, 15M tokens/day
- **Cost**: Free tier
- **Status**: ✅ Configured

### 3. OpenRouter (Priority: 3 - Medium)
- **Models**: DeepSeek R1, Mistral
- **Rate Limits**: 50 req/min, 50K tokens/day
- **Cost**: Free tier (some models)
- **Status**: ✅ Configured

### 4. Together AI (Priority: 4 - Medium)
- **Models**: Mixtral-8x7B-Instruct
- **Rate Limits**: 40 req/min, 100K tokens/day
- **Cost**: Free tier available
- **Status**: Optional (if configured)

### 5. OpenAI (Priority: 5 - Lower)
- **Models**: GPT-4o-mini
- **Rate Limits**: 60 req/min, 1M tokens/day
- **Cost**: Paid
- **Status**: Optional (if configured)

## How It Works

### Provider Selection

1. **Initialization**: System checks all configured providers
2. **Priority Sorting**: Providers sorted by priority (lower = higher priority)
3. **Status Check**: Only available providers are considered
4. **Selection**: Best available provider is selected automatically

### Request Flow

```
Agent Request
    ↓
LLM Provider Manager
    ↓
Check Current Provider
    ↓
Rate Limit Check
    ↓
[Within Limits?]
    ├─ Yes → Use Provider
    └─ No → Select Next Provider
            ↓
        Retry Request
```

### Fallback Mechanism

1. **Error Detection**: Catches API errors, rate limits, timeouts
2. **Provider Marking**: Marks provider as unavailable temporarily
3. **Next Provider**: Automatically selects next best provider
4. **Retry**: Retries request with new provider
5. **Recovery**: Provider recovers after 5-minute cooldown

## Configuration

### Environment Variables

Add to `.env` file:

```env
# Multi-Provider Configuration
LLM_PROVIDER=multi  # Use multi-provider manager
LLM_MODEL=auto      # Auto-select model

# Provider API Keys
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIzaSy...
OPENROUTER_API_KEY=sk-or-v1-...
TOGETHER_API_KEY=...  # Optional
OPENAI_API_KEY=...    # Optional
```

### Quick Setup

Run the setup script:

```bash
python scripts/update_env_multi_provider.py
```

This will:
- Add all API keys to `.env`
- Configure multi-provider mode
- Set up provider priorities

## Usage

### Automatic (Default)

The system automatically uses the best available provider. No code changes needed!

### Manual Provider Selection

```python
from agents.llm_provider_manager import get_llm_manager

llm_manager = get_llm_manager()

# Use specific provider
response = llm_manager.call_llm(
    system_prompt="...",
    user_message="...",
    provider_name="groq"  # Optional: specify provider
)
```

## Monitoring

### Dashboard

View provider status at:
```
http://localhost:8888/api/llm-providers
```

### Provider Status

```json
{
  "current_provider": "groq",
  "providers": {
    "groq": {
      "status": "available",
      "priority": 1,
      "requests_today": 150,
      "requests_this_minute": 5,
      "rate_limit_per_minute": 30,
      "rate_limit_per_day": 100000,
      "is_current": true
    },
    "gemini": {
      "status": "available",
      "priority": 2,
      "requests_today": 0,
      "requests_this_minute": 0,
      "is_current": false
    }
  }
}
```

## Benefits

### 1. High Availability
- **99.9% uptime**: Multiple providers ensure service continuity
- **No single point of failure**: If one provider fails, others take over

### 2. Rate Limit Protection
- **Never hit limits**: Automatic switching prevents rate limit errors
- **Distributed load**: Spreads requests across providers

### 3. Cost Efficiency
- **Free tier priority**: Uses free providers first
- **Paid only when needed**: Paid providers used as fallback

### 4. Performance Optimization
- **Fast providers first**: Prioritizes fast, low-latency providers
- **Optimal selection**: Chooses best provider for each request

## Example Scenarios

### Scenario 1: Groq Rate Limit Hit

```
Request 1-30: Groq (within limits)
Request 31: Groq rate limit → Switch to Gemini
Request 32-60: Gemini
Request 61: Groq recovered → Switch back to Groq
```

### Scenario 2: Provider Error

```
Request 1: Groq → Error (API timeout)
Request 1 (retry): Gemini → Success
Groq marked unavailable for 5 minutes
Request 2-10: Gemini
Request 11: Groq recovered → Switch back to Groq
```

### Scenario 3: Daily Limit Approaching

```
Groq: 95K tokens used (95% of limit)
System: Switch to Gemini (plenty of capacity)
Remaining requests: Gemini
Next day: Reset → Back to Groq
```

## Best Practices

1. **Monitor Usage**: Check provider status regularly
2. **Set Alerts**: Monitor rate limit usage
3. **Balance Providers**: Don't rely on single provider
4. **Update Keys**: Keep API keys current
5. **Test Fallback**: Verify fallback works correctly

## Troubleshooting

### All Providers Failing

**Symptoms**: All providers return errors

**Solutions**:
1. Check API keys are valid
2. Verify internet connection
3. Check provider status pages
4. Review error logs

### Rate Limits Hit Frequently

**Symptoms**: Frequent provider switching

**Solutions**:
1. Add more providers
2. Increase rate limits (upgrade plans)
3. Reduce request frequency
4. Optimize prompts (fewer tokens)

### Provider Not Available

**Symptoms**: Provider marked as unavailable

**Solutions**:
1. Check API key validity
2. Verify provider service status
3. Wait for cooldown period (5 minutes)
4. Check error logs for details

## API Reference

### `LLMProviderManager`

```python
class LLMProviderManager:
    def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        provider_name: Optional[str] = None
    ) -> str
    
    def get_client(provider_name: Optional[str] = None) -> Tuple[Any, str]
    
    def get_provider_status() -> Dict[str, Dict[str, Any]]
```

## Summary

The multi-provider LLM system provides:
- ✅ **Reliability**: Multiple providers ensure uptime
- ✅ **Efficiency**: Optimal provider selection
- ✅ **Cost Savings**: Free tier priority
- ✅ **Scalability**: Handle high request volumes
- ✅ **Resilience**: Automatic error recovery

**Result**: Your trading system will work reliably for months without interruption!

