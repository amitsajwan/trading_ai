# Agent Issues Analysis - Why Agents Are Not Running

## Root Causes Identified

### 1. **Model Too Large/Slow** ⚠️ CRITICAL
**Location**: `config/settings.py` line 50, `.env.example` line 20

**Problem**:
- Default model: `llama-3.3-70b-versatile` (70 billion parameters!)
- This is a HUGE model that:
  - Takes 10-60 seconds per call
  - Has strict rate limits
  - May cause timeouts

**Impact**:
- Trading loop has 5-minute timeout (`trading_service.py` line 299)
- System runs 10+ agents, each making 1+ LLM calls
- 10 agents × 30 seconds/call = 300 seconds = 5 minutes (timeout threshold!)
- With rate limits, this becomes even worse

**Solution**: Use faster models like `llama-3.1-8b-instant` (8B parameters)
- 8B model: 2-5 seconds per call
- 70B model: 10-60 seconds per call
- **6-12x faster!**

---

### 2. **Rate Limit Bottleneck** ⚠️ CRITICAL
**Location**: `agents/llm_provider_manager.py` line 128

**Problem**:
```python
rate_limit_per_minute=30  # Groq free tier
```

With 10+ agents calling simultaneously:
- First analysis run: 10 agents need LLM calls
- 10 calls in ~10 seconds = easily hits 30/minute limit
- When rate limited, system waits 4-5 minutes before retrying
- This cascades into timeouts

**Impact**:
- Agents get rate-limited mid-execution
- Trading loop times out waiting for recovery
- System appears "stuck" or "not running"

**Solution**:
1. Use faster models (less time = more calls/minute)
2. Add multiple provider fallbacks (Groq → OpenRouter → Gemini)
3. Increase request spacing

---

### 3. **Timeout Chain Reaction** ⚠️ HIGH
**Location**: `services/trading_service.py` line 296-306

**Problem**:
```python
result = await asyncio.wait_for(
    self.trading_graph.arun(),
    timeout=300.0  # 5 minutes timeout
)
```

- If LLM calls are slow (70B model) or rate-limited
- Each agent takes 30-60 seconds
- 10 agents × 60s = 600 seconds (10 minutes)
- **Exceeds 5-minute timeout!**

**What happens**:
1. Trading loop starts
2. Agents begin making LLM calls
3. Hits rate limit or model is slow
4. Timeout occurs at 5 minutes
5. Loop retries in 60 seconds
6. Same problem repeats
7. **Agents never complete successfully**

---

### 4. **LLM Provider Priority Issue** ⚠️ MEDIUM
**Location**: `agents/llm_provider_manager.py` lines 89-139

**Problem**:
```python
# Ollama - priority=10 (lowest priority)
# Groq - priority=0 (highest priority)
# Gemini - priority=1
# OpenRouter - priority=2
```

**Current behavior**:
- Always tries Groq first (fastest but strict rate limits)
- When Groq is rate-limited, fallback to Gemini/OpenRouter
- But Groq reset time might be far in future

**Issue**: System keeps trying Groq even when it's rate-limited for next 4 minutes

---

### 5. **No LLM Call Batching/Parallelization** ⚠️ MEDIUM
**Location**: `agents/base_agent.py` line 139-150

**Problem**:
- Each agent calls LLM synchronously
- No batching or optimization
- Multiple agents running in parallel all hit the same rate limit

**Impact**:
- With 4 analysis agents running in parallel (technical, fundamental, sentiment, macro)
- All 4 hit Groq simultaneously
- Instant rate limit hit on first iteration

---

## Quick Fixes (Immediate)

### Fix 1: Use Faster Models ⚡ **HIGHEST PRIORITY**

**Change in `.env`**:
```bash
# FROM (slow):
LLM_MODEL=llama-3.3-70b-versatile

# TO (fast):
LLM_MODEL=llama-3.1-8b-instant
```

**Expected improvement**:
- 6-12x faster per call
- More calls per minute before rate limit
- Trading loop completes in ~60 seconds instead of 5+ minutes

---

### Fix 2: Add Multiple Provider Fallbacks

**Create `.env` with multiple providers**:
```bash
# Primary (fastest)
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.1-8b-instant

# Fallback 1 (free, generous limits)
GOOGLE_API_KEY=your_key

# Fallback 2 (free, good for burst)
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
```

**Expected improvement**:
- When Groq rate-limited, automatically switch to Gemini
- 3x effective rate limit capacity
- System can handle burst requests

---

### Fix 3: Increase Timeout (Temporary)

**Location**: `services/trading_service.py` line 299

```python
# FROM:
timeout=300.0  # 5 minutes

# TO:
timeout=600.0  # 10 minutes (temporary fix)
```

**Warning**: This is a band-aid. Real fix is faster models.

---

## Recommended Model Configuration

### For Speed (Development/Testing)
```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
```
- Speed: ⚡⚡⚡ (2-5 seconds per call)
- Quality: ⭐⭐⭐ (good enough for trading)
- Rate limit: 30/minute (manageable)

### For Quality (Production)
```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-70b-versatile
```
- Speed: ⚡⚡ (10-30 seconds per call)
- Quality: ⭐⭐⭐⭐ (better analysis)
- Rate limit: 30/minute (may need multiple providers)

### For Maximum Stability (Recommended)
```bash
# Use multiple providers for auto-fallback
GROQ_API_KEY=xxx
GROQ_MODEL=llama-3.1-8b-instant
GOOGLE_API_KEY=xxx
OPENROUTER_API_KEY=xxx
```

---

## Free Model Options with Better Limits

| Provider | Model | Speed | Limit | Notes |
|----------|-------|-------|-------|-------|
| **Groq** | `llama-3.1-8b-instant` | ⚡⚡⚡ | 30/min | **FASTEST** - Use this first |
| **Gemini** | `gemini-flash-latest` | ⚡⚡⚡ | 60/min | Great fallback, generous limits |
| **OpenRouter** | `llama-3.2-3b-instruct:free` | ⚡⚡ | 50/min | Good for burst capacity |
| **Together AI** | `mixtral-8x7b-instruct` | ⚡⚡ | 40/min | Alternative option |

**Recommendation**: Use Groq (8B model) + Gemini as primary setup
- Groq for speed
- Gemini for fallback (generous free tier)
- Combined 90 requests/minute capacity

---

## Code Changes Needed

### Optional Enhancement: Reduce Agent Calls

**Location**: `agents/portfolio_manager.py` or individual agents

**Idea**: Some agents could use simple rules instead of LLM for every decision
- Technical agent: Use TA-Lib for indicators (no LLM needed)
- Fundamental agent: Only call LLM if news exists
- Sentiment agent: Use simple keyword matching first, LLM only for complex cases

**Expected improvement**:
- Reduce LLM calls from 10 to 5-7 per iteration
- 2x effective rate limit capacity

---

## Summary

**Why agents not running**:
1. ❌ Model too large (70B → use 8B)
2. ❌ Rate limits hit too quickly (30/min with 10 agents)
3. ❌ Timeouts cascade (5 min timeout with 10 min execution)

**Quick fixes**:
1. ✅ Change to `llama-3.1-8b-instant` (6-12x faster)
2. ✅ Add Gemini API key for fallback
3. ✅ (Optional) Increase timeout to 10 minutes

**Expected results after fixes**:
- Trading loop completes in 30-90 seconds (was 5+ minutes)
- Rate limits much less likely (faster = more headroom)
- Agents complete successfully
- System runs reliably
