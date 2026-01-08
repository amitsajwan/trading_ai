# Options Chain Endpoint - 503 Error Explanation

## Issue

The `GET /api/v1/options/chain/{instrument}` endpoint returns **503 Service Unavailable** with the message:
```
"Options client not initialized. Requires Kite API credentials."
```

## Root Cause

The options client (`_options_client`) is **never initialized** because:

1. **Missing Legacy Module**: The code requires `data.options_chain_fetcher.OptionsChainFetcher` which doesn't exist in the current codebase
2. **No Initialization in Startup**: The `startup_event()` function doesn't attempt to build the options client
3. **Global Variable Never Set**: `_options_client` remains `None` because `build_options_client()` is never called

## What's Required

To make the options chain endpoint work, you need:

1. **Kite API Credentials**:
   - `credentials.json` file with `api_key` and `access_token`
   - OR environment variables: `KITE_API_KEY` and `KITE_ACCESS_TOKEN`

2. **Legacy Modules** (currently missing):
   - `data.options_chain_fetcher.OptionsChainFetcher` class
   - `data.market_memory.MarketMemory` class

3. **Initialization**:
   - Build KiteConnect client from credentials
   - Create OptionsChainFetcher instance
   - Build options client using `build_options_client(kite, fetcher)`

## Solution Applied

I've updated the API service to:

1. **Lazy Initialization**: Added `get_options_client()` function that tries to build the options client when needed
2. **Better Error Messages**: The 503 error now explains exactly what's missing:
   ```
   "Options client not available. Requires: (1) Kite API credentials in credentials.json, 
   (2) data.options_chain_fetcher module, (3) data.market_memory module. 
   Check logs for initialization errors."
   ```
3. **Startup Attempt**: The startup event now attempts to initialize the options client (non-blocking)

## Current Status

- ✅ **API Endpoint**: Working correctly, returns proper 503 with clear error message
- ❌ **Options Client**: Cannot be initialized because legacy modules are missing
- ✅ **Error Handling**: Proper HTTP status codes and descriptive error messages

## Next Steps

To fully enable options chain:

1. **Option A - Restore Legacy Module**: 
   - Add `data/options_chain_fetcher.py` with `OptionsChainFetcher` class
   - Add `data/market_memory.py` with `MarketMemory` class

2. **Option B - Direct Kite API** (Recommended):
   - Create a new options chain fetcher that uses Kite API directly
   - No dependency on legacy modules
   - Simpler and more maintainable

3. **Option C - Mock/Stub**:
   - Create a simple stub that returns empty/mock data
   - Allows API to work without full implementation

## Testing

Test the endpoint:
```bash
curl http://localhost:8004/api/v1/options/chain/BANKNIFTY
```

Expected response (until modules are added):
```json
{
  "detail": "Options client not available. Requires: (1) Kite API credentials in credentials.json, (2) data.options_chain_fetcher module, (3) data.market_memory module. Check logs for initialization errors."
}
```

