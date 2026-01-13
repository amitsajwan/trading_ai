# IRON_CONDOR Signal Threshold Fix - Summary

## Problem Identified

**Signal created with wrong threshold**: `current_price > 47524.722299999994`
- **Actual current price**: ~60,000
- **Threshold used**: 47,524 (from stale OHLC data)
- **Impact**: Signal triggers immediately (defeats conditional execution)

## Root Cause

**`current_price` is taken from LAST OHLC bar's close price**, not real-time tick price:

```python
# BEFORE (line 294 - WRONG):
current_price = ohlc_data[-1].get('close', 0)  # ❌ Stale OHLC close
```

**Problem**:
- OHLC bars are historical candle data (15-minute candles)
- Last bar's close can be 15+ minutes old
- Price moved from 47k to 60k, but code uses old 47k price
- Threshold calculated as 47k * 0.99 = 47k (always true at 60k)

## Solution Implemented

**Fixed `_fetch_market_data()` to use real-time tick price**:

1. **Try Redis tick price first** (real-time):
   - Redis key: `price:{instrument}:last_price`
   - Alternative: `tick:{instrument}:latest`
   
2. **Fallback to OHLC close** (if tick unavailable):
   - Only if tick price not available
   - Better than 0, but not ideal

3. **Log warning** when using fallback

## Code Changes

**File**: `engine_module/src/engine_module/orchestrator_stub.py`
**Method**: `_fetch_market_data()` (line 287-315)

### Before:
```python
current_price = ohlc_data[-1].get('close', 0)  # ❌ Stale
```

### After:
```python
# Try real-time tick price from Redis
current_price = None
try:
    redis_client = redis.Redis(...)
    # Try price:{instrument}:last_price key
    price_str = redis_client.get(f"price:{instrument}:last_price")
    if price_str:
        current_price = float(price_str)
    # Or try tick:{instrument}:latest format
    ...
except Exception:
    current_price = None

# Fallback to OHLC close if tick unavailable
if current_price is None or current_price <= 0:
    current_price = ohlc_data[-1].get('close', 0)  # ⚠️ Fallback only
```

## Expected Behavior After Fix

### Before Fix:
- Current price: 47,524 (stale OHLC close)
- Threshold: 47,524 * 0.99 = 47,048
- Condition: `current_price > 47048` → **TRUE at 60k** → Triggers immediately ❌

### After Fix:
- Current price: 60,000 (real-time tick price)
- Threshold: 60,000 * 0.99 = 59,400
- Condition: `current_price > 59400` → **FALSE at 60k** → Waits correctly ✅

## Verification

After fix, verify:

1. **Signal threshold** ≈ 99% of current real-time price
   - For 60k price: threshold ≈ 59,400 (not 47,524)

2. **Threshold updates** when price moves
   - Signal uses fresh price each cycle

3. **Signal doesn't trigger immediately** (unless price actually triggers)
   - Condition is meaningful, not always true

4. **Logging** shows when fallback is used
   - Check logs for "Using OHLC close price as fallback"

## Files Modified

1. ✅ `engine_module/src/engine_module/orchestrator_stub.py`
   - Updated `_fetch_market_data()` method
   - Now uses real-time tick price from Redis
   - Falls back to OHLC close only if tick unavailable

## Testing

### Test 1: Verify Current Price Source

```python
# In orchestrator cycle, check:
market_data = await orchestrator._fetch_market_data("BANKNIFTY")
current_price = market_data.get("current_price")
print(f"Current price: {current_price}")

# Should be ~60k (real-time), not 47k (stale)
```

### Test 2: Verify Signal Threshold

```python
# After signal creation:
signal = signal_monitor.get_signal(signal_id)
condition = signal.entry_conditions[0]
print(f"Threshold: {condition.threshold}")
print(f"Current price: {current_price}")
print(f"Expected threshold: {current_price * 0.99}")

# Threshold should be ~99% of current price
```

### Test 3: Verify Conditional Execution

1. Create signal with current price 60k
2. Threshold should be ~59,400
3. Signal should NOT trigger immediately (60k > 59,400 is FALSE)
4. Only trigger when price drops below 59,400

## Status

- ✅ **Root Cause**: Identified (stale OHLC close price)
- ✅ **Fix**: Implemented (use real-time tick price)
- ⏳ **Testing**: Need to verify after restart
- ⏳ **Production**: Ready after testing

## Next Steps

1. **Restart Orchestrator** to load new code
2. **Verify** current_price is now ~60k (not 47k)
3. **Verify** signal threshold is ~59,400 (not 47,524)
4. **Verify** conditional execution works correctly