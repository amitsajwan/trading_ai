# Market Data API Verification Guide

## Overview

This document describes how to verify all Market Data API endpoints have data, for both **historical** and **live** modes.

## API Endpoints

### Critical Endpoints (Must Have Data)

1. **GET /health** - Service health check
2. **GET /api/v1/market/tick/{instrument}** - Latest tick data
3. **GET /api/v1/market/price/{instrument}** - Latest price (fast access)
4. **GET /api/v1/market/raw/{instrument}** - Raw Redis data
5. **GET /api/v1/market/ohlc/{instrument}** - OHLC bars (requires candle builder)

### Optional Endpoints (Nice to Have)

6. **GET /api/v1/options/chain/{instrument}** - Options chain (requires market hours)
7. **GET /api/v1/technical/indicators/{instrument}** - Technical indicators (needs sufficient data)
8. **GET /api/v1/market/depth/{instrument}** - Market depth (requires live market hours)

## Verification Script

Use `verify_market_data_apis.py` to test all endpoints:

```bash
# For historical mode
python start_local.py --provider historical --historical-from 2026-01-07
# Wait for replay to complete, then:
python verify_market_data_apis.py

# For live mode
python start_local.py --provider zerodha
# Wait for collectors to start, then:
python verify_market_data_apis.py
```

## Expected Results

### Historical Mode

| Endpoint | Expected Status | Notes |
|----------|----------------|-------|
| /health | ✅ healthy or ⚠️ degraded | May show stale_data (expected for historical) |
| /api/v1/market/tick/BANKNIFTY | ✅ | Should have price and timestamp |
| /api/v1/market/price/BANKNIFTY | ✅ | Should have price |
| /api/v1/market/raw/BANKNIFTY | ✅ | Should show Redis keys |
| /api/v1/market/ohlc/BANKNIFTY | ⚠️ | Requires candle builder (may not be set up) |
| /api/v1/options/chain/BANKNIFTY | ⚠️ | May work if market hours |
| /api/v1/technical/indicators/BANKNIFTY | ⚠️ | Needs sufficient data |
| /api/v1/market/depth/BANKNIFTY | ⚠️ | May work if market hours |

### Live Mode

| Endpoint | Expected Status | Notes |
|----------|----------------|-------|
| /health | ✅ healthy | Should show fresh_data |
| /api/v1/market/tick/BANKNIFTY | ✅ | Real-time price updates |
| /api/v1/market/price/BANKNIFTY | ✅ | Real-time price |
| /api/v1/market/raw/BANKNIFTY | ✅ | Should show Redis keys |
| /api/v1/market/ohlc/BANKNIFTY | ⚠️ | Requires candle builder |
| /api/v1/options/chain/BANKNIFTY | ✅ | Should work during market hours |
| /api/v1/technical/indicators/BANKNIFTY | ⚠️ | Needs time to calculate |
| /api/v1/market/depth/BANKNIFTY | ✅ | Should work during market hours |

## Data Flow

### Historical Mode
```
Zerodha Historical API → HistoricalTickReplayer → MarketStore.store_tick() → Redis
```

### Live Mode
```
Zerodha Live API → LTP Collector → MarketStore.store_tick() → Redis
```

Both modes write to the same Redis keys:
- `tick:{instrument}:latest` - Latest tick data
- `price:{instrument}:latest` - Latest price
- `price:{instrument}:latest_ts` - Latest timestamp

## OHLC Data

OHLC bars require a **CandleBuilder** to aggregate ticks into candles. The candle builder:
- Processes ticks as they arrive
- Aggregates into time-based candles (1min, 5min, etc.)
- Stores OHLC bars via `store.store_ohlc()`

**Note:** The current setup may not have a candle builder running automatically. OHLC data will only be available if:
1. A candle builder is configured and running
2. Ticks are being processed through the candle builder
3. Enough time has passed to generate candles

## Verification Checklist

### Historical Mode
- [ ] Start historical replay: `python start_local.py --provider historical --historical-from YYYY-MM-DD`
- [ ] Wait for replay to complete (check logs for "Replay complete")
- [ ] Run verification: `python verify_market_data_apis.py`
- [ ] Verify critical endpoints (tick, price, raw) have data
- [ ] Note: OHLC may not be available without candle builder

### Live Mode
- [ ] Start live collectors: `python start_local.py --provider zerodha`
- [ ] Wait for collectors to start (check logs for "LTP collector started")
- [ ] Wait 5-10 seconds for initial data collection
- [ ] Run verification: `python verify_market_data_apis.py`
- [ ] Verify critical endpoints have fresh data
- [ ] Verify options chain works (during market hours)
- [ ] Verify depth data works (during market hours)

## Troubleshooting

### No Tick Data
- Check Redis is running: `docker-compose -f docker-compose.data.yml ps`
- Check Redis keys: `redis-cli keys "tick:*"`
- Verify collectors/replayer are running (check logs)

### No OHLC Data
- OHLC requires candle builder (may not be configured)
- This is expected if candle builder is not running
- Ticks are still available via `/api/v1/market/tick`

### Stale Data Warning
- Historical mode: Expected (data is from past date)
- Live mode: Check collectors are running and updating

### Options Chain Not Available
- Requires market hours (9:15 AM - 3:30 PM IST)
- Requires valid Zerodha credentials
- May take time to initialize

## Success Criteria

**Minimum (Critical):**
- ✅ Health endpoint returns healthy or degraded (with data)
- ✅ Tick endpoint returns price > 0
- ✅ Price endpoint returns price > 0
- ✅ Raw endpoint shows Redis keys

**Full (All Endpoints):**
- ✅ All critical endpoints pass
- ✅ OHLC endpoint has data (if candle builder configured)
- ✅ Options chain available (during market hours)
- ✅ Technical indicators calculated (with sufficient data)
- ✅ Market depth available (during market hours)

