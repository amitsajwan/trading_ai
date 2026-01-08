# Market Data API Contract

## Base URL
`http://localhost:8004`

## Health Check

### GET /health
Check service health and dependencies.

**Response:**
```json
{
  "status": "healthy" | "degraded",
  "module": "market_data",
  "timestamp": "2024-01-01T00:00:00",
  "dependencies": {
    "redis": "healthy" | "unhealthy",
    "store": "initialized" | "not_initialized"
  }
}
```

## Market Data Endpoints

### GET /api/v1/market/tick/{instrument}
Get latest tick data for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol (e.g., "BANKNIFTY", "NIFTY")

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "timestamp": "2024-01-01T00:00:00",
  "last_price": 45000.0,
  "volume": 1234567
}
```

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

## Data Sources

The API retrieves data from:
1. **Redis Store** - Primary source for real-time data
2. **Technical Indicators Service** - Pre-calculated indicators
3. **Zerodha Kite API** - Options chain (requires API keys)

## Notes

- All data is collected by market data collectors (LTP, Depth collectors)
- Technical indicators are calculated in real-time as data arrives
- Options chain requires Kite API credentials to be configured
- Data availability depends on collectors being running and configured
