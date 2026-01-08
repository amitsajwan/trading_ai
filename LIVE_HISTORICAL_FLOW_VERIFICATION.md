# Live vs Historical Flow Verification

## Flow Separation Logic

### Decision Point (Line 881)
```python
if provider_name_normalized in ('historical', 'replay', 'auto'):
    # HISTORICAL FLOW
else:
    # LIVE FLOW
```

## ✅ LIVE FLOW (`--provider zerodha` or `--provider kite`)

**Path:** Lines 904-960

### Steps:
1. **Clear Virtual Time** (Lines 907-917)
   - Deletes `system:virtual_time:enabled`
   - Deletes `system:virtual_time:current`
   - ✅ Ensures real-time is used

2. **Start Live Collectors** (Lines 920-960)
   - ✅ LTP Collector: Writes to MarketStore via `store_tick()`
   - ✅ Depth Collector: Writes depth data to Redis
   - ✅ Collectors run in background threads
   - ✅ NO historical replay started

3. **Data Flow:**
   ```
   Zerodha API → LTP Collector → MarketStore.store_tick() → Redis (tick:BANKNIFTY:latest)
   ```

4. **APIs Read From:**
   - MarketStore.get_latest_tick() → Reads from Redis
   - ✅ Gets live data from collectors

### Verification Points:
- ✅ No `start_historical_replay()` called
- ✅ Virtual time cleared
- ✅ Collectors write via MarketStore interface
- ✅ Real-time timestamps used

---

## ✅ HISTORICAL FLOW (`--provider historical` or `--provider replay`)

**Path:** Lines 881-903

### Steps:
1. **Start Historical Replay** (Line 882)
   - Calls `start_historical_replay()` (Lines 646-780)
   - ✅ Builds MarketStore with Redis client
   - ✅ Creates HistoricalTickReplayer
   - ✅ Starts replay (writes to MarketStore)

2. **Virtual Time** (Set by replayer)
   - HistoricalTickReplayer sets virtual time in Redis
   - ✅ System uses virtual time for historical data

3. **Data Flow:**
   ```
   Zerodha Historical API / CSV → HistoricalTickReplayer → MarketStore.store_tick() → Redis (tick:BANKNIFTY:latest)
   ```

4. **APIs Read From:**
   - MarketStore.get_latest_tick() → Reads from Redis
   - ✅ Gets historical data from replayer

### Verification Points:
- ✅ No collectors started
- ✅ Historical replay writes via MarketStore interface
- ✅ Virtual time set by replayer
- ✅ Historical timestamps preserved

---

## 🔍 Key Verification Checks

### 1. Separation is Clean?
- ✅ Live mode: `provider_name_normalized in ('zerodha', 'kite')` → Goes to `else:` block
- ✅ Historical mode: `provider_name_normalized in ('historical', 'replay', 'auto')` → Goes to `if:` block
- ✅ No overlap - collectors only start in live mode, replayer only starts in historical mode

### 2. Both Use Same Store Interface?
- ✅ Live: `live_store.store_tick(tick)` (Line 221 in ltp_collector.py)
- ✅ Historical: `store.store_tick(tick)` (via HistoricalTickReplayer)
- ✅ Both write to same Redis keys: `tick:{instrument}:latest`

### 3. Virtual Time Handling?
- ✅ Live: Virtual time cleared (Lines 913-914)
- ✅ Historical: Virtual time set by replayer (in historical_tick_replayer.py)

### 4. Data Source Correct?
- ✅ Live: Real-time Zerodha API via collectors
- ✅ Historical: Zerodha historical API or CSV via replayer

---

## 🧪 Test Commands

### Test Live Flow:
```bash
python start_local.py --provider zerodha
```
**Expected:**
- ✅ Collectors start
- ✅ No historical replay
- ✅ Virtual time cleared
- ✅ Live data in Redis

### Test Historical Flow:
```bash
python start_local.py --provider historical --historical-from 2026-01-07
```
**Expected:**
- ✅ Historical replay starts
- ✅ No collectors
- ✅ Virtual time set
- ✅ Historical data in Redis

---

## ⚠️ Potential Issues to Check

1. **Collector writes but store reads different key?**
   - ✅ Fixed: Collector uses `store_tick()` which writes to `tick:{instrument}:latest`
   - ✅ Store reads from `tick:{instrument}:latest`

2. **Virtual time not cleared in live mode?**
   - ✅ Fixed: Explicitly cleared at Lines 913-914

3. **Both flows writing to same Redis?**
   - ✅ This is correct - both use MarketStore interface
   - ✅ Separation is by mode (live vs historical), not by storage

4. **Instrument name mismatch?**
   - ✅ Fixed: Collector normalizes to "BANKNIFTY"
   - ✅ Store expects "BANKNIFTY"

---

## ✅ Conclusion

Both flows are properly separated and use the same MarketStore interface:
- **Live**: Collectors → MarketStore → Redis
- **Historical**: Replayer → MarketStore → Redis

The key is the provider selection determines which path is taken, and both paths write through the same interface.

## 🔧 Code Verification Summary

### Live Flow Code Path:
1. **Provider Check** (Line 881): `if provider_name_normalized in ('historical', 'replay', 'auto'):` → **FALSE** for 'zerodha'
2. **Else Block** (Line 904): Enters live mode
3. **Collector Start** (Line 920): `if provider_name_normalized in ('zerodha', 'kite') and kite_instance:`
4. **Store Creation** (Line 934): `live_store = build_store(redis_client=redis_client)`
5. **Collector Writes** (ltp_collector.py Line 221): `self.market_memory.store_tick(tick)`
6. **Virtual Time** (Lines 913-914): Cleared

### Historical Flow Code Path:
1. **Provider Check** (Line 881): `if provider_name_normalized in ('historical', 'replay', 'auto'):` → **TRUE**
2. **Replay Start** (Line 882): `await start_historical_replay(...)`
3. **Store Creation** (start_historical_replay Line 724): `store = build_store(redis_client=redis_client)`
4. **Replayer Writes** (historical_tick_replayer.py Line 172): `self.store.store_tick(tick)`
5. **Virtual Time** (historical_tick_replayer.py Line 169): Set by replayer

### API Service Reads:
- **Market Data API** (api_service.py Line 108): `_store = build_store(redis_client=redis_client)`
- **Reads From** (redis_store.py Line 127): `self.redis.get(f"tick:{instrument}:latest")`
- ✅ Works for both live and historical data (same Redis keys)

## ✅ Final Verification

| Aspect | Live Flow | Historical Flow | Status |
|--------|-----------|-----------------|--------|
| Provider Check | `zerodha`/`kite` → `else:` block | `historical`/`replay` → `if:` block | ✅ Separated |
| Collectors Start | ✅ Yes (Line 920) | ❌ No | ✅ Correct |
| Replayer Start | ❌ No | ✅ Yes (Line 882) | ✅ Correct |
| Store Interface | `live_store.store_tick()` | `store.store_tick()` | ✅ Same |
| Redis Keys | `tick:BANKNIFTY:latest` | `tick:BANKNIFTY:latest` | ✅ Same |
| Virtual Time | Cleared (Lines 913-914) | Set by replayer | ✅ Correct |
| API Reads | From Redis (same keys) | From Redis (same keys) | ✅ Works |

**✅ Both flows are perfect and properly separated!**

