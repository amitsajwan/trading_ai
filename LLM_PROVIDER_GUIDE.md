# LLM Provider Options - Rate Limit Solutions

## Current Issue
Groq free tier has a **100K tokens/day limit**. You've hit this limit.

## Available Providers

### 1. **OpenAI** (Recommended for production)
**Pros:**
- High quality models (GPT-4o, GPT-4 Turbo)
- No daily token limits (pay per use)
- Reliable and fast
- Good for production trading systems

**Cons:**
- Costs money (~$0.15-30 per 1M tokens depending on model)
- Requires credit card

**Setup:**
```bash
# 1. Get API key from: https://platform.openai.com/api-keys
# 2. Add to .env file:
OPENAI_API_KEY=sk-your-key-here

# 3. Switch provider:
python scripts/switch_llm_provider.py openai
```

**Models:**
- `gpt-4o-mini` - Cost-effective ($0.15/$0.60 per 1M tokens)
- `gpt-4o` - Best quality ($2.50/$10 per 1M tokens)
- `gpt-4-turbo` - Balanced ($10/$30 per 1M tokens)

### 2. **Azure OpenAI**
**Pros:**
- Enterprise-grade
- Good for Azure users
- Pay per use

**Cons:**
- Requires Azure subscription
- More complex setup

**Setup:**
```bash
# Add to .env:
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Switch:
python scripts/switch_llm_provider.py azure
```

### 3. **Groq** (Current - Upgrade tier)
**Pros:**
- Very fast inference
- Free tier available

**Cons:**
- Free tier: 100K tokens/day limit (you've hit this)
- Need to upgrade for more

**Upgrade:**
1. Visit: https://console.groq.com/settings/billing
2. Upgrade to Dev Tier or higher
3. Keep using Groq

## Quick Switch Commands

```bash
# Switch to OpenAI (if you have API key)
python scripts/switch_llm_provider.py openai

# Switch to Azure (if configured)
python scripts/switch_llm_provider.py azure

# Switch back to Groq
python scripts/switch_llm_provider.py groq

# Check current config
python scripts/switch_llm_provider.py
```

## Cost Comparison

**For 1M tokens (approximate):**
- Groq Free: $0 (100K/day limit) ❌ Hit limit
- Groq Paid: ~$0.27 (no daily limit) ✅
- OpenAI GPT-4o-mini: $0.15/$0.60 ✅ Cost-effective
- OpenAI GPT-4o: $2.50/$10 ✅ Best quality
- Azure: Varies by subscription

## Recommendation

**For immediate use:**
1. **OpenAI GPT-4o-mini** - Best balance of cost and quality
   - Add `OPENAI_API_KEY` to `.env`
   - Run: `python scripts/switch_llm_provider.py openai`

**For long-term:**
- Upgrade Groq to paid tier (if you like speed)
- Or use OpenAI GPT-4o-mini (cost-effective)

## After Switching

Restart your trading service:
```bash
# Stop current services
Get-Process python | Stop-Process -Force

# Start again
python scripts/start_all.py
```

The agents will now use the new provider!

