# Market Data API Contract

## Base URL
`http://localhost:8004`

**Note:** The API is **mode-agnostic** - same endpoints work for both live and historical modes. All data is served from Redis.

## Health Check

### GET /health
Check service health and dependencies.

**Response:**
```json
{
  "status": "healthy" | "degraded",
  "module": "market_data",
  "timestamp": "2026-01-08T12:00:00+05:30",
  "dependencies": {
    "redis": "healthy" | "unhealthy",
    "store": "initialized" | "not_initialized",
    "data_availability": "fresh_data_for_BANKNIFTY" | "stale_data_for_BANKNIFTY_age_3600s" | "missing_price_data_for_BANKNIFTY"
  }
}
```

**Status Values:**
- `healthy` - All systems operational, data available
- `degraded` - Service running but data missing or stale

## Market Data Endpoints

### GET /api/v1/market/tick/{instrument}
Get latest tick data for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol (e.g., "BANKNIFTY", "NIFTY")

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "timestamp": "2026-01-08T12:00:00+05:30",
  "last_price": 59650.0,
  "volume": 1234567
}
```

**Note:** Timestamps are in IST (Indian Standard Time, UTC+05:30) format.

### GET /api/v1/market/ohlc/{instrument}
Get OHLC (Open/High/Low/Close) bars for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol
- `timeframe` (query, optional): Timeframe (default: "minute")
- `limit` (query, optional): Number of bars to return (default: 100)

**Response:**
```json
[
  {
    "instrument": "BANKNIFTY",
    "timeframe": "minute",
    "open": 45000.0,
    "high": 45100.0,
    "low": 44900.0,
    "close": 45050.0,
    "volume": 1234567,
    "start_at": "2024-01-01T00:00:00"
  }
]
```

### GET /api/v1/market/price/{instrument}
Get latest price data directly from Redis (fast access).

**Parameters:**
- `instrument` (path): Instrument symbol

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "price": 45000.0,
  "timestamp": "2024-01-01T00:00:00",
  "volume": 1234567,
  "source": "redis"
}
```

### GET /api/v1/market/raw/{instrument}
Get raw market data from Redis for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol
- `limit` (query, optional): Maximum number of keys to return (default: 100)

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "keys_found": 50,
  "data": {
    "price:BANKNIFTY:last_price": 45000.0,
    "price:BANKNIFTY:latest_ts": "2024-01-01T00:00:00",
    "price:BANKNIFTY:volume": 1234567
  },
  "timestamp": "2024-01-01T00:00:00"
}
```

## Options Chain Endpoints

### GET /api/v1/options/chain/{instrument}
Get options chain for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "expiry": "2024-01-25",
  "strikes": [
    {
      "strike": 45000,
      "call_oi": 12345,
      "put_oi": 12345,
      "call_ltp": 100.0,
      "put_ltp": 100.0
    }
  ],
  "timestamp": "2024-01-01T00:00:00"
}
```

## Technical Indicators Endpoints

### GET /api/v1/technical/indicators/{instrument}
Get technical indicators for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol
- `timeframe` (query, optional): Timeframe (default: "minute")

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "timestamp": "2024-01-01T00:00:00",
  "indicators": {
    "rsi_14": 65.5,
    "sma_20": 45000.0,
    "sma_50": 44800.0,
    "ema_20": 45020.0,
    "ema_50": 44850.0,
    "macd_value": 50.0,
    "macd_signal": 45.0,
    "macd_histogram": 5.0,
    "atr_14": 200.0,
    "bollinger_upper": 45200.0,
    "bollinger_middle": 45000.0,
    "bollinger_lower": 44800.0,
    "adx": 25.5,
    "volume_sma": 1000000,
    "volume_ratio": 1.2,
    "price_change_pct": 0.5,
    "volatility": 0.02
  }
}
```

**Available Indicators:**
- **Trend Indicators**: SMA (20, 50), EMA (20, 50)
- **Momentum Indicators**: RSI (14), MACD (value, signal, histogram)
- **Volatility Indicators**: ATR (14), Bollinger Bands (upper, middle, lower)
- **Volume Indicators**: Volume SMA, Volume Ratio
- **Other**: ADX, Price Change %, Volatility

## Error Responses

All endpoints may return:
- `404`: Resource not found (no data available)
- `500`: Internal server error
- `503`: Service unavailable (dependencies not initialized)

## Market Depth Endpoint

**GET** `/api/v1/market/depth/{instrument}`

Get market depth (order book) data.

**Parameters:**
- `instrument` (path): Instrument symbol

**Example:** `GET /api/v1/market/depth/BANKNIFTY`

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "buy": [
    {"price": 59650.0, "quantity": 100, "orders": 5},
    {"price": 59649.0, "quantity": 200, "orders": 8}
  ],
  "sell": [
    {"price": 59651.0, "quantity": 150, "orders": 6},
    {"price": 59652.0, "quantity": 180, "orders": 7}
  ],
  "timestamp": "2026-01-08T12:00:00+05:30"
}
```

---

## Data Sources

The API retrieves data from:
1. **Redis Store** - Primary source (populated by collectors or replay)
2. **Technical Indicators Service** - Pre-calculated indicators
3. **Zerodha Kite API** - Options chain (requires API keys)

## Mode Behavior

**Live Mode:**
- Data updated every 2-5 seconds
- Timestamps reflect current time (IST)
- Virtual time disabled

**Historical Mode:**
- Data from specified historical date
- Timestamps reflect historical time (IST)
- Virtual time enabled for system synchronization

**Both modes use the same API endpoints - no difference in API behavior.**

## Notes

- All data flows through Redis (mode-agnostic)
- Data collectors (live) or replay (historical) populate Redis
- Technical indicators calculated in real-time as data arrives
- Options chain requires Kite API credentials
- Data availability depends on collectors/replay being running
- Timestamps are always in IST (UTC+05:30) format
