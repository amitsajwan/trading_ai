# System Architecture - Live Trading System

**Last Updated:** February 6, 2026  
**Status:** ✅ Production Ready

## Overview

Real-time trading system with tick-to-dashboard data flow processing Zerodha market data.

## Data Flow Architecture

```
Zerodha WebSocket API
         ↓
WebSocket Tick Collector (zerodha-websocket-tick-collector-banknifty)
         ↓
Redis Pub/Sub (raw_ticks:BANKNIFTY26FEBFUT)
         ↓
Volume Enhancer (ltp-collector-banknifty)
         ↓ (with tick-by-tick volume)
Redis Pub/Sub (enhanced_ticks:BANKNIFTY26FEBFUT)
         ↓
OHLC Aggregator (ohlc-aggregator-banknifty)
         ↓ (1min, 5min, 15min, 1h, 4h, 1d candles)
Redis Storage (live:ohlc_sorted:BANKNIFTY26FEBFUT:{timeframe})
         ↓
Engine API (zerodha-engine-api)
         ↓ (technical indicators: RSI, SMA, EMA, MACD, etc.)
Redis Storage (indicators:*)
         ↓
Market Data API (zerodha-market-data-api)
         ↓ (REST API on port 8004)
Dashboard (zerodha-market-data-dashboard)
         ↓ (WebUI on port 8008)
Live Charts & Options Chain
```

## Core Services (8 Services)

### 1. **redis** (Port 6380→6379)
- In-memory data store
- Pub/Sub message broker
- Key-value storage for ticks, candles, indicators

### 2. **mongodb** (Port 27017)
- Historical data persistence
- OHLC backup storage

### 3. **redis-ws-gateway**
- WebSocket gateway for Redis pub/sub
- Real-time data streaming to dashboard

### 4. **websocket-tick-collector-banknifty**
- Connects to Zerodha WebSocket API
- Receives real-time tick data
- Publishes to `raw_ticks:BANKNIFTY26FEBFUT`

### 5. **ltp-collector-banknifty** (Volume Enhancer)
- Subscribes to raw ticks
- Extracts tick-by-tick volume (`last_traded_quantity`)
- Publishes to `enhanced_ticks:BANKNIFTY26FEBFUT`

### 6. **ohlc-aggregator-banknifty**
- Subscribes to enhanced ticks
- Aggregates into OHLC candles (1min, 5min, 15min, 1h, 4h, 1d)
- Stores in Redis sorted sets

### 7. **engine-api** (Port 8006)
- Calculates technical indicators (RSI, SMA, EMA, MACD, Bollinger Bands, etc.)
- Processes OHLC data
- Stores indicators in Redis

### 8. **market-data-api** (Port 8004)
- REST API serving market data
- Endpoints:
  - `/health` - Health check
  - `/api/v1/ticks/{instrument}` - Latest tick
  - `/api/v1/candles/{instrument}` - OHLC data
  - `/api/v1/options/chain/{underlying}` - Options chain
  - `/api/v1/indicators/{instrument}` - Technical indicators

### 9. **market-data-dashboard** (Port 8008)
- Web dashboard
- Real-time price charts
- Options chain visualization
- Volume data

## Volume Calculation Logic

**Priority Order:**
1. `last_traded_quantity` (tick-by-tick delta) ✅ **PRIMARY**
2. `candle_volume` (delta from OHLC)
3. `volume_traded`, `volume`, `cumulative_volume` (cumulative fallback)

**Implementation:** `market_data/src/market_data/processors/volume_enhancer.py`

## Options Chain

**Provider:** Zerodha Options API  
**Calculations:** Greek calculations (Delta, Gamma, Theta, Vega) when scipy available  
**Fallback:** Returns chain without Greeks if calculations unavailable  
**Implementation:** `market_data/src/market_data/adapters/zerodha_options_chain.py`

## Redis Data Structure

### Tick Data
- **Key:** `websocket:tick:{INSTRUMENT}:latest`
- **Format:** JSON with last_price, volume, timestamp, OHLC, depth

### OHLC Data
- **Key:** `live:ohlc_sorted:{INSTRUMENT}:{TIMEFRAME}`
- **Format:** Sorted set (timestamp → JSON OHLC bar)

### Indicators
- **Key:** `indicators:{INSTRUMENT}:{INDICATOR_NAME}`
- **Format:** Time-series data

### Pub/Sub Channels
- `raw_ticks:{INSTRUMENT}` - Raw WebSocket ticks
- `enhanced_ticks:{INSTRUMENT}` - Volume-enhanced ticks
- `live:enhanced_ticks:{INSTRUMENT}` - Live mode enhanced ticks
- `market:tick:{INSTRUMENT}:{TYPE}` - Market tick broadcasts

## Startup Process

**Script:** `start_live_validated.py`

### Step 1: Pre-Flight Validation
- ✅ Check `credentials.json` exists
- ✅ Validate Kite API credentials
- ✅ Verify Docker is running

### Step 2: Environment Cleanup
- Stop mock services
- Stop historical replay
- **Flush Redis cache** (`FLUSHALL`)
- **Stop Redis + remove Docker volume** (ensures fresh start)
- Clear MongoDB OHLC collections
- Clear virtual time flags

### Step 3: Start Services
- Start all 8 services via `docker compose up`
- Wait for containers to initialize

### Step 4: Health Checks
- Redis ping
- Market Data API `/health`
- Dashboard accessibility
- Engine API health (port 8006)
- WebSocket collector logs

### Step 5: Data Pipeline Validation
- Wait 12 seconds for fresh WebSocket ticks
- Verify price in Redis (expected range: ₹50,000-70,000)
- Check data source is ZERODHA (not mock)
- Verify no mock services running

### Result
```
✅ LIVE MODE STARTED SUCCESSFULLY

Dashboard:  http://localhost:8008
API:        http://localhost:8004
Validated:  2026-02-06 10:26:58

✅ Real Zerodha data confirmed - prices validated
✅ All services healthy and connected
```

## Key Fixes Applied

### Issue 1: Volume Data Showing Zero ✅ FIXED
**Problem:** Volume enhancer returning 0 despite ticks containing real volume  
**Root Cause:** Prioritized cumulative `volume_traded` which didn't change tick-to-tick  
**Solution:** Reprioritized to `last_traded_quantity` (tick-by-tick delta) first  
**Result:** Now showing real volumes: 30, 171, 156, 189 per tick

### Issue 2: Old Cached Data (45k price) ✅ FIXED
**Problem:** Stale ₹45k price appearing despite real ₹60k market price  
**Root Cause:** Docker Redis persistent volume retained old data  
**Solution:** Multi-layer cleanup:
  - Redis `FLUSHALL`
  - MongoDB OHLC collections cleanup
  - Stop Redis + remove Docker volume
  - 12-second wait for fresh ticks
**Result:** Startup validates with real price ₹60,124

### Issue 3: Empty Options Chain ✅ FIXED
**Problem:** `'NoneType' object is not callable` error  
**Root Cause:** `time_to_expiry()` called before scipy loaded  
**Solution:** Moved call inside `OPTIONS_CALCULATIONS_AVAILABLE` check  
**Result:** Returns 129 strikes successfully

## Configuration Files

- **Root `.env`** - Main environment configuration
- **`credentials.json`** - Zerodha API credentials (API key + access token)
- **`config.py`** - Python configuration
- **`docker-compose.yml`** - Docker services definition

## Utility Scripts

- **`start_live_validated.py`** ✅ - Validated startup with automatic checks
- **`check_status.py`** - System status
- **`check_live_prices.py`** - Live price verification
- **`check_redis_data.py`** - Redis data inspection
- **`check_indicators.py`** - Indicator data check
- **`check_options.py`** - Options chain check
- **`check_instruments.py`** - Instrument data
- **`check_data_freshness.py`** - Data timestamp validation
- **`verify_api_keys.py`** - API key validation

## Project Structure

```
zerodha/
├── market_data/                    # Market data module
│   ├── src/market_data/           # Source code
│   │   ├── adapters/              # Data adapters (Zerodha, options)
│   │   ├── collectors/            # Data collectors
│   │   ├── processors/            # Data processors (volume enhancer)
│   │   ├── sources/               # WebSocket sources
│   │   ├── ohlc/                  # OHLC aggregation
│   │   ├── services/              # Business logic services
│   │   ├── tools/                 # CLI tools (auth)
│   │   ├── api_service.py         # Market Data API
│   │   ├── store.py               # Redis storage
│   │   └── technical_indicators_service.py
│   ├── tests/                     # Test suite
│   └── README.md                  # Module documentation
├── docker-compose.yml             # Main Docker configuration
├── start_live_validated.py        # Validated startup script
├── credentials.json               # Zerodha API credentials
└── SYSTEM_ARCHITECTURE.md         # This file
```

## API Endpoints

### Market Data API (Port 8004)

```bash
# Health check
GET http://localhost:8004/health

# Latest tick
GET http://localhost:8004/api/v1/ticks/BANKNIFTY26FEBFUT

# OHLC candles
GET http://localhost:8004/api/v1/candles/BANKNIFTY26FEBFUT?timeframe=5min&limit=100

# Options chain
GET http://localhost:8004/api/v1/options/chain/BANKNIFTY26FEBFUT

# Technical indicators
GET http://localhost:8004/api/v1/indicators/BANKNIFTY26FEBFUT
```

### Dashboard (Port 8008)

```
http://localhost:8008
```

## Data Guarantees

✅ **Real-time:** Sub-second tick latency from Zerodha  
✅ **Accuracy:** Tick-by-tick volume calculation  
✅ **Reliability:** Automatic health checks & validation  
✅ **Fresh Data:** Cache clearing on startup  
✅ **No Mock Data:** Validation rejects mock data (price range check)

## Current Market

- **Instrument:** BANKNIFTY26FEBFUT (Bank Nifty Feb 2026 Futures)
- **Current Price:** ₹60,080 - ₹60,125 (as of 2026-02-06 10:27 IST)
- **Volume:** Real tick-by-tick (30, 171, 156, 189 per tick)
- **Options Chain:** 129 strikes active

## Maintenance

- **Start System:** `python start_live_validated.py`
- **Stop System:** `docker compose down`
- **View Logs:** `docker logs <service-name>`
- **Restart Service:** `docker compose restart <service-name>`
- **Clear Cache:** Handled automatically by startup script

## Status

**System Status:** ✅ Production Ready  
**Last Validated:** 2026-02-06 10:26:58 IST  
**Data Quality:** ✅ Real Zerodha data confirmed  
**All Services:** ✅ Healthy and connected
