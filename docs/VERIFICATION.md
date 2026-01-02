# Component Verification System

## Overview

The system includes comprehensive pre-flight verification that checks **every component individually** before starting the trading system. This ensures all components are working correctly and provides detailed notes about each check.

## Running Verification

### Automatic (During Startup)
Verification runs automatically when you start the system:
```bash
python scripts/start_all.py BTC
```

### Manual (Standalone)
You can run verification independently:
```bash
python scripts/verify_all_components.py BTC
```

## Components Verified

### 1. MongoDB ✅
**What it checks:**
- MongoDB connection
- Database accessibility
- Required collections exist (agent_decisions, trades_executed, ohlc_history)

**Status Messages:**
- ✅ **PASS**: MongoDB connected and collections exist
- ⚠️ **WARNING**: Some collections missing (will be created automatically)
- ❌ **FAIL**: Cannot connect to MongoDB

**Fix if fails:**
- Start MongoDB: `mongod` or Docker
- Check MongoDB is running: `mongosh` or `mongo`

---

### 2. Redis ⚠️
**What it checks:**
- Redis connection
- Redis server accessibility

**Status Messages:**
- ✅ **PASS**: Redis connected
- ⚠️ **WARNING**: Redis not accessible (system can work without it)

**Fix if fails:**
- Start Redis: `redis-server` or Docker
- System will work without Redis but performance may be reduced

---

### 3. LLM Provider 🔴 CRITICAL
**What it checks:**
- **Ollama**: Server running, models available
- **Cloud Providers**: API keys configured

**Status Messages:**
- ✅ **PASS**: LLM provider accessible
- ❌ **FAIL**: LLM provider not accessible or misconfigured

**Fix if fails:**
- **Ollama**: Start with `ollama serve`, pull models with `ollama pull llama3.1:8b`
- **Cloud**: Add API key to `.env` file

---

### 4. Market Data 📊
**What it checks:**
- Current price available
- OHLC 1-minute candles available
- OHLC 5-minute candles available

**Status Messages:**
- ✅ **PASS**: Market data available
- ⚠️ **WARNING**: Some data missing (may need time to populate)

**Fix if fails:**
- Ensure data feed is running
- Wait for data feed to populate (can take 1-2 minutes)

---

### 5. Data Feed 🔴 CRITICAL
**What it checks:**
- **BTC**: Binance API accessible
- **Bank Nifty/Nifty**: Zerodha credentials valid

**Status Messages:**
- ✅ **PASS**: Data feed accessible
- ❌ **FAIL**: Data feed not accessible

**Fix if fails:**
- **BTC**: Check internet connection, Binance API status
- **Zerodha**: Run `python auto_login.py` to authenticate

---

### 6. Trading Graph ✅
**What it checks:**
- Trading graph can be initialized
- All agents can be created

**Status Messages:**
- ✅ **PASS**: Trading graph initialized successfully

**Fix if fails:**
- Check all dependencies installed
- Check configuration in `.env`

---

### 7. Agent Analysis 🔴 CRITICAL
**What it checks:**
- Runs a **full analysis cycle** (30-60 seconds)
- Verifies each agent produces meaningful output:
  - Technical Agent
  - Fundamental Agent
  - Sentiment Agent
  - Macro Agent
  - Bull Researcher
  - Bear Researcher
  - Portfolio Manager

**Status Messages:**
- ✅ **PASS**: Agent producing analysis with meaningful fields
- ⚠️ **WARNING**: Agent producing empty analysis (LLM may not be finding patterns)
- ❌ **FAIL**: Agent missing from results

**Detailed Notes:**
- Shows which fields are populated
- Shows which fields are empty
- Provides guidance on what might be wrong

**Fix if fails:**
- Check LLM provider is responding
- Check market data is available
- Review agent prompts if needed
- Check LLM response parsing

---

## Verification Report

After verification completes, you'll see a comprehensive report:

```
======================================================================
COMPREHENSIVE COMPONENT VERIFICATION REPORT
======================================================================

✅ PASSED: 12
⚠️  WARNINGS: 2
❌ FAILED: 0

======================================================================
✅ PASSED COMPONENTS
======================================================================
  ✅ MongoDB
     MongoDB connection successful
  
  ✅ Agent (fundamental)
     Fundamental agent producing analysis
     Has 8 meaningful fields: sector_strength, credit_quality_trend, ...

...

======================================================================
⚠️  WARNINGS
======================================================================
  ⚠️  Agent (technical)
     Technical agent producing empty analysis
     All 7 fields are empty/None. LLM may not be finding patterns...

...

======================================================================
SUMMARY
======================================================================
✅ All components verified successfully!
```

---

## Critical vs Non-Critical

### Critical Components (Must Pass)
- **MongoDB**: Required for storing analysis and trades
- **LLM Provider**: Required for agent analysis
- **Data Feed**: Required for market data
- **Agent Analysis**: Required for trading decisions

### Non-Critical Components (Warnings OK)
- **Redis**: Improves performance but not required
- **Market Data**: May need time to populate
- **Individual Agents**: Some may produce empty analysis initially

---

## What Happens If Verification Fails?

### Critical Failures
If critical components fail, the system **will not start** unless you explicitly choose to continue:
```
[CRITICAL] Component verification failed!
The system cannot start without working components.
Please review the verification report above and fix all critical issues.

Continue anyway? (y/N):
```

### Non-Critical Failures/Warnings
System will start but may have limited functionality. You'll see warnings in the report.

---

## Troubleshooting

### Agents Producing Empty Analysis
**Symptoms:**
- Agent verification shows "WARNING" for specific agents
- Fields are all None/empty/False

**Possible Causes:**
1. LLM not responding properly
2. LLM responses not being parsed correctly
3. Market data format doesn't match what agents expect
4. Prompts need adjustment

**Solutions:**
1. Check LLM provider is responding: `curl http://localhost:11434/api/tags` (Ollama)
2. Check market data is available: Run `python scripts/check_market_data.py`
3. Review agent logs for parsing errors
4. Check LLM response format matches expected structure

### Verification Timeout
**Symptoms:**
- Verification times out after 2-3 minutes

**Possible Causes:**
1. LLM calls hanging
2. Network issues
3. MongoDB slow to respond

**Solutions:**
1. Check LLM provider is responding
2. Check network connectivity
3. Check MongoDB performance

---

## Best Practices

1. **Always run verification before starting** - Catch issues early
2. **Review the detailed report** - Understand what's working and what's not
3. **Fix critical failures first** - Don't start with broken critical components
4. **Monitor warnings** - Address warnings to improve system performance
5. **Run verification after changes** - Verify after updating configuration or code

---

## Example Output

```
======================================================================
COMPREHENSIVE COMPONENT VERIFICATION
======================================================================
Instrument: BTC

Verifying MongoDB...
   ✅ MongoDB connection successful
   ✅ All required collections exist

Verifying Redis...
   ⚠️  Redis not accessible (system can work without Redis)

Verifying LLM Provider...
   ✅ Ollama running with 6 model(s)
   Models: llama3.1:8b, mistral:7b, ...

Verifying Market Data...
   ✅ Current price available: $89,469.26
   ✅ 5 1-minute candles available
   ⚠️  No 5-minute OHLC data

Verifying Data Feed...
   ✅ Binance API accessible (BTC: $89,469.26)

Verifying Agents (this may take 30-60 seconds)...
   Initializing trading graph...
   ✅ Trading graph initialized successfully
   Running single analysis cycle (30-60 seconds)...
   ✅ Analysis cycle completed

======================================================================
COMPREHENSIVE COMPONENT VERIFICATION REPORT
======================================================================

✅ PASSED: 12
⚠️  WARNINGS: 2
❌ FAILED: 0

[Detailed report follows...]
```

---

## Summary

The verification system ensures:
- ✅ All critical components are working
- ✅ Agents can produce meaningful analysis
- ✅ Market data is available
- ✅ LLM provider is accessible
- ✅ Detailed notes for troubleshooting

**Always verify before starting to ensure a smooth trading experience!**

