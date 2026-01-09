# Market Data Module

**Status: ✅ Production Ready**

A production-ready market data module for trading systems. Provides REST API access to market data from both **live** and **historical** sources via Zerodha API, with Redis-backed persistence.

## 🎯 Core Concept

The Market Data API is **mode-agnostic** - it reads from Redis regardless of data source. Two modes populate Redis differently:

- **LIVE MODE**: Real-time data collectors continuously update Redis
- **HISTORICAL MODE**: Historical replay populates Redis with past data

The same API code serves both modes seamlessly.

---

## 📊 Operating Modes

### Mode 1: Live Data Mode

**What it does:**
- Collects real-time market data from Zerodha API
- Updates Redis every 2-5 seconds with current prices
- Uses real system time (no virtual time)

**How to start:**
```powershell
# From project root
python start_local.py --provider zerodha
```

**What gets started:**
- LTP Collector (Last Traded Price) - updates every 2 seconds
- Depth Collector (Market Depth) - updates every 5 seconds
- Market Data API (port 8004) - serves data from Redis

**Key characteristics:**
- Virtual Time: **DISABLED**
- Data timestamps: Current time (IST)
- Data freshness: < 5 minutes (if market is open)

---

### Mode 2: Historical Replay Mode

**What it does:**
- Fetches historical data from Zerodha API or CSV file
- Replays it into Redis at configurable speed
- Can replay data from any date (past or today)

**How to start:**
```powershell
# From project root
python start_local.py --provider historical --historical-source zerodha --historical-speed 10 --historical-from 2026-01-07
```

**Arguments:**
- `--provider historical` - Enables historical replay mode
- `--historical-source zerodha` - Use Zerodha API for data (or `path/to/file.csv` for CSV)
- `--historical-speed 10` - Replay speed (0.0 = instant, 1.0 = real-time, 10 = 10x speed)
- `--historical-from 2026-01-07` - Start date for replay (YYYY-MM-DD format)

**What gets started:**
- Historical Replay Service - fetches and replays data
- Market Data API (port 8004) - serves data from Redis

**Key characteristics:**
- Virtual Time: **ENABLED** (for system-wide time synchronization)
- Data timestamps: From the specified historical date
- Replay speed: Configurable (0.0 to any multiplier)

---

## 🚀 Quick Start

### Prerequisites

1. **Redis** running on `localhost:6379`
2. **Python 3.8+** with dependencies installed
3. **Zerodha credentials** (for live mode or Zerodha historical data)

### Step 1: Start Data Services

```powershell
# Start Redis (if using Docker)
docker-compose -f docker-compose.data.yml up -d redis
```

### Step 2: Configure Credentials

Set environment variables or use `credentials.json`:
```bash
KITE_API_KEY="your_api_key"
KITE_API_SECRET="your_api_secret"
KITE_ACCESS_TOKEN="your_access_token"  # Optional - auto-generated
```

### Step 3: Start in Your Desired Mode

**For Live Mode:**
```powershell
python start_local.py --provider zerodha
```

**For Historical Mode:**
```powershell
python start_local.py --provider historical --historical-source zerodha --historical-speed 10 --historical-from 2026-01-07
```

**Runner (supervisor) usage:**
You can also start market-data using the built-in supervisor runner which spawns the API, collectors and historical replayer as separate processes:

```powershell
# Live with collectors started by the runner
python -m market_data.runner --mode live --start-collectors

# Historical via runner
python -m market_data.runner --mode historical --historical-source zerodha --historical-from 2026-01-07
```

**Credential check:**
- When starting collectors in live mode (`--start-collectors`) the runner will validate Zerodha credentials before launching collectors.
- If credentials are missing or invalid the runner will refuse to start collectors and print clear instructions:
  - Set `KITE_API_KEY` and `KITE_ACCESS_TOKEN` in the environment, OR
  - Run `python -m market_data.tools.kite_auth` to generate `credentials.json`, OR
  - Set `USE_MOCK_KITE=1` to start collectors in mock mode for testing.

---

## Zerodha Historical Data Integration

Detailed Zerodha historical integration and examples were consolidated here from `ZERODHA_HISTORICAL_INTEGRATION.md`.

Summary:
- Supports `data_source='zerodha'` (real historical data via Kite API), `path/to/file.csv`, or `synthetic`.
- `HistoricalTickReplayer` and `UnifiedDataFlow` can fetch Zerodha OHLC candles, convert them into tick sequences, and replay into the Redis-backed store.
- Usage example (simplified):

```python
from datetime import date, timedelta
from kiteconnect import KiteConnect
from market_data.adapters.unified_data_flow import UnifiedDataFlow
from market_data.store import InMemoryMarketStore

kite = KiteConnect(api_key="...")
kite.set_access_token("...")

flow = UnifiedDataFlow(
    store=InMemoryMarketStore(),
    data_source="zerodha",
    kite=kite,
    instrument_symbol="NIFTY BANK",
    from_date=date.today() - timedelta(days=30),
    to_date=date.today(),
    interval="minute",
)
flow.start()
```

Notes:
- Historical replay preserves timestamps and can rebase to a virtual time if needed.
- ``HistoricalTickReplayer`` supports multiple intervals and converts candles to tick-level sequences for realistic replay.
- For quick testing you can use synthetic mode: `data_source='synthetic'`.

For more details on parameters and advanced options see the module docstrings in `market_data.adapters.historical_tick_replayer` and the `UnifiedDataFlow` implementation.


### Step 4: Verify It's Working

```powershell
# Check health
python -c "import requests; print(requests.get('http://localhost:8004/health').json())"

# Or use verification script
cd market_data
python verify_modes.py
```

---

## 🔌 REST API Endpoints

The Market Data API exposes the following endpoints (all modes use the same API):

### Health Check

**GET** `/health`

Check service health and data availability.

**Response:**
```json
{
  "status": "healthy",
  "module": "market_data",
  "timestamp": "2026-01-08T12:00:00+05:30",
  "dependencies": {
    "redis": "healthy",
    "store": "initialized",
    "data_availability": "fresh_data_for_BANKNIFTY"
  }
}
```

### Market Data Endpoints

**GET** `/api/v1/market/tick/{instrument}`

Get latest tick data for an instrument.

**Example:** `GET /api/v1/market/tick/BANKNIFTY`

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "timestamp": "2026-01-08T12:00:00+05:30",
  "last_price": 59650.0,
  "volume": 1234567
}
```

**GET** `/api/v1/market/price/{instrument}`

Get latest price (fast access from Redis).

**Example:** `GET /api/v1/market/price/BANKNIFTY`

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "price": 59650.0,
  "timestamp": "2026-01-08T12:00:00+05:30",
  "source": "redis"
}
```

**GET** `/api/v1/market/ohlc/{instrument}`

Get OHLC (Open/High/Low/Close) bars.

**Parameters:**
- `timeframe` (query, optional): `minute`, `5minute`, `day` (default: `minute`)
- `limit` (query, optional): Number of bars (default: 100)

**Example:** `GET /api/v1/market/ohlc/BANKNIFTY?timeframe=minute&limit=10`

**Response:**
```json
[
  {
    "instrument": "BANKNIFTY",
    "timeframe": "minute",
    "open": 59600.0,
    "high": 59700.0,
    "low": 59550.0,
    "close": 59650.0,
    "volume": 1234567,
    "start_at": "2026-01-08T12:00:00+05:30"
  }
]
```

**GET** `/api/v1/market/raw/{instrument}`

Get raw market data keys from Redis.

**Parameters:**
- `limit` (query, optional): Max keys to return (default: 100)

**Example:** `GET /api/v1/market/raw/BANKNIFTY?limit=10`

### Options Chain

**GET** `/api/v1/options/chain/{instrument}`

Get options chain data.

**Example:** `GET /api/v1/options/chain/BANKNIFTY`

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "expiry": "2026-01-27",
  "strikes": [
    {
      "strike": 59500,
      "call_oi": 12345,
      "put_oi": 12345,
      "call_ltp": 100.0,
      "put_ltp": 95.0
    }
  ],
  "timestamp": "2026-01-08T12:00:00+05:30"
}
```

### Technical Indicators

**GET** `/api/v1/technical/indicators/{instrument}`

Get calculated technical indicators.

**Parameters:**
- `timeframe` (query, optional): `minute`, `5minute`, `day` (default: `minute`)

**Example:** `GET /api/v1/technical/indicators/BANKNIFTY?timeframe=minute`

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "timestamp": "2026-01-08T12:00:00+05:30",
  "indicators": {
    "rsi_14": 65.5,
    "sma_20": 59600.0,
    "ema_20": 59620.0,
    "macd_value": 50.0,
    "bollinger_upper": 59800.0,
    "bollinger_lower": 59400.0,
    "atr_14": 200.0,
    "adx": 25.5
  }
}
```

**Available Indicators:**
- Trend: SMA (20, 50), EMA (20, 50)
- Momentum: RSI (14), MACD
- Volatility: ATR (14), Bollinger Bands
- Volume: Volume SMA, Volume Ratio
- Other: ADX, Price Change %, Volatility

### Market Depth

**GET** `/api/v1/market/depth/{instrument}`

Get market depth (order book) data.

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

## 🔄 Mode Switching

### From Live to Historical

1. Stop live collectors (Ctrl+C or kill process)
2. Start historical replay:
   ```powershell
   python start_local.py --provider historical --historical-source zerodha --historical-speed 10 --historical-from 2026-01-07
   ```
3. API continues running (no restart needed)

### From Historical to Live

1. Stop historical replay (Ctrl+C or kill process)
2. Clear virtual time:
   ```powershell
   python -c "import redis; r=redis.Redis(); r.delete('system:virtual_time:enabled'); r.delete('system:virtual_time:current')"
   ```
3. Start live collectors:
   ```powershell
   python start_local.py --provider zerodha
   ```
4. API continues running (no restart needed)

---

## External dependencies

See below for the key external services and packages required by the module. These were previously kept in `EXTERNAL_DEPENDENCIES.md`.

### System services
- Redis (production): `redis:7-alpine` (default port 6379). Used for ticks, prices, OHLC, indicators.
- MongoDB (optional): `mongo:7` (for news and optional stores).

### Python packages
- Required (examples): `redis`, `kiteconnect`, `python-dotenv`, `uvicorn`, `fastapi`
- Optional (analysis): `pandas`, `numpy`

### Zerodha Kite Connect
- API keys: `KITE_API_KEY`, `KITE_API_SECRET` (from https://kite.zerodha.com/apps/)
- Access token is generated via `python -m market_data.tools.kite_auth` (interactive browser flow)

---

## Environment & deployment

This module supports per-module `.env` configuration. Use the example templates in the repository (e.g., `market_data/.env.example`, `genai_module/.env.example`) and copy them into a local `.env` file which you must not commit.

- Copy and edit module template:
  - `cp market_data/.env.example market_data/.env`
  - `cp genai_module/.env.example genai_module/.env`
  - `cp engine_module/.env.example engine_module/.env`
  - `cp news_module/.env.example news_module/.env`

- Docker compose services use the module-scoped env files (e.g. `market_data/.env.banknifty`).

**Note:** `start_local.py` will prefer a `local.env` if present, otherwise it will load per-module `.env` files (e.g., `market_data/.env`) if found.

## Troubleshooting

- Redis: `docker-compose -f docker-compose.data.yml up -d redis` and `redis-cli ping`
- Generate access token: `python -m market_data.tools.kite_auth`

---

## 📝 Command Line Arguments

### start_local.py Arguments

**Provider Selection:**
- `--provider zerodha` - Live mode with Zerodha data
- `--provider historical` - Historical replay mode
- `--provider mock` - Mock/simulator mode

**Historical Replay Options:**
- `--historical-source zerodha` - Use Zerodha API (or `path/to/file.csv` for CSV)
- `--historical-speed 10` - Replay speed multiplier
  - `0.0` = Instant (all ticks immediately)
  - `1.0` = Real-time speed
  - `10` = 10x faster than real-time
- `--historical-from 2026-01-07` - Start date (YYYY-MM-DD format)
- `--historical-ticks` - Use tick-level replayer (instead of bar-level)

**Other Options:**
- `--skip-validation` - Skip health checks during startup

### Examples

**Instant historical replay (for testing):**
```powershell
python start_local.py --provider historical --historical-source zerodha --historical-speed 0 --historical-from 2026-01-07
```

**Real-time speed historical replay:**
```powershell
python start_local.py --provider historical --historical-source zerodha --historical-speed 1.0 --historical-from 2026-01-07
```

**Fast historical replay (10x speed):**
```powershell
python start_local.py --provider historical --historical-source zerodha --historical-speed 10 --historical-from 2026-01-07
```

**Historical from CSV (no credentials needed):**
```powershell
python start_local.py --provider historical --historical-source data/historical.csv --historical-speed 0
```

---

## 🏗️ Architecture

(Consolidated docs) This README is the single canonical reference for the `market_data` module. Previously separate documents (EXTERNAL_DEPENDENCIES.md, QUICK_START.md, START_API.md) have been merged here — see the "External dependencies" and "Environment & deployment" sections below.


```
┌─────────────────────────────────────────────────────────┐
│                  DATA SOURCE LAYER                       │
├─────────────────────────────────────────────────────────┤
│  Live Mode: Zerodha API → Collectors → Redis            │
│  Historical Mode: Zerodha/CSV → Replayer → Redis        │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    REDIS STORAGE                         │
│  (tick:*, price:*, ohlc:*, indicators:*)                 │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              MARKET DATA API SERVICE                    │
│  (Port 8004) - Mode-Agnostic                             │
│  Reads from Redis, serves via REST API                  │
└─────────────────────────────────────────────────────────┘
```

**Key Points:**
- Redis is the bridge between data sources and API
- API service is mode-agnostic (same code for both modes)
- Data collectors/replay populate Redis
- API reads from Redis and serves via REST

---

## 🔧 Standalone API Service

You can start **only the API service** without data collectors/replay:

**From `market_data/` folder:**
```powershell
cd market_data
$env:PYTHONPATH = './src'; python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
```

**Note:** The API will only serve data that's already in Redis. If Redis is empty, endpoints will return errors.

**Environment Variables:**
- `MARKET_DATA_API_PORT` (default: `8004`)
- `MARKET_DATA_API_HOST` (default: `0.0.0.0`)

---

## ✅ Verification

### Verify Current Mode

**From `market_data/` folder:**
```powershell
cd market_data
python verify_modes.py
```

This script:
- Detects current mode (Live or Historical)
- Verifies API is running
- Checks Redis data and timestamps
- Tests all endpoints
- Reports pass/fail results

### Manual Verification

```powershell
# Check health
python -c "import requests; import json; r = requests.get('http://localhost:8004/health'); print(json.dumps(r.json(), indent=2))"

# Check latest tick
python -c "import requests; import json; r = requests.get('http://localhost:8004/api/v1/market/tick/BANKNIFTY'); print(json.dumps(r.json(), indent=2))"
```

---

## 📚 Related Documentation

- **API_CONTRACT.md** - Complete API endpoint documentation
- **HISTORICAL_SIMULATION_README.md** - Detailed historical replay guide
- **EXTERNAL_DEPENDENCIES.md** - Dependencies and setup details
- **START_API.md** - API startup commands reference

---

## 🎯 Key Design Principles

1. **Mode-Agnostic API**: Same API code works for both live and historical modes
2. **Redis as Bridge**: All data flows through Redis for consistency
3. **Real Data Only**: No synthetic data - uses Zerodha API or CSV files
4. **Production Ready**: Error handling, logging, health checks
5. **Easy Mode Switching**: Switch modes without restarting API

---

## 🐛 Troubleshooting

**API not responding:**
- Check if process is running: `netstat -ano | findstr :8004`
- Check API logs for errors
- Verify Redis is accessible: `redis-cli ping`

**No data in endpoints:**
- Check if data source is running (collectors or replay)
- Check Redis for data: `redis-cli keys "tick:*"`
- Verify credentials (for Zerodha data)

**Wrong mode detected:**
- Check virtual time: `redis-cli get system:virtual_time:enabled`
- Check timestamp age in Redis
- Verify data source is running

---

## ✅ Status

- ✅ **Real Data Sources**: Zerodha API and CSV files
- ✅ **Redis Storage**: Production-ready persistence
- ✅ **Historical Replay**: Configurable speed and date range
- ✅ **Live Data Collection**: Real-time updates every 2-5 seconds
- ✅ **REST API**: FastAPI with comprehensive endpoints
- ✅ **Mode Switching**: Seamless switching between modes
- ✅ **Verification Tools**: Automated mode detection and testing

**The module is production-ready and uses only real market data sources.**
