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

### Options Chain (Enhanced)

**GET** `/api/v1/options/chain/{instrument}`

Get enhanced options chain with IV, Greeks, validation, and normalization.

**Parameters:**
- `expiry` (query, optional): Expiry date (YYYY-MM-DD format)

**Example:** `GET /api/v1/options/chain/BANKNIFTY?expiry=2026-01-30`

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "expiry": "2026-01-30",
  "available": true,
  "strikes": [
    {
      "strike": 47500,
      "CE": {
        "tradingsymbol": "BANKNIFTY24JAN47500CE",
        "last_price": 150.5,
        "volume": 1000,
        "oi": 50000,
        "iv": 20.5,
        "delta": 0.55,
        "gamma": 0.001,
        "theta": -5.2,
        "vega": 12.3
      },
      "PE": {
        "tradingsymbol": "BANKNIFTY24JAN47500PE",
        "last_price": 100.5,
        "volume": 800,
        "oi": 45000,
        "iv": 18.5,
        "delta": -0.45,
        "gamma": 0.001,
        "theta": -4.8,
        "vega": 11.8
      },
      "ce_ltp": 150.5,
      "pe_ltp": 100.5,
      "ce_volume": 1000,
      "pe_volume": 800,
      "ce_oi": 50000,
      "pe_oi": 45000,
      "ce_iv": 20.5,
      "pe_iv": 18.5,
      "ce_delta": 0.55,
      "pe_delta": -0.45
    }
  ]
}
```

**Enhanced Features:**
- **Implied Volatility (IV)**: Available when calculated or provided by broker
- **Greeks**: Delta, Gamma, Theta, Vega, Rho calculated using Black-Scholes
- **Data Validation**: Invalid option data is filtered out
- **Data Normalization**: Standardized format across all providers

**Usage:**
```python
from market_data.providers.enhanced_options_chain import EnhancedOptionsChainAdapter

adapter = EnhancedOptionsChainAdapter(
    kite=kite_client,
    instrument_symbol="BANKNIFTY",
    enable_greeks=True  # Enable Greeks calculation
)

chain = await adapter.fetch_options_chain()
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

## 📈 Multi-Timeframe Data Access

The `MultiTimeframeReader` provides efficient access to OHLC data across multiple timeframes with intelligent caching.

### Features

- **Multiple Timeframes**: Fetch data for 5m, 15m, 1h, 4h, and daily timeframes
- **Intelligent Caching**: Automatic caching with configurable TTL to minimize Redis queries
- **Batch Fetching**: Fetch all timeframes at once for efficient multi-timeframe analysis
- **Cache Management**: Clear cache per instrument or globally

### Usage

```python
from market_data.ohlc import MultiTimeframeReader
from market_data.adapters.redis_store import RedisMarketStore
import redis

# Initialize Redis store
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=False)
market_store = RedisMarketStore(redis_client)

# Create multi-timeframe reader
reader = MultiTimeframeReader(market_store, cache_ttl_seconds=300)

# Fetch single timeframe
data_5m = reader.fetch_timeframe("BANKNIFTY", "5m", limit=100)

# Fetch multiple timeframes
data_all = reader.fetch_all_timeframes("BANKNIFTY", ["5m", "15m", "1h", "daily"])

# Access data
for timeframe, timeframe_data in data_all.items():
    print(f"{timeframe}: {timeframe_data.count} bars")
    latest_bar = timeframe_data.bars[-1] if timeframe_data.bars else None
    if latest_bar:
        print(f"  Latest close: {latest_bar.close}")

# Cache management
reader.clear_cache("BANKNIFTY")  # Clear for specific instrument
reader.clear_cache()  # Clear all cache

# Cache statistics
stats = reader.get_cache_stats()
print(f"Cached instruments: {stats['cached_instruments']}")
```

### Supported Timeframes

- `5m` - 5-minute candles
- `15m` - 15-minute candles
- `1h` - 1-hour candles
- `4h` - 4-hour candles
- `daily` - Daily candles

### Configuration

```python
reader = MultiTimeframeReader(
    market_store=market_store,
    cache_ttl_seconds=300,  # Cache TTL in seconds (default: 5 minutes)
    max_cache_size=1000     # Maximum cached entries (default: 1000)
)
```

### Performance

- **Cache Hit**: Returns cached data immediately (no Redis query)
- **Cache Miss**: Fetches from Redis and caches result
- **Batch Fetch**: Optimized to fetch multiple timeframes efficiently

---

## 📊 Greeks Calculator

The `GreeksCalculator` provides Black-Scholes Greeks calculations for options analysis.

**Usage:**
```python
from market_data.analytics.greeks_calculator import GreeksCalculator

calculator = GreeksCalculator()

# Calculate all Greeks
greeks = calculator.calculate_greeks(
    spot_price=47500.0,
    strike=47500.0,
    time_to_expiry=0.25,  # 3 months in years
    volatility=0.20,  # 20% as decimal
    risk_free_rate=0.07,  # 7% for India
    option_type='CE'  # or 'PE'
)

# Result:
# {
#   'delta': 0.55,      # Price sensitivity
#   'gamma': 0.001,     # Delta sensitivity
#   'theta': -5.2,      # Time decay per day
#   'vega': 12.3,       # Volatility sensitivity (per 1%)
#   'rho': 8.5          # Interest rate sensitivity (per 1%)
# }
```

**Greeks Explained:**
- **Delta**: Change in option price for ₹1 change in underlying (0 to 1 for calls, -1 to 0 for puts)
- **Gamma**: Rate of change of delta (always positive, highest at ATM)
- **Theta**: Time decay (always negative, option loses value over time)
- **Vega**: Sensitivity to volatility changes (always positive, same for calls/puts)
- **Rho**: Interest rate sensitivity (positive for calls, negative for puts)

---

## 📈 Implied Volatility (IV) Calculator

The `GreeksCalculator` also provides **Implied Volatility (IV)** calculation by inverting the Black-Scholes formula. This finds the volatility that matches the market price of an option.

**Usage:**
```python
from market_data.analytics.greeks_calculator import GreeksCalculator

calculator = GreeksCalculator()

# Calculate IV from market price
iv = calculator.calculate_implied_volatility(
    market_price=925.80,  # Current market price of option
    spot_price=47500.0,   # Current underlying price
    strike=47500.0,       # Option strike price
    time_to_expiry=0.25,  # 3 months in years
    risk_free_rate=0.07,  # 7% for India
    option_type='CE',     # or 'PE'
    initial_guess=0.20    # 20% initial guess (optional)
)

# Result: 0.20 (20% as decimal)
# Convert to percentage: iv * 100 = 20.0%
```

**How It Works:**
1. Uses **Newton-Raphson method** for fast convergence (uses vega as derivative)
2. Falls back to **bisection method** if Newton-Raphson fails (more stable)
3. Validates inputs (market price must be >= intrinsic value)
4. Returns `None` if calculation fails (e.g., invalid inputs, no convergence)

**Features:**
- ✅ Fast convergence (typically < 10 iterations)
- ✅ Robust fallback (bisection method for difficult cases)
- ✅ Input validation (handles edge cases gracefully)
- ✅ Accurate results (within 0.0001% tolerance)

**Example:**
```python
# Calculate option price first (to get market price)
market_price = GreeksCalculator.calculate_option_price(
    spot_price=100.0,
    strike=100.0,
    time_to_expiry=0.25,
    volatility=0.20,  # 20% IV
    option_type='CE'
)

# Now invert to recover IV (should get ~20%)
iv_recovered = GreeksCalculator.calculate_implied_volatility(
    market_price=market_price,
    spot_price=100.0,
    strike=100.0,
    time_to_expiry=0.25,
    option_type='CE'
)

# iv_recovered ≈ 0.20 (within 1% accuracy)
```

**Integration with Enhanced Options Chain:**
The `EnhancedOptionsChainAdapter` automatically calculates IV for all options in the chain:
```python
from market_data.providers.enhanced_options_chain import EnhancedOptionsChainAdapter

adapter = EnhancedOptionsChainAdapter(kite, "BANKNIFTY")
chain = adapter.get_options_chain(expiry="2026-01-27")

# Each strike will have ce_iv and pe_iv populated
for strike_data in chain['strikes']:
    ce_iv = strike_data.get('ce_iv')  # IV as percentage (e.g., 20.5 for 20.5%)
    pe_iv = strike_data.get('pe_iv')  # IV as percentage (e.g., 18.5 for 18.5%)
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

## ✅ Verification with Real Data

### Running Verification with Real Zerodha Historical Data

When the market is closed, you can verify all implementations work correctly with real historical data from Zerodha.

**Prerequisites:**
- Redis running (`localhost:6379`)
- Zerodha credentials set (`KITE_API_KEY`, `KITE_ACCESS_TOKEN`)
- Market closed (uses historical data)

**Run Verification:**
```bash
# From project root
python market_data/verify_with_real_data.py
```

**Or directly:**
```bash
cd market_data
python -m pytest tests/integration/verify_real_data.py -v -s
```

**What it Tests:**
1. ✅ **Multi-Timeframe Reader** - Fetches real OHLC data for 5m, 15m, 1h, daily timeframes
2. ✅ **Technical Indicators** - Calculates indicators on real historical minute data
3. ✅ **Greeks Calculator** - Validates Greeks calculations with realistic option parameters
4. ✅ **Enhanced Options Chain** - Fetches real options chain data from Zerodha
5. ✅ **Multi-Timeframe Indicators** - Calculates indicators across multiple timeframes

**Example Output:**
```
====================================================================
VERIFICATION WITH REAL ZERODHA HISTORICAL DATA
====================================================================

✅ Connected to Zerodha as: UserName
✅ Connected to Redis at localhost:6379

TEST 1: Multi-Timeframe Reader with Real Data
====================================================================
📊 Using instrument: BANKNIFTY (token: 26009)
📥 Fetching 5m data...
✅ Fetched 1200 candles
✅ Converted 1200 bars for 5m
✅ Stored 1200 5m bars in Redis
...

✅ 5m: 1200 bars, latest: 47500.00
✅ 15m: 400 bars, latest: 47505.00
✅ 1h: 80 bars, latest: 47510.00
✅ daily: 7 bars, latest: 47520.00

TEST 2: Technical Indicators with Real Data
====================================================================
📊 Calculating technical indicators...
✅ Technical Indicators Calculated:
  RSI(14): 58.32
  MACD: 12.45
  SMA(20): 47450.00
  EMA(50): 47380.00
  ADX(14): 28.50
  ATR(14): 185.25
  Volume Ratio: 1.25

TEST 3: Greeks Calculator with Real Option Parameters
====================================================================
✅ Call Option Greeks:
  Delta: 0.5432
  Gamma: 0.000145
  Theta: -5.23 (per day)
  Vega: 12.34 (per 1% vol change)
  Rho: 8.56 (per 1% rate change)
✅ Call-Put Delta Parity: 1.0000 (should be ~1.0)
  ✅ Delta parity verified!

VERIFICATION SUMMARY
====================================================================
✅ PASS: multi_timeframe
✅ PASS: technical_indicators
✅ PASS: greeks
✅ PASS: options_chain
✅ PASS: mtf_indicators

Total: 5/5 tests passed
🎉 All tests passed! Implementations work with real data.
```

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
