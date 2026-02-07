# ZERODHA TRADING SYSTEM - COMPREHENSIVE FIX PLAN
## Date: February 3, 2026

## Executive Summary

After deep architectural analysis, identified **3 CRITICAL issues**:
1. ❌ Volume aggregation bug (replaces instead of sums)
2. ❌ No data isolation between LIVE and HISTORICAL modes
3. ❌ Unclear service boundaries (what runs when?)

---

## Issue 1: Volume Aggregation Bug ⚠️ CRITICAL

### Root Cause
Two files aggregate 1min bars into higher timeframes but **replace volume instead of summing**:

**File 1: [aggregate_timeframes.py](aggregate_timeframes.py) Line 67**
```python
# BUG:
c['volume'] = bar['volume']  # ❌ Only keeps last bar's volume

# FIX:
c['volume'] += bar['volume']  # ✅ Sum all volumes
```

**File 2: [multi_timeframe_aggregator.py](multi_timeframe_aggregator.py) Line 98**
```python
# BUG:
candle['volume'] = candle_data['volume']  # ❌ Only keeps last bar's volume

# FIX:
candle['volume'] += candle_data['volume']  # ✅ Sum all volumes
```

### Impact
- All 5min, 15min, 1h, 4h bars show volume=0 or incorrect volume
- Technical indicators relying on volume (VWAP, volume oscillators) are broken
- Zerodha API DOES provide volume data - we're just not aggregating it correctly

### Solution
Fix both files to SUM volumes when aggregating candles.

---

## Issue 2: Data Isolation Missing ❌ CRITICAL

### Current Problem
```python
# Both LIVE and HISTORICAL modes write to SAME Redis keys:
ohlc_sorted:BANKNIFTY26FEBFUT:1min
ohlc_sorted:BANKNIFTY26FEBFUT:5min
enhanced_ticks:BANKNIFTY26FEBFUT

# MongoDB same collections:
signals, decisions, trades, market_data
```

**Result:** Old historical data contaminates live trading data!

### Solution: Mode Prefixing

#### Redis Keys
```python
# LIVE Mode:
live:ohlc_sorted:BANKNIFTY26FEBFUT:1min
live:ohlc_sorted:BANKNIFTY26FEBFUT:5min
live:enhanced_ticks:BANKNIFTY26FEBFUT
live:raw_ticks:BANKNIFTY26FEBFUT

# HISTORICAL Mode:
historical:ohlc_sorted:BANKNIFTY26FEBFUT:1min
historical:enhanced_ticks:BANKNIFTY26FEBFUT
```

#### MongoDB Collections
```python
# LIVE Mode:
live_signals
live_decisions
live_trades
live_market_data

# HISTORICAL Mode:
historical_signals
historical_decisions
historical_trades
historical_market_data
```

#### Implementation Files to Modify
1. **`ohlc_aggregator_service.py`** - Add mode prefix to Redis keys
2. **`multi_timeframe_aggregator.py`** - Add mode prefix
3. **`ltp_collector.py`** - Add mode prefix to pub/sub channels
4. **`websocket_tick_collector.py`** - Add mode prefix
5. **`market_data/src/market_data/api_service.py`** - Read from correct mode prefix
6. **`load_today_historical.py`** - Use live: prefix
7. **`aggregate_timeframes.py`** - Use live: prefix
8. **`start_unified.py`** - Set mode environment variable

#### New Environment Variable
```bash
EXECUTION_MODE=LIVE  # or HISTORICAL
```

All services check this variable and prefix Redis keys accordingly.

---

## Issue 3: Service Boundaries Unclear ❌ CRITICAL

### Current Docker Services (23 total)

**Core Infrastructure (ALWAYS run)**
- `mongodb` - Database
- `redis` - Cache/pub-sub

**LIVE Mode ONLY (7 services)**
- `websocket-tick-collector-banknifty` ✅ Real-time Zerodha ticks
- `ltp-collector-banknifty` ✅ Process ticks, volume logic
- `depth-collector-banknifty` ✅ Order book data
- `ohlc-aggregator` ✅ Create 1min bars from ticks
- `multi-timeframe-aggregator` ⚠️ NOT IN DOCKER-COMPOSE (need to add)
- `market-data-api` ✅ REST API
- `market-data-dashboard` ✅ Chart UI

**HISTORICAL Mode ONLY (1 service)**
- `historical-replay-service` ✅ Replay old data

**Trading Bots (Mode-aware)**
- `trading-bot-banknifty` - Orchestrator (runs in both modes)
- `automatic-trading-service` - Auto-trader (LIVE only)

**NOT NEEDED for basic live chart display:**
- `trading-bot-btc` (disabled)
- `trading-bot-nifty` (disabled)
- `backend-banknifty`, `backend-btc`, `backend-nifty` (old dashboards)
- `orchestrator-service` (duplicate)
- `news-collector`, `news-api` (optional)
- `engine-api` (trading decisions)
- `redis-ws-gateway` (WebSocket bridge)
- `kite-auth-service` (background token refresh - optional)
- `dashboard-backend`, `dashboard-frontend` (main dashboard - optional)

### What User Wants
> "when we start system, it should start all components, all the not required components should not be there"

**Translation:**
```bash
# LIVE Mode - Start ONLY these 9 containers:
python start_unified.py --live
# Should start:
- mongodb
- redis
- websocket-tick-collector-banknifty
- ltp-collector-banknifty
- ohlc-aggregator
- multi-timeframe-aggregator (NEW - to be added)
- market-data-api
- market-data-dashboard

# Should NOT start:
- historical-replay-service ❌
- All disabled/nifty/btc services ❌
```

---

## Implementation Plan

### Phase 1: Fix Volume Bug (10 minutes) ⚠️ HIGH PRIORITY
1. ✅ Fix `aggregate_timeframes.py` line 67
2. ✅ Fix `multi_timeframe_aggregator.py` line 98
3. ✅ Add multi-timeframe-aggregator to docker-compose.yml
4. ✅ Test: Clear Redis, reload data, verify volume sums correctly

### Phase 2: Add Data Isolation (30 minutes) ⚠️ HIGH PRIORITY
1. Add `EXECUTION_MODE` environment variable
2. Create utility function `get_redis_key(base_key, mode)`
3. Modify all services to use mode-prefixed keys:
   - ohlc_aggregator_service.py
   - multi_timeframe_aggregator.py
   - ltp_collector.py
   - websocket_tick_collector.py
   - api_service.py
4. Test: Switch between modes, verify no data contamination

### Phase 3: Clean Startup (20 minutes) 🎯 USER REQUEST
1. Modify `start_unified.py --live` to:
   - Set `EXECUTION_MODE=LIVE` environment variable
   - Clear only `live:*` Redis keys
   - Start ONLY required services
   - Stop `historical-replay-service` if running
2. Modify `start_unified.py --historical --date 2026-01-28` to:
   - Set `EXECUTION_MODE=HISTORICAL`
   - Clear only `historical:*` Redis keys
   - Start `historical-replay-service`
   - Stop WebSocket collectors

### Phase 4: Add Missing Service (15 minutes)
1. Add `multi-timeframe-aggregator` to docker-compose.yml
2. Configure it to subscribe to `1min_candle:BANKNIFTY26FEBFUT`
3. Set auto-restart and healthcheck

---

## Expected Results

### ✅ Volume Fixed
```json
{
  "timeframe": "15min",
  "open": 57971.9,
  "high": 57978.35,
  "low": 57940.45,
  "close": 57941.75,
  "volume": 12543,  // ✅ Sum of all 1min bars (not 0!)
  "start_at": "2026-02-02T11:15:00+05:30"
}
```

### ✅ Data Isolation
```bash
# LIVE mode Redis:
127.0.0.1:6380> KEYS live:*
1) "live:ohlc_sorted:BANKNIFTY26FEBFUT:1min"
2) "live:ohlc_sorted:BANKNIFTY26FEBFUT:5min"

# HISTORICAL mode Redis:
127.0.0.1:6380> KEYS historical:*
1) "historical:ohlc_sorted:BANKNIFTY26FEBFUT:1min"

# No mixing!
```

### ✅ Clean Startup
```bash
$ python start_unified.py --live
✓ Authenticated as BV2032
✓ Cleared live Redis data
✓ Loaded today's historical data (122 bars)
✓ Aggregated into timeframes
✓ Started 8 services:
  - websocket-tick-collector-banknifty
  - ltp-collector-banknifty
  - ohlc-aggregator
  - multi-timeframe-aggregator
  - market-data-api
  - market-data-dashboard
✓ Stopped historical-replay-service
✓ System ready at http://localhost:8008
```

---

## Testing Checklist

### Volume Aggregation Test
```bash
# 1. Clear data
docker-compose exec redis redis-cli FLUSHDB

# 2. Load historical data
python load_today_historical.py

# 3. Aggregate
python aggregate_timeframes.py

# 4. Check volume
docker-compose exec redis redis-cli ZRANGE "ohlc_sorted:BANKNIFTY26FEBFUT:15min" -1 -1

# Expected: volume > 0
```

### Data Isolation Test
```bash
# 1. Start LIVE mode
python start_unified.py --live

# 2. Check keys
docker-compose exec redis redis-cli KEYS "live:*"

# 3. Start HISTORICAL mode
python start_unified.py --historical --date 2026-01-28

# 4. Check keys
docker-compose exec redis redis-cli KEYS "historical:*"

# 5. Verify no mixing
docker-compose exec redis redis-cli KEYS "ohlc_sorted:*"  # Should be empty
```

### Clean Startup Test
```bash
# 1. Start live
python start_unified.py --live

# 2. Check running services
docker-compose ps

# 3. Verify ONLY required services running:
# ✅ websocket-tick-collector-banknifty
# ✅ ltp-collector-banknifty
# ✅ ohlc-aggregator
# ✅ multi-timeframe-aggregator
# ✅ market-data-api
# ✅ market-data-dashboard
# ❌ historical-replay-service (should be stopped)
```

---

## Files to Modify Summary

**Priority 1 (Volume Fix):**
1. `aggregate_timeframes.py` - Line 67: Change `=` to `+=`
2. `multi_timeframe_aggregator.py` - Line 98: Change `=` to `+=`
3. `docker-compose.yml` - Add multi-timeframe-aggregator service

**Priority 2 (Data Isolation):**
4. `ohlc_aggregator_service.py` - Add mode prefix
5. `multi_timeframe_aggregator.py` - Add mode prefix
6. `market_data/src/market_data/collectors/ltp_collector.py` - Add mode prefix
7. `market_data/src/market_data/collectors/websocket_tick_collector.py` - Add mode prefix
8. `market_data/src/market_data/api_service.py` - Add mode prefix
9. `load_today_historical.py` - Add mode prefix
10. `aggregate_timeframes.py` - Add mode prefix

**Priority 3 (Clean Startup):**
11. `start_unified.py` - Implement service filtering by mode

---

## Next Steps

**IMMEDIATE ACTION (User can do now - market closed):**
1. Fix volume bug in 2 files
2. Test with existing data
3. Verify volume shows non-zero

**WHEN MARKET OPENS:**
1. Implement data isolation
2. Test clean startup
3. Verify live WebSocket ticks flow correctly

**Market Status:** CLOSED (February 3, 2026)
**Can Test:** Volume aggregation with historical data ✅
**Cannot Test:** Live WebSocket ticks (need market open) ❌
