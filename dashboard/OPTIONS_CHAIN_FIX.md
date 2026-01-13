# Options Chain Not Updating - Root Cause Analysis

## Problem

Options Chain widget shows static data that doesn't update:
- Expiry: 1/27/2026 (fixed)
- Futures: ₹59525.00 (not changing)
- Put/Call Ratio: 0.86 (not changing)
- Max Pain: ₹59,500 (not changing)
- Strike prices and OI values (not changing)

## Root Causes Identified

### 1. **API Endpoint Issue** ✅ FIXED
- Component calls: `/api/market-data/options/chain/${instrument}`
- Proxy: Forwards to `http://localhost:8004/api/v1/options/chain/${instrument}`
- **Status**: Endpoint exists in `market_data/src/market_data/api_service.py`

### 2. **Static Mock Data** ⚠️ ISSUE
- FastAPI `app.py` has `/api/options-chain` with **hardcoded static data** (lines 1087-1158)
- This endpoint is NOT being used by the component (good)
- But if market_data API (port 8004) is not running, component will fail

### 3. **No Real-Time Updates** ⚠️ ISSUE
- WebSocket supports `market:options:*` channel
- Component now subscribes to WebSocket (✅ FIXED)
- **BUT**: Nothing is publishing options chain updates to Redis/WebSocket
- Data only updates via polling (every 5 seconds)

### 4. **Missing Data Publishing** ❌ CRITICAL
- No service is publishing options chain data to Redis pub/sub
- Market data API returns data but doesn't publish to `market:options:*` channel
- WebSocket subscription works but receives no messages

## Solutions Applied

### ✅ 1. WebSocket Subscription (FIXED)
**File**: `dashboard/modular_ui/src/components/widgets/OptionsChainWidget.tsx`

- Added WebSocket subscription for `market:options:${instrument}` and `market:options:*`
- Component now subscribes when WebSocket connects
- Falls back to polling if WebSocket unavailable
- Reduced polling frequency when WebSocket connected (30s backup vs 5s)

### ✅ 2. Live Status Indicator (FIXED)
- Added "Live" indicator when WebSocket is connected
- Shows connection status to user

### ⚠️ 3. Still Need: Data Publishing Service

The market_data API needs to publish options chain updates to Redis:

```python
# In market_data API (api_service.py), after fetching options chain:
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# After fetching options chain data:
chain_data = await options_client.fetch_options_chain(instrument=instrument)

# Publish to Redis for WebSocket forwarding:
redis_client.publish(
    f'market:options:{instrument}', 
    json.dumps({
        'instrument': instrument,
        'futures_price': chain_data.futures_price,
        'expiry': chain_data.expiry,
        'pcr': chain_data.pcr,
        'max_pain': chain_data.max_pain,
        'strikes': chain_data.strikes,
        'timestamp': datetime.now().isoformat()
    })
)
```

## Verification Steps

1. **Check if market_data API is running:**
   ```bash
   curl http://localhost:8004/api/v1/options/chain/BANKNIFTY
   ```

2. **Check if data is being published to Redis:**
   ```bash
   redis-cli
   > PSUBSCRIBE market:options:*
   # Should see messages when options chain updates
   ```

3. **Check browser console:**
   - Should see: `[OptionsChain] Subscribed to WebSocket channels: market:options:BANKNIFTY, market:options:*`
   - Should see: `📊 WebSocket options chain update:` when data arrives

4. **Check if polling is working:**
   - Component polls every 5s (or 30s if WebSocket connected)
   - Check Network tab for `/api/market-data/options/chain/BANKNIFTY` requests

## Expected Behavior After Full Fix

1. ✅ Component fetches initial data on mount
2. ✅ Component subscribes to WebSocket `market:options:*` channel
3. ✅ Market data API publishes updates to Redis `market:options:*` channel
4. ✅ WebSocket gateway forwards updates to frontend
5. ✅ Component receives real-time updates via WebSocket
6. ✅ Component falls back to polling if WebSocket unavailable

## Next Steps

1. **Implement Redis publishing** in market_data API options chain endpoint
2. **Add periodic updates** - publish options chain every few seconds (or on change)
3. **Test end-to-end** - verify data flows: API → Redis → WebSocket → Frontend
4. **Monitor** - Check Redis pub/sub and WebSocket message rates

## Current Status

- ✅ Component: Fixed to subscribe to WebSocket
- ✅ WebSocket: Already supports `market:options:*` channel  
- ❌ **Data Publishing**: NOT implemented - this is the blocker
- ✅ Polling: Works as fallback, but only updates if API returns new data

## Temporary Workaround

Until data publishing is implemented, the component will:
- Poll every 5 seconds (or 30s with WebSocket)
- Updates will only work if the API endpoint returns fresh data
- If API returns cached/static data, UI won't update

The **root cause** is that nothing is publishing options chain updates to Redis/WebSocket. The API exists and works, but data is not being streamed in real-time.