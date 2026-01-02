# .env File Configuration Guide

## Overview

The `.env` file is **automatically updated** when you switch instruments. You don't need to manually edit it - just use the flag!

## What Changes vs What Stays the Same

### ✅ What Changes (Instrument-Specific)

When you run `python scripts/configure_instrument.py BTC` or `python scripts/start_all.py BTC`, these variables are **automatically updated**:

```bash
# Instrument Configuration
INSTRUMENT_SYMBOL=BTC-USD          # Changes: BTC-USD, NIFTY BANK, NIFTY 50
INSTRUMENT_NAME=Bitcoin             # Changes: Bitcoin, Bank Nifty, Nifty 50
INSTRUMENT_EXCHANGE=CRYPTO          # Changes: CRYPTO, NSE
DATA_SOURCE=CRYPTO                  # Changes: CRYPTO, ZERODHA
NEWS_QUERY=Bitcoin OR BTC...        # Changes: Different queries per instrument
NEWS_KEYWORDS=Bitcoin,BTC...        # Changes: Different keywords
MACRO_DATA_ENABLED=false            # Changes: false for crypto, true for stocks
MARKET_24_7=true                    # Changes: true for crypto, false for stocks
MARKET_OPEN_TIME=00:00:00           # Changes: 00:00:00 for crypto, 09:15:00 for stocks
MARKET_CLOSE_TIME=23:59:59          # Changes: 23:59:59 for crypto, 15:30:00 for stocks
```

### 🔒 What Stays the Same (Infrastructure)

These **DO NOT change** when switching instruments - they're infrastructure settings:

```bash
# Database URLs (same for all instruments)
MONGODB_URI=mongodb://localhost:27017/
REDIS_HOST=localhost
REDIS_PORT=6379

# LLM Provider URLs (same for all instruments)
OLLAMA_BASE_URL=http://localhost:11434

# API Keys (same for all instruments)
GROQ_API_KEY=...
GOOGLE_API_KEY=...
NEWS_API_KEY=...
```

## How It Works

1. **You run**: `python scripts/start_all.py BTC`
2. **Script automatically**:
   - Calls `configure_instrument.py BTC`
   - Updates only instrument-specific variables in `.env`
   - Preserves all other settings (URLs, API keys, etc.)
3. **System reads** updated `.env` and uses correct data source

## Verify Changes

Check what's currently configured:

```bash
python scripts/verify_env.py
```

Or see what will change:

```bash
python scripts/show_env_changes.py
```

## Manual Override

If you need to manually edit `.env`:

1. **Don't edit instrument configs** - use the script instead
2. **You CAN edit**:
   - API keys
   - Database URLs
   - LLM provider settings
   - Trading parameters

## Example: Switching from BTC to BANKNIFTY

**Before (BTC):**
```bash
INSTRUMENT_SYMBOL=BTC-USD
DATA_SOURCE=CRYPTO
MARKET_24_7=true
MACRO_DATA_ENABLED=false
```

**After running**: `python scripts/configure_instrument.py BANKNIFTY`

**After (BANKNIFTY):**
```bash
INSTRUMENT_SYMBOL=NIFTY BANK
DATA_SOURCE=ZERODHA
MARKET_24_7=false
MACRO_DATA_ENABLED=true
```

**What stayed the same:**
- All API keys
- All database URLs
- All LLM provider URLs
- All other infrastructure settings

## Troubleshooting

### .env Not Updating

1. **Check file permissions**: Make sure `.env` is writable
2. **Check script output**: Look for "SUCCESS: Configuration updated!"
3. **Verify manually**: Run `python scripts/verify_env.py`

### Wrong Values After Switch

1. **Re-run config**: `python scripts/configure_instrument.py BTC`
2. **Check for duplicates**: Make sure each key appears only once
3. **Verify**: `python scripts/verify_env.py`

### Want to Reset Everything

1. **Backup**: Copy `.env` to `.env.backup`
2. **Reconfigure**: `python scripts/configure_instrument.py BTC`
3. **Restore other settings**: Copy API keys, URLs from backup

## Summary

- ✅ **Instrument configs**: Auto-updated by script
- 🔒 **Infrastructure (URLs, keys)**: Never change
- 📝 **Single .env file**: One file for everything
- 🚀 **Flag-based**: Just use `BTC`, `BANKNIFTY`, or `NIFTY`

**No manual .env editing needed for instrument switching!**

