# GenAI Agent Data Reference

This document provides a comprehensive reference for all market data available to GenAI orchestrator agents. The system streams live market data that agents can consume via REST APIs and real-time WebSocket/STOMP subscriptions.

## System Overview

The platform provides three main data access methods:
1. **REST APIs** (`http://localhost:8004`) - Historical and current data
2. **Dashboard APIs** (`http://localhost:8000`) - Aggregated views and status
3. **Real-time Streaming** (`ws://localhost:8000/ws`) - Live updates via STOMP over WebSocket

## Canonical startup (how to run)

Use repo-root scripts as the single source of truth.

### Windows PowerShell (recommended)

- Live Zerodha streaming:
  - `./start_system.ps1 -Source kite`
- Historical replay (real Zerodha, fail-fast):
  - `./stop_system.ps1; ./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1 -FreshStart`
- Mock/dev mode:
  - `./start_system.ps1 -Source mock`
- Stop all:
  - `./stop_system.ps1`

### Bash / WSL (secondary)

- `./start_all.sh --source kite`
- `./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1`
- `./start_all.sh --source mock`
- `./stop_all.sh`

### After startup, always verify

- API health: `GET http://127.0.0.1:8004/health`
- Dashboard health: `GET http://127.0.0.1:8000/api/health`
- Mode: `GET http://127.0.0.1:8004/api/v1/system/mode`

## What data is created by the system

At runtime, collectors/replayers generate and update four main datasets per instrument:

1. **Tick/price stream** (latest price + timestamp + quote envelope)
2. **OHLC time-series** (`1min`, `5min`, `15min`, `1h`, etc.)
3. **Technical indicators** (RSI/MACD/ATR/OI-derived metrics, etc.)
4. **Depth and options snapshots** (when available from provider)

### Redis namespaces (mode isolation)

Data is written under mode prefixes:

- `live:*`
- `historical:*`
- `paper:*`

Examples:

- `live:ohlc_sorted:{instrument}:1min`
- `historical:ohlc_sorted:{instrument}:1min`
- `live:price:{instrument}:latest`
- `historical:price:{instrument}:latest`
- `live:depth:{instrument}:buy`
- `live:options:{instrument}:chain`

### Streaming events produced

The bridge publishes Redis-driven updates that appear as STOMP topics:

- `/topic/market/ohlc/{instrument}`
- `/topic/market/tick/{instrument}`
- `/topic/indicators/{instrument}`
- `/topic/market/depth/{instrument}`

This is the canonical “data we are creating” path:

**provider/replay → Redis keys → API endpoints → dashboard/WebSocket topics**

## Core Data Structures

### Market Tick
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timestamp": "2026-02-12T09:15:00Z",
  "last_price": 45000.25,
  "volume": 1250,
  "oi": 151230,
  "oi_day_high": 152000,
  "oi_day_low": 149500
}
```

### OHLC Bar
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timeframe": "1min",
  "open": 44950.00,
  "high": 45025.50,
  "low": 44925.75,
  "close": 45000.25,
  "volume": 1250,
  "oi": 151230,
  "start_at": "2026-02-12T09:15:00Z"
}
```

### Market Depth
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "buy": [
    {"price": 44999.00, "quantity": 100},
    {"price": 44998.50, "quantity": 250},
    {"price": 44998.00, "quantity": 150}
  ],
  "sell": [
    {"price": 45001.00, "quantity": 200},
    {"price": 45001.50, "quantity": 175},
    {"price": 45002.00, "quantity": 300}
  ],
  "timestamp": "2026-02-12T09:15:30Z"
}
```

### Options Chain
```json
{
  "instrument": "BANKNIFTY",
  "expiry": "2026-02-12",
  "futures_price": 45000.25,
  "pcr": 1.25,
  "max_pain": 44950.00,
  "strikes": [
    {
      "strike": 44500,
      "ce_ltp": 525.50,
      "ce_oi": 125000,
      "ce_volume": 25000,
      "ce_iv": null,
      "pe_ltp": 25.75,
      "pe_oi": 98000,
      "pe_volume": 18500,
      "pe_iv": null
    }
  ],
  "timestamp": "2026-02-12T09:15:00Z"
}
```

## Technical Indicators

The system calculates comprehensive technical indicators using pandas-ta. All indicators are updated every 30 seconds.

### Available Indicators

#### Trend Indicators
- **Moving Averages**: `sma_10`, `sma_20`, `sma_50`, `ema_10`, `ema_20`, `ema_50`, `wma_20`
- **Trend Strength**: `adx_14`, `di_plus`, `di_minus`
- **Ichimoku Cloud**: `ichimoku_tenkan`, `ichimoku_kijun`, `ichimoku_senkou_a`, `ichimoku_senkou_b`

#### Momentum Indicators
- **RSI**: `rsi_14`, `rsi_9`
- **Stochastic**: `stoch_k`, `stoch_d`
- **Williams %R**: `williams_r`
- **MACD**: `macd_value`, `macd_signal`, `macd_histogram`
- **Rate of Change**: `roc_12`
- **Momentum**: `momentum_10`

#### Volatility Indicators
- **Bollinger Bands**: `bollinger_upper`, `bollinger_middle`, `bollinger_lower`, `bollinger_width`, `bollinger_percent_b`
- **Average True Range**: `atr_14`, `atr_20`

#### Volume Indicators
- **On Balance Volume**: `obv`
- **Volume SMA**: `volume_sma_20`
- **Volume RSI**: `volume_rsi_14`
- **Chaikin Money Flow**: `cmf_20`

#### Open Interest Indicators
- **Current OI**: `oi`
- **OI Change**: `oi_change`, `oi_pct_change`
- **OI Trend**: `oi_sma_5`, `oi_ema_10`, `oi_momentum_5`

#### Oscillators
- **Commodity Channel Index**: `cci_20`
- **Money Flow Index**: `mfi_14`

#### Support/Resistance
- **Pivot Points**: `pivot_point`, `pivot_r1`, `pivot_r2`, `pivot_s1`, `pivot_s2`
- **Price Levels**: `high_20`, `low_20`, `range_20`

#### Derived Signals
- **Signal Strength**: `signal_strength` (0-100 composite score)
- **Volume Ratio**: `volume_ratio`
- **Support/Resistance Levels**: `support_level`, `resistance_level`
- **Trend Analysis**: `trend_direction` ("UP", "DOWN", "SIDEWAYS"), `trend_strength` (0-100)
- **RSI Status**: `rsi_status` ("OVERSOLD", "OVERBOUGHT", "NEUTRAL")
- **Volatility Level**: `volatility_level` ("LOW", "MEDIUM", "HIGH")

### Indicator Response Format
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timestamp": "2026-02-12T09:15:30Z",
  "indicators": {
    "rsi_14": 65.25,
    "macd_value": 12.50,
    "bollinger_upper": 45125.75,
    "adx_14": 28.45,
    "trend_direction": "UP",
    "signal_strength": 78.50
  }
}
```

## REST API Endpoints

### Market Data API (Port 8004)

#### Health & Status
- `GET /health` - System health check
- `GET /health/detailed` - Detailed health with validation
- `GET /diagnostics` - Comprehensive system diagnostics
- `GET /api/v1/system/mode` - Current execution mode (LIVE/HISTORICAL)

#### Market Data
- `GET /api/v1/market/tick/{instrument}` - Latest tick data
- `GET /api/v1/market/price/{instrument}` - Current price with staleness check
- `GET /api/v1/market/ohlc/{instrument}?timeframe=1min&limit=100&order=desc` - OHLC bars
- `GET /api/v1/market/instruments` - Available instruments discovered from Redis/config
- `GET /api/v1/market/depth/{instrument}` - Market depth (buy/sell orders)
- `GET /api/v1/market/raw/{instrument}?limit=100` - Raw Redis keys for instrument
- `GET /api/v1/market/overview?symbol={instrument}` - 24h overview (high/low/VWAP/change)

#### Options Data
- `GET /api/v1/options/chain/{instrument}` - Full options chain with PCR/Max Pain

#### Technical Indicators
- `GET /api/v1/technical/indicators/{instrument}?timeframe=1min` - All technical indicators
- `GET /api/v1/technical/status` - Indicator service status

### Dashboard API (Port 8000)

#### Status & Health
- `GET /api/health` - Dashboard health
- `GET /api/market-data/health` - Market data proxy health
- `GET /api/v1/system/mode` - System mode (proxied)

#### Market Data (Proxied + Enhanced)
- `GET /api/market-data/ohlc/{instrument}?timeframe=1min&limit=100` - OHLC with auto-discovery
- `GET /api/market-data/indicators/{instrument}?timeframe=1min` - Technical indicators
- `GET /api/market-data/instruments` - Available instruments
- `GET /api/market-data/depth/{instrument}` - Market depth
- `GET /api/market-data/options/{instrument}` - Options chain (mode-aware status + stale fallback)
- `GET /api/market-data/status` - Comprehensive status view

### Dashboard options endpoint status semantics

`GET /api/market-data/options/{instrument}` may return:

- `status: "ok"` → fresh options chain present
- `status: "stale"` → last-good cached options chain served due to upstream slowness/error
- `status: "no_data"` → no chain currently available for instrument/mode
- `status: "error"` → unrecoverable dashboard-side failure

Additional fields that may be present:

- `warning` → upstream timeout/error context
- `mode_hint` → best-effort mode (`live`/`historical`/`paper`) used for user messaging

## Real-Time Streaming (WebSocket + STOMP)

### Connection Details
- **URL**: `ws://localhost:8000/ws`
- **Protocol**: STOMP over WebSocket
- **Supported Subprotocols**: `v12.stomp`, `v11.stomp`, `v10.stomp`, `stomp`

### STOMP Subscription Topics

#### Market Data Topics
- `/topic/market/ohlc/{instrument}` - All OHLC timeframes for instrument
- `/topic/market/ohlc/{instrument}/{timeframe}` - Specific timeframe OHLC
- `/topic/market/tick/{instrument}` - Live tick updates
- `/topic/market/depth/{instrument}` - Market depth updates

#### Technical Indicators
- `/topic/indicators/{instrument}` - All indicator updates for instrument

#### System Status
- `/topic/auth/status` - Authentication/connection status

### STOMP Message Format
```javascript
// Subscribe to OHLC updates
STOMP.subscribe('/topic/market/ohlc/BANKNIFTY26JANFUT', function(message) {
  const data = JSON.parse(message.body);
  console.log('OHLC Update:', data);
});

// Subscribe to indicators
STOMP.subscribe('/topic/indicators/BANKNIFTY26JANFUT', function(message) {
  const indicators = JSON.parse(message.body);
  console.log('Indicators:', indicators);
});
```

### Real-Time Message Examples

#### OHLC Update
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timeframe": "1min",
  "open": 44950.00,
  "high": 45025.50,
  "low": 44925.75,
  "close": 45000.25,
  "volume": 1250,
  "start_at": "2026-02-12T09:15:00Z"
}
```

#### Indicator Update
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timestamp": "2026-02-12T09:15:30Z",
  "rsi_14": 65.25,
  "macd_value": 12.50,
  "trend_direction": "UP",
  "signal_strength": 78.50,
  "oi": 151230,
  "oi_change": 340,
  "oi_sma_5": 150980,
  "intrabar": false,
  "candle_closed": true,
  "update_type": "candle"
}
```

> Note: Redis/STOMP indicator topic messages contain a flattened indicator payload (not nested under `indicators`). REST indicator API responses remain nested under `{"indicators": {...}}`.

#### Tick Update
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timestamp": "2026-02-12T09:15:45Z",
  "last_price": 45005.75,
  "volume": 1300
}
```

## Data Storage & Keys

### Redis Key Patterns

#### Market Data
- `price:{instrument}:latest` - Current price
- `price:{instrument}:latest_ts` - Price timestamp
- `price:{instrument}:volume` - Volume data
- `ohlc:{instrument}:{timeframe}:{timestamp}` - Individual OHLC bars
- `ohlc_sorted:{instrument}:{timeframe}` - Sorted set of OHLC bars
- `depth:{instrument}:buy` - Buy depth
- `depth:{instrument}:sell` - Sell depth

#### Technical Indicators
- `indicators:{instrument}:{indicator_name}` - Individual indicator values

#### Options Data
- `options:{instrument}:chain` - Options chain data

#### System State
- `system:execution_mode` - Current mode (LIVE/HISTORICAL)
- `system:virtual_time:enabled` - Virtual time status
- `system:virtual_time:current` - Current virtual time

## Agent Integration Examples

### Python Agent Example
```python
import requests
import websocket
import json
import stomp

# REST API access
def get_market_data(instrument):
    response = requests.get(f'http://localhost:8004/api/v1/market/ohlc/{instrument}?limit=50')
    return response.json()

def get_indicators(instrument):
    response = requests.get(f'http://localhost:8004/api/v1/technical/indicators/{instrument}')
    return response.json()

# Real-time streaming
def on_message(frame):
    data = json.loads(frame.body)
    # Process real-time data
    print(f"Received: {data}")

# Connect to WebSocket
conn = stomp.Connection([('localhost', 8000)], heartbeats=(10000, 10000))
conn.connect()
conn.subscribe('/topic/market/ohlc/BANKNIFTY26JANFUT', on_message)
```

### JavaScript/Node.js Agent Example
```javascript
const WebSocket = require('ws');
const Stomp = require('stompjs');

// REST API calls
async function getMarketData(instrument) {
  const response = await fetch(`http://localhost:8004/api/v1/market/ohlc/${instrument}?limit=50`);
  return response.json();
}

async function getIndicators(instrument) {
  const response = await fetch(`http://localhost:8004/api/v1/technical/indicators/${instrument}`);
  return response.json();
}

// Real-time streaming
const ws = new WebSocket('ws://localhost:8000/ws', ['v12.stomp']);
const stompClient = Stomp.over(ws);

stompClient.connect({}, function(frame) {
  console.log('Connected: ' + frame);
  
  // Subscribe to OHLC updates
  stompClient.subscribe('/topic/market/ohlc/BANKNIFTY26JANFUT', function(message) {
    const data = JSON.parse(message.body);
    console.log('OHLC Update:', data);
  });
  
  // Subscribe to indicators
  stompClient.subscribe('/topic/indicators/BANKNIFTY26JANFUT', function(message) {
    const indicators = JSON.parse(message.body);
    console.log('Indicators:', indicators);
  });
});
```

## Data Update Frequencies

- **Ticks**: Real-time (as received from exchange)
- **OHLC Bars**: End of each timeframe period
- **Technical Indicators**: Every 30 seconds
- **Market Depth**: Real-time (as available)
- **Options Chain**: Every 30-60 seconds (market dependent)

## Error Handling

### Common HTTP Status Codes
- `200` - Success
- `404` - Instrument/data not found
- `500` - Server error
- `503` - Service unavailable (e.g., Kite credentials missing)

### WebSocket Error Handling
- Connection drops: Auto-reconnect recommended
- STOMP errors: Check subscription syntax
- Data parsing errors: Validate JSON structure

### Dashboard status levels (`/api/market-data/status`)
- `healthy`: API healthy and data flowing
- `degraded`: Redis/instrument data available but API health degraded/unreachable
- `warning`: API healthy but instrument data currently missing
- `critical`: no usable data path

Instrument entries can also report:

- `status: "available"`
- `status: "mode_mismatch"` (data exists, but from a different mode namespace)
- `status: "no_data"`

### Live mode operational notes (2026-02-13)

- Options chain for futures symbols (for example `BANKNIFTY26FEBFUT`) is fetched through underlying extraction (for example `BANKNIFTY`) in upstream API.
- Live options-chain calls can take ~10-20s depending on provider latency; dashboard proxy timeout is tuned to tolerate this window and avoid false `no_data`.
- Dashboard UI intentionally avoids tick-topic rendering load and uses throttled chart refresh + polling fallback under websocket instability.

## Best Practices for Agents

1. **Use appropriate polling intervals** - Don't overwhelm APIs
2. **Cache frequently accessed data** - Redis keys persist between requests
3. **Subscribe only to needed topics** - WebSocket subscriptions are per-client
4. **Handle connection failures gracefully** - Implement reconnection logic
5. **Validate data freshness** - Check timestamps for stale data
6. **Use batch requests** when possible for multiple instruments

## Available Instruments

The system auto-discovers instruments from Redis data. Common instruments include:
- `BANKNIFTY26JANFUT` - Bank Nifty Futures
- `NIFTY26JANFUT` - Nifty Futures
- `BANKNIFTY` - Bank Nifty Index
- `NIFTY` - Nifty Index

Use `GET /api/market-data/instruments` to get currently available instruments.

---

*Last updated: February 13, 2026*

*This reference covers all data structures, endpoints, and streaming topics available to GenAI agents for market analysis and trading decisions.*