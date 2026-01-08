# market_data - Market Data Module

**Status: ✅ Production Ready - Real Data Sources Only**

A production-ready market data module for trading systems. Supports real-time and historical data from Zerodha API, with Redis-backed persistence and complete offline testing capabilities.

## 🎯 Key Features

- **Real Data Sources**: Zerodha API for live and historical data (no synthetic data)
- **Market Data Storage**: Redis-backed persistence + in-memory for testing
- **Real-time Ingestion**: WebSocket streaming + REST API fallbacks
- **Historical Replay**: Real Zerodha historical data with configurable replay speed
- **Options Data**: Live options chains via Zerodha
- **Technical Indicators**: Real-time calculation and caching
- **100% Testable**: Complete functionality with in-memory storage for testing

## 📦 Architecture

```
market_data/
├── contracts/          # Protocol definitions (MarketStore, MarketIngestion, etc.)
├── store/              # Market data storage (Redis + In-Memory)
├── adapters/           # External service adapters (Redis, Zerodha)
├── collectors/         # LTP, depth, options collectors
├── tools/              # Utilities (auth, demo data)
└── tests/              # Comprehensive test suite
```

## 🚀 Quick Start

### Prerequisites

1. **Docker & Docker Compose** (for Redis and MongoDB)
2. **Python 3.8+**
3. **Zerodha Kite Connect API credentials** (for real data)

### Step 1: Start Data Services (Docker)

```bash
# Start Redis and MongoDB
docker-compose -f docker-compose.data.yml up -d

# Verify services are running
docker-compose -f docker-compose.data.yml ps
```

**Services:**
- **Redis** (port 6379): Market data storage (ticks, OHLC, prices)
- **MongoDB** (port 27017): Optional - for prompt storage

### Step 2: Configure Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required for Zerodha data
KITE_API_KEY="your_api_key"
KITE_API_SECRET="your_api_secret"
KITE_ACCESS_TOKEN="your_access_token"  # Optional - can be generated via kite_auth.py

# Redis configuration (defaults shown)
REDIS_HOST="localhost"
REDIS_PORT="6379"

# Instrument configuration
INSTRUMENT_SYMBOL="BANKNIFTY"  # or "NIFTY BANK", "NIFTY", etc.
```

### Step 3: Authenticate with Zerodha (First Time)

```bash
# Generate access token
python market_data/src/market_data/tools/kite_auth.py

# This will:
# 1. Open browser for Zerodha login
# 2. Capture request_token from redirect
# 3. Generate access_token
# 4. Save to credentials.json
```

### Step 4: Use the Module

```python
from market_data.api import build_store, build_historical_replay
import redis
from datetime import datetime, date

# Build Redis-backed store
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
store = build_store(redis_client=redis_client)

# Start historical replay with Zerodha data
from kiteconnect import KiteConnect
kite = KiteConnect(api_key="...")
kite.set_access_token("...")

replay = build_historical_replay(
    store=store,
    data_source="zerodha",  # Real Zerodha data
    start_date=datetime(2026, 1, 7),
    kite=kite
)
replay.start()

# Access data
tick = store.get_latest_tick("BANKNIFTY")
bars = list(store.get_ohlc("BANKNIFTY", "1min", limit=100))

replay.stop()
```

## 📊 Data Sources

### Zerodha API (Recommended)

**Real historical and live market data from Zerodha:**

```python
replay = build_historical_replay(
    store=store,
    data_source="zerodha",
    kite=kite,
    start_date=datetime(2026, 1, 7)
)
```

**Requirements:**
- Valid Zerodha Kite Connect credentials
- `KITE_API_KEY` and `KITE_ACCESS_TOKEN` in environment or `credentials.json`
- Market data available for the requested date

**Features:**
- Real market data (no synthetic/dummy data)
- Multiple intervals (minute, 5minute, day, etc.)
- Automatic OHLC to tick conversion
- Configurable replay speed (0.0 = instant, 1.0 = real-time)

**Note:** If credentials are missing, use CSV files (see below) as an alternative. The system will clearly indicate when credentials are required.

### CSV File (Works Without Credentials)

**Historical data from CSV file - No Zerodha credentials required:**

```python
replay = build_historical_replay(
    store=store,
    data_source="path/to/data.csv"  # CSV file path
)
```

**CSV Format:**
```csv
Date,Time,Open,High,Low,Close,Volume
2024-01-15,09:15,45000,45100,44950,45050,1500000
2024-01-15,09:16,45050,45150,45000,45100,1600000
```

**Benefits:**
- ✅ Works without Zerodha credentials
- ✅ No API rate limits
- ✅ Offline testing capability
- ✅ Use your own historical data files

## 🔄 Graceful Degradation (Missing Credentials)

**✅ The system works seamlessly even without Zerodha credentials!**

### What Works Without Credentials

1. **In-Memory Storage (No Redis, No Credentials):**
   ```python
   # Works completely offline
   store = build_store()  # In-memory store
   tick = store.get_latest_tick("BANKNIFTY")
   bars = list(store.get_ohlc("BANKNIFTY", "1min", limit=100))
   ```

2. **CSV Data Source (No Credentials Required):**
   ```python
   # Works without Zerodha credentials
   replay = build_historical_replay(
       store=store,
       data_source="path/to/data.csv"  # CSV file path
   )
   replay.start()
   ```

3. **Unit Testing (100% Offline):**
   ```bash
   # All unit tests work without credentials or Redis
   pytest market_data/tests/ -m "not integration"
   ```

4. **API Service (Graceful Error Handling):**
   - Health endpoint always works
   - Data endpoints return clear errors if data unavailable
   - No crashes or silent failures

### What Requires Credentials

Only these specific features require Zerodha credentials:

1. **Zerodha Historical Data:**
   ```python
   # Requires KITE_API_KEY and KITE_ACCESS_TOKEN
   replay = build_historical_replay(
       store=store,
       data_source="zerodha",  # ← Requires credentials
       kite=kite
   )
   ```
   - **Alternative**: Use CSV files (no credentials needed)

2. **Live Data Collection:**
   - Requires valid Zerodha credentials
   - **Alternative**: Use historical replay with CSV

3. **Options Chain from Zerodha:**
   - Requires API access
   - **Alternative**: Mock options chain for testing

### Error Handling

**The system will clearly indicate when credentials are required:**

```python
# If credentials missing, you'll see:
# ❌ Zerodha data source requires valid credentials!
# 💡 Please configure Zerodha credentials in Step 0
# 💡 Or use CSV file: --historical-source path/to/data.csv
```

**The system will NOT:**
- ❌ Fail silently
- ❌ Crash unexpectedly
- ❌ Use dummy/synthetic data
- ❌ Hide credential requirements

### Best Practices

**For Development/Testing (No Credentials):**
```python
# Use CSV files
store = build_store()  # In-memory
replay = build_historical_replay(store, data_source="data.csv")
```

**For Production (With Credentials):**
```python
# Use Zerodha API
redis_client = redis.Redis(...)
store = build_store(redis_client=redis_client)
replay = build_historical_replay(store, data_source="zerodha", kite=kite)
```

## 🔧 External Dependencies

### Required Dependencies

**Python Packages:**
```bash
pip install redis kiteconnect python-dotenv uvicorn fastapi
```

**System Services:**
- **Redis**: Required for production data storage
  - Default: `localhost:6379`
  - Can be started via `docker-compose -f docker-compose.data.yml up -d redis`
- **MongoDB**: Optional (for prompt storage)
  - Default: `localhost:27017`

### Zerodha Kite Connect

**Required for real data:**
- `KITE_API_KEY`: From Zerodha app settings
- `KITE_API_SECRET`: From Zerodha app settings
- `KITE_ACCESS_TOKEN`: Generated via `kite_auth.py` (expires daily)

**Setup:**
1. Create app at https://kite.zerodha.com/apps/
2. Get API Key and Secret
3. Set redirect URI: `http://127.0.0.1:5000/login` (or available port)
4. Run `python market_data/src/market_data/tools/kite_auth.py`

## 🐳 Docker Compose Setup

### Start Data Services

```bash
# Start Redis and MongoDB
docker-compose -f docker-compose.data.yml up -d

# Check status
docker-compose -f docker-compose.data.yml ps

# View logs
docker-compose -f docker-compose.data.yml logs -f redis
docker-compose -f docker-compose.data.yml logs -f mongodb
```

### Stop Services

```bash
# Stop services
docker-compose -f docker-compose.data.yml down

# Stop and remove volumes (clears all data)
docker-compose -f docker-compose.data.yml down -v
```

### Service Details

**Redis (Port 6379):**
- Stores market ticks, OHLC bars, prices
- Data persists in `redis-data` volume
- Health check: `redis-cli ping`

**MongoDB (Port 27017):**
- Optional storage for prompts/logs
- Credentials: `admin/admin` (change in production)
- Data persists in `mongo-data` volume

## 📊 Data Storage Format

### Redis Keys

**Tick Data:**
```
tick:{instrument}:latest              → Latest tick JSON
tick:{instrument}:{timestamp}         → Historical tick JSON
price:{instrument}:latest              → Latest price (float)
price:{instrument}:latest_ts          → Latest timestamp
volume:{instrument}:latest             → Latest volume
```

**OHLC Data:**
```
ohlc:{instrument}:{timeframe}:{timestamp}  → OHLC bar JSON
ohlc_sorted:{instrument}:{timeframe}       → Sorted set of bars
```

**Technical Indicators:**
```
indicators:{instrument}:{indicator_name}   → Cached indicator value
```

## 🔄 Graceful Degradation (Missing Credentials)

**The system works seamlessly even without Zerodha credentials:**

### ✅ What Works Without Credentials

1. **In-Memory Storage:**
   ```python
   # Works without Redis or Zerodha
   store = build_store()  # In-memory store
   tick = store.get_latest_tick("BANKNIFTY")
   ```

2. **CSV Data Source:**
   ```python
   # Works without Zerodha credentials
   replay = build_historical_replay(
       store=store,
       data_source="path/to/data.csv"  # CSV file
   )
   ```

3. **Unit Testing:**
   ```bash
   # All unit tests work without credentials
   pytest market_data/tests/ -m "not integration"
   ```

4. **API Service (Limited):**
   - Health endpoint works
   - Endpoints return appropriate errors if data unavailable
   - No crashes or silent failures

### ❌ What Requires Credentials

1. **Zerodha Historical Data:**
   - Requires `KITE_API_KEY` and `KITE_ACCESS_TOKEN`
   - System will clearly indicate if credentials are missing
   - Use CSV files as alternative

2. **Live Data Collection:**
   - Requires valid Zerodha credentials
   - Options chain data requires API access

### 🎯 Best Practice

**For Development/Testing:**
- Use CSV files for historical data
- Use in-memory storage for testing
- No credentials needed

**For Production:**
- Configure Zerodha credentials
- Use Redis for persistence
- Enable live data collection

## 🧪 Testing

### Unit Tests (No External Dependencies)

```bash
# Run all unit tests (works without credentials or Redis)
pytest market_data/tests/ -m "not integration"

# Test specific components
pytest market_data/tests/test_store.py
pytest market_data/tests/test_redis_store.py
```

### Integration Tests (Requires Docker)

```bash
# Start services
docker-compose -f docker-compose.data.yml up -d

# Run integration tests
pytest market_data/tests/ -m integration

# Stop services
docker-compose -f docker-compose.data.yml down
```

### Offline Testing

The module supports 100% offline testing using in-memory storage:

```python
# In-memory store (no Redis needed)
store = build_store()  # No redis_client = in-memory

# Test with in-memory store
tick = store.get_latest_tick("BANKNIFTY")
```

## 🔌 API Reference

### Factory Functions

```python
from market_data.api import (
    build_store,           # Market data storage
    build_historical_replay,  # Historical data replay
    build_options_client   # Options chain data
)
```

### MarketStore Protocol

```python
class MarketStore(Protocol):
    def store_tick(self, tick: MarketTick) -> None: ...
    def get_latest_tick(self, instrument: str) -> Optional[MarketTick]: ...
    def store_ohlc(self, bar: OHLCBar) -> None: ...
    def get_ohlc(self, instrument: str, timeframe: str, limit: int = 100) -> Iterable[OHLCBar]: ...
```

### MarketIngestion Protocol

```python
class MarketIngestion(Protocol):
    def bind_store(self, store: MarketStore) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

## 📡 Market Data API Service

The module includes a FastAPI service for REST access:

```bash
# Start API service
python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
```

**Endpoints:**
- `GET /health` - Service health check
- `GET /api/v1/market/tick/{instrument}` - Latest tick data
- `GET /api/v1/market/ohlc/{instrument}` - OHLC bars
- `GET /api/v1/market/price/{instrument}` - Latest price
- `GET /api/v1/options/chain/{instrument}` - Options chain
- `GET /api/v1/technical/indicators/{instrument}` - Technical indicators

See `API_CONTRACT.md` for detailed API documentation.

## 🎯 Key Design Principles

1. **Real Data Only**: No synthetic/dummy data generation
2. **Protocol-Based**: Clean interfaces, easy to extend
3. **Production Ready**: Redis persistence, error handling, logging
4. **Testable**: In-memory storage for offline testing
5. **Docker Ready**: Standard docker-compose setup

## 📚 Documentation

- **API_CONTRACT.md**: Complete REST API documentation
- **HISTORICAL_SIMULATION_README.md**: Historical replay guide
- **EXTERNAL_DEPENDENCIES.md**: External dependencies details
- **src/market_data/README.md**: Internal module documentation

## 🚀 Production Deployment

### Environment Variables

```bash
# Required
KITE_API_KEY="your_api_key"
KITE_API_SECRET="your_api_secret"
REDIS_HOST="redis-host"
REDIS_PORT="6379"

# Optional
KITE_ACCESS_TOKEN="your_token"  # Auto-generated if not provided
INSTRUMENT_SYMBOL="BANKNIFTY"
```

### Docker Compose for Production

```yaml
# Use docker-compose.data.yml as base
# Add environment variables
# Configure volumes for data persistence
# Set up health checks
```

## ✅ Status

- ✅ **Real Data Sources**: Zerodha API and CSV only
- ✅ **Redis Storage**: Production-ready persistence
- ✅ **Historical Replay**: Real data with configurable speed
- ✅ **API Service**: FastAPI REST endpoints
- ✅ **Testing**: Complete test coverage
- ✅ **Documentation**: Comprehensive guides

**The module is production-ready and uses only real market data sources.**
