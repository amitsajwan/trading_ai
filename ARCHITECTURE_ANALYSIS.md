# ARCHITECTURE ANALYSIS - Zerodha Trading System

## Current Date: February 3, 2026 (Market Closed)

## Core Problems Identified

### 1. **Volume Aggregation Bug** ✅ IDENTIFIED
**Location:** `aggregate_timeframes.py` line 67

```python
# WRONG:
c['volume'] = bar['volume']  # Replaces instead of summing

# CORRECT:
c['volume'] += bar['volume']  # Must SUM volumes across all 1min bars in the period
```

**Impact:** All aggregated timeframes (5min, 15min, 1h, 4h) show only the LAST 1min bar's volume, not the total.

---

### 2. **Data Isolation Missing** ❌ CRITICAL ISSUE
**Problem:** LIVE and HISTORICAL data mix in same Redis keys

**Current State:**
- Both modes write to: `ohlc_sorted:{instrument}:{timeframe}`
- No mode prefix or separation
- Old data contamination when switching modes

**Solution Options:**

#### Option A: Redis Key Prefixes (RECOMMENDED)
```python
# LIVE mode
live:ohlc_sorted:BANKNIFTY26FEBFUT:1min
live:enhanced_ticks:BANKNIFTY26FEBFUT

# HISTORICAL mode  
historical:ohlc_sorted:BANKNIFTY26FEBFUT:1min
historical:enhanced_ticks:BANKNIFTY26FEBFUT

# MongoDB similar pattern
live_signals, live_decisions, live_trades
historical_signals, historical_decisions, historical_trades
```

#### Option B: Redis DB Numbers
```python
# DB 0 = LIVE
# DB 1 = HISTORICAL
```

**Prefer Option A** - More explicit, easier debugging, no DB limitations

---

### 3. **Service Confusion** ❌ ARCHITECTURE ISSUE
**Problem:** Don't know which services are for which mode

Let me analyze docker-compose.yml:

## Data Flow Architecture

### **LIVE MODE** (Real-time WebSocket)
```
Zerodha WebSocket API
    ↓ (real ticks with volume)
websocket-tick-collector-banknifty (Docker service)
    ↓ publish to Redis channel: raw_ticks:BANKNIFTY26FEBFUT
ltp-collector-banknifty (Docker service)
    ↓ reads raw_ticks, applies volume logic
    ↓ publish to Redis channel: enhanced_ticks:BANKNIFTY26FEBFUT
ohlc-aggregator (Docker service - SHOULD RUN IN LIVE)
    ↓ subscribes to enhanced_ticks
    ↓ creates 1min OHLC bars
    ↓ stores in Redis: ohlc_sorted:{instrument}:1min
    ↓ publishes to: 1min_candle:{instrument}
multi-timeframe-aggregator (MISSING SERVICE?)
    ↓ subscribes to 1min_candle
    ↓ aggregates to 5min/15min/1h/4h
    ↓ stores in Redis: ohlc_sorted:{instrument}:{timeframe}
market-data-api (Docker service)
    ↓ reads from Redis, calculates indicators
market-data-dashboard (Docker service)
    ↓ displays charts
```

### **HISTORICAL MODE** (Replay from files/API)
```
Historical Data File or Zerodha API
    ↓
historical-replay-service (Docker service)
    ↓ publishes to Redis: raw_ticks:* OR enhanced_ticks:*
    ↓ (unclear which channel)
ohlc-aggregator OR load_historical script
    ↓ creates OHLC bars
    ↓ stores in same Redis keys (❌ DATA MIXING!)
```

### **Current Issues:**
1. ✅ **Volume available**: Zerodha WebSocket provides volume in ticks
2. ✅ **LTP collector extracts volume**: `volume_str = await redis_client.get(volume_key)`
3. ✅ **OHLC aggregator uses volume**: `self.current_candle["volume"] = volume`
4. ❌ **Aggregate script doesn't SUM**: Line 67 bug
5. ❌ **No data isolation**: Same keys for LIVE/HISTORICAL
6. ❌ **Service confusion**: Don't know what runs when

---

## Simplified Architecture (What User Wants)

### Core Concept
> "we have some data price volume, option, depth, we need to create indicators and momentum, so easy"

### What We Actually Need (SIMPLE!)

#### **Data Sources**
1. **Price Data**: OHLC bars at multiple timeframes
2. **Volume Data**: Already in OHLC bars
3. **Options Data**: Strike prices, IV, Greeks
4. **Depth Data**: Order book (NOT IMPLEMENTED YET)

#### **Processing**
1. **Indicators**: RSI, MACD, Bollinger Bands (from OHLC)
2. **Momentum**: Rate of change, trends (from OHLC)

#### **Required Services (MINIMAL)**

**LIVE Mode:**
- `redis` - Data store
- `websocket-tick-collector` - Get real-time ticks
- `ltp-collector` - Process ticks
- `ohlc-aggregator` - Create 1min bars
- `multi-timeframe-aggregator` - Create 5min/15min/1h/4h bars
- `market-data-api` - REST API for dashboard
- `market-data-dashboard` - UI
- ❌ NOT NEEDED: `historical-replay-service`, `kite-auth-service` (only for auth)

**HISTORICAL Mode (Backtesting):**
- `redis` - Data store
- `historical-replay-service` - Replay old data
- `market-data-api` - REST API
- `market-data-dashboard` - UI
- ❌ NOT NEEDED: `websocket-tick-collector`, `ltp-collector`

---

## Recommended Fixes

### **Priority 1: Fix Volume Aggregation**
File: `aggregate_timeframes.py` line 67

```python
# Change from:
c['volume'] = bar['volume']

# To:
c['volume'] += bar['volume']
```

### **Priority 2: Add Data Isolation**
1. Add mode prefix to all Redis keys
2. Clear old data when switching modes
3. Separate MongoDB collections by mode

### **Priority 3: Clean Startup**
`start_unified.py --live` should:
1. ✅ Validate authentication
2. ✅ Clear LIVE Redis keys only
3. ✅ Load today's historical data (for chart initialization)
4. ✅ Aggregate into timeframes
5. ✅ Start ONLY live services:
   - websocket-tick-collector
   - ltp-collector
   - ohlc-aggregator
   - multi-timeframe-aggregator (if exists)
   - market-data-api
   - market-data-dashboard
6. ❌ DO NOT START:
   - historical-replay-service
   - Any services with "historical" in name

### **Priority 4: Multi-timeframe Real-time Aggregation**
Current: Manual script `aggregate_timeframes.py`
Needed: Service that subscribes to `1min_candle:*` and aggregates in real-time

---

## Questions to Answer (Next Steps)

1. Does `multi-timeframe-aggregator.py` exist? ✅ YES, in root
2. Is it integrated into docker-compose? ⚠️ NEED TO CHECK
3. How does historical-replay-service publish data? ⚠️ NEED TO CHECK
4. What's in MongoDB? ⚠️ NEED TO CHECK

---

## User's Core Request

> "we should be absolutely clear when we start system, it should start all components, all the not required components should not be there"

**Translation:**
- `start_unified.py --live` → Start ONLY live components
- `start_unified.py --historical` → Start ONLY historical components
- Clear separation, no mixing

**Current Problem:**
- Services start without mode awareness
- Data mixes between modes
- No clear boundary between LIVE and HISTORICAL architectures
