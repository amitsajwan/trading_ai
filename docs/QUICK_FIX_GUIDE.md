# Quick Fix Guide - Get Agents Running

## Problem
Your agents are not running due to:
1. ❌ Model too slow (70B model takes 10-60 seconds per call)
2. ❌ Rate limits hit quickly (30/minute with 10 agents = instant rate limit)
3. ❌ Trading loop times out (5 minute timeout, but execution takes 10+ minutes)

## Solution (5 Minutes Setup)

### Step 1: Use Faster Model ⚡ **CRITICAL**

Edit your `.env` file (or create from `.env.optimized`):

```bash
# Change FROM:
LLM_MODEL=llama-3.3-70b-versatile

# Change TO:
LLM_MODEL=llama-3.1-8b-instant
```

**Result**: 6-12x faster (2-5 seconds vs 10-60 seconds per call)

---

### Step 2: Add Fallback Provider (Recommended)

Get a **free** Google Gemini API key (takes 2 minutes):

1. Visit: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key

Add to `.env`:
```bash
GOOGLE_API_KEY=your_key_here
```

**Result**: Automatic fallback when Groq is rate-limited

---

### Step 3: Test the Fix

Run your trading system:
```bash
python start_trading_system.py
```

**Expected results**:
- ✅ Agents complete in 30-90 seconds (was 5+ minutes or timeout)
- ✅ No more timeouts
- ✅ Fewer rate limit errors
- ✅ System runs reliably

---

## Complete Optimized Configuration

Copy `.env.optimized` to `.env` for best results:

```bash
cp .env.optimized .env
# Edit .env and add your API keys
```

**Minimum required** (just Groq):
```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_key_here
```

**Recommended** (Groq + Gemini fallback):
```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_google_key
```

**Best** (3 providers for maximum stability):
```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_google_key
OPENROUTER_API_KEY=your_openrouter_key
```

---

## Model Comparison

### Current (SLOW):
- Model: `llama-3.3-70b-versatile`
- Speed: 10-60 seconds per call
- 10 agents × 30 seconds = 300 seconds (5 minutes)
- **Result**: Timeouts, rate limits, agents don't complete

### Fixed (FAST):
- Model: `llama-3.1-8b-instant`
- Speed: 2-5 seconds per call
- 10 agents × 4 seconds = 40 seconds
- **Result**: ✅ Completes successfully, no timeouts

---

## Free API Keys (No Credit Card Required)

### 1. Groq (Primary - FASTEST)
- URL: https://console.groq.com/keys
- Speed: ⚡⚡⚡ (2-5 sec)
- Limit: 30/min
- Models: llama-3.1-8b-instant (recommended)

### 2. Google Gemini (Fallback - GENEROUS)
- URL: https://makersuite.google.com/app/apikey
- Speed: ⚡⚡⚡ (2-5 sec)
- Limit: 60/min
- Models: gemini-flash-latest (auto)

### 3. OpenRouter (Extra - FREE MODELS)
- URL: https://openrouter.ai/keys
- Speed: ⚡⚡ (5-10 sec)
- Limit: 50/min
- Models: llama-3.2-3b-instruct:free

**Total capacity**: 30 + 60 + 50 = 140 requests/minute 🚀

---

## Verify the Fix

### Before Fix:
```
🔄 [LOOP #1] Running trading analysis...
🔵 [technical_agent] Calling LLM...
⏳ (30 seconds...)
❌ [TRADING_LOOP] Analysis timed out after 5 minutes!
```

### After Fix:
```
🔄 [LOOP #1] Running trading analysis...
🔵 [technical_agent] Calling LLM...
✅ [technical_agent] LLM response received (1250 chars) in 3.2s
✅ [GRAPH] technical_analysis node completed
... (all agents complete)
✅ [LOOP #1] Analysis completed successfully
⏳ Next analysis in 60 seconds...
```

---

## Still Having Issues?

### Issue: "No available LLM providers"
**Fix**: Check your API keys are set in `.env`

```bash
# Check if keys are loaded
python -c "from config.settings import settings; print('Groq:', 'SET' if settings.groq_api_key else 'NOT SET')"
```

### Issue: "Rate limit exceeded"
**Fix**: Add more fallback providers (Gemini + OpenRouter)

### Issue: Still timing out
**Fix**: Temporarily increase timeout in `services/trading_service.py`:
```python
timeout=600.0  # 10 minutes (line 299)
```

### Issue: "All LLM providers failed"
**Fix**: 
1. Check internet connection
2. Verify API keys are valid
3. Check provider status pages

---

## Testing Your Setup

Quick test script:
```bash
python -c "
from agents.llm_provider_manager import get_llm_manager
import time

mgr = get_llm_manager()
print('Testing LLM providers...')

start = time.time()
response = mgr.call_llm(
    system_prompt='You are a helpful assistant.',
    user_message='Respond with OK',
    max_tokens=50
)
elapsed = time.time() - start

print(f'✅ Response: {response}')
print(f'⚡ Speed: {elapsed:.1f} seconds')
print(f'✅ Provider status:')
for name, status in mgr.get_provider_status().items():
    print(f'  {name}: {status[\"status\"]}')
"
```

**Expected output**:
```
Testing LLM providers...
✅ Response: OK
⚡ Speed: 3.2 seconds
✅ Provider status:
  groq: available
  gemini: available
  openrouter: available
```

---

## Summary

✅ **Quick Fix** (1 minute):
- Change `LLM_MODEL=llama-3.1-8b-instant` in `.env`

✅ **Recommended** (5 minutes):
- Use `.env.optimized` template
- Get Groq + Gemini API keys
- 6-12x faster, auto-fallback

✅ **Expected Results**:
- Agents complete in 30-90 seconds
- No more timeouts
- Reliable operation

🚀 **Your agents will now run successfully!**
