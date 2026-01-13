# IRON_CONDOR Signal Threshold Issue - Root Cause Analysis

## Problem

Signal created with threshold: `current_price > 47524.722299999994`
- **Actual current price**: ~60,000 (60k)
- **Threshold used**: 47,524 (47k)
- **Gap**: ~13k difference (20% lower!)

## Root Cause Analysis

### Signal Creation Flow

1. **Orchestrator runs cycle** (`orchestrator_stub.py:run_cycle`)
   - Calls `_fetch_market_data(instrument)`
   
2. **Market Data Fetching** (line 287-315)
   ```python
   async def _fetch_market_data(self, instrument: str) -> Dict[str, Any]:
       # Uses Redis provider
       ohlc_data = await self.market_data_provider.get_ohlc_data(instrument, periods=100)
       current_price = ohlc_data[-1].get('close', 0) if ohlc_data else 0  # Line 294
       return {
           "current_price": current_price,  # ⚠️ Uses LAST OHLC bar's close
           ...
       }
   ```

3. **Signal Creation** (line 247-252)
   ```python
   await self._create_signals_from_decision(
       final_decision,
       instrument,
       market_data.get("current_price"),  # ⚠️ Passes stale OHLC close price
       technical_data.get("technical_indicators", {})
   )
   ```

4. **Default Condition Logic** (`signal_creator.py:187`)
   ```python
   if not parsed_conditions:
       if current_price and current_price > 0:
           parsed_conditions = [{
               "indicator": "current_price",
               "operator": ConditionOperator.GREATER_THAN,
               "threshold": current_price * 0.99,  # ⚠️ 1% below stale price
               "source": "default"
           }]
   ```

### The Problem

**`current_price` is taken from the LAST OHLC bar's close price**, which can be:
- **Stale**: Last 15-minute candle's close (not current tick price)
- **Historical**: If using historical replay mode
- **Delayed**: Not real-time current price

### Calculation

If last OHLC bar close = 47,524:
- Threshold = 47,524 * 0.99 = 47,048.76
- But we see: 47,524.722299999994

This suggests:
- Either `current_price` is exactly 47,524.72 (stale OHLC data)
- Or threshold validation adjusted it (but shouldn't if it's already 99% of current)

### Expected vs Actual

**Expected Behavior**:
- Current price: ~60,000 (real-time tick price)
- Threshold: 60,000 * 0.99 = 59,400
- Condition: `current_price > 59400`

**Actual Behavior**:
- Current price: 47,524 (stale OHLC close)
- Threshold: 47,524.72 (or 47,524 * 0.99 = 47,048.76)
- Condition: `current_price > 47524.72` ← **WRONG! Always true at 60k!**

## Impact

### For IRON_CONDOR Signal:
- Signal is created with threshold 47,524
- Current price is 60,000
- Condition: `current_price > 47524.72` → **TRUE immediately**
- Signal executes immediately (not conditional)
- **This defeats the purpose of conditional execution!**

### The Signal Should:
- Use current real-time price (~60k)
- Set threshold at 60k * 0.99 = 59,400
- Wait for price to drop below 59,400 (or rise above based on strategy)

## Root Cause Summary

**The `current_price` passed to `create_signals_from_decision` comes from stale OHLC data, not real-time tick price.**

### Where it goes wrong:

1. ✅ **Orchestrator** fetches market data correctly
2. ❌ **Uses OHLC close** instead of real-time tick price
3. ❌ **Passes stale price** to signal creator
4. ❌ **Signal creator** creates condition based on stale price
5. ❌ **Threshold is wrong** → Signal triggers immediately

## Solution

### Option 1: Use Real-Time Tick Price (Recommended)

Get current price from Redis tick data, not OHLC:

```python
async def _fetch_market_data(self, instrument: str) -> Dict[str, Any]:
    # Try to get real-time tick price first
    current_price = None
    
    # Option A: From Redis tick data (real-time)
    try:
        if self.market_store:
            ticks = await self.market_store.get_latest_ticks(instrument, limit=1)
            if ticks and len(ticks) > 0:
                current_price = ticks[0].last_price
    except Exception:
        pass
    
    # Option B: From market data provider (real-time)
    if current_price is None:
        try:
            if self.market_data_provider and hasattr(self.market_data_provider, 'get_current_price'):
                current_price = await self.market_data_provider.get_current_price(instrument)
        except Exception:
            pass
    
    # Fallback C: Use OHLC close (less ideal but better than 0)
    if current_price is None:
        ohlc_data = await self.market_data_provider.get_ohlc_data(instrument, periods=100)
        current_price = ohlc_data[-1].get('close', 0) if ohlc_data else 0
    
    return {
        "current_price": current_price,  # ✅ Real-time price
        ...
    }
```

### Option 2: Use Futures Price from Options Chain

For options strategies, use futures price instead:

```python
# In _select_and_build_strategy or signal creation
if options_chain and options_chain.get('futures_price'):
    current_price = options_chain['futures_price']  # ✅ More accurate for options
```

### Option 3: Fetch Fresh Price in Signal Creator

Don't trust passed price, fetch fresh:

```python
def create_signals_from_decision(...):
    # Fetch fresh current price if available
    if market_data_provider:
        fresh_price = await market_data_provider.get_current_price(instrument)
        if fresh_price and fresh_price > 0:
            current_price = fresh_price  # ✅ Use fresh price
```

## Verification

After fix, verify:
1. ✅ Signal threshold ≈ 99% of current real-time price
2. ✅ Threshold updates when price moves
3. ✅ Signal doesn't trigger immediately (unless intended)
4. ✅ For 60k price: threshold ≈ 59,400 (not 47,524)

## Files to Fix

1. **Primary**: `engine_module/src/engine_module/orchestrator_stub.py`
   - `_fetch_market_data()` method (line 287-315)
   - Use real-time tick price instead of OHLC close

2. **Secondary**: `engine_module/src/engine_module/signal_creator.py`
   - `create_signals_from_decision()` method
   - Add validation/warning if price seems stale
   - Or fetch fresh price directly

## Recommendation

**Use Option 1**: Get real-time tick price from Redis or market data provider. This ensures:
- ✅ Accurate current price
- ✅ Correct threshold calculation
- ✅ Conditional execution works as intended
- ✅ Signals don't trigger immediately

The issue is that **OHLC close prices are historical/candle data, not real-time current prices**. For conditional execution to work correctly, we need the **actual current tick price**.