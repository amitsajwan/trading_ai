# External Dependencies

This document outlines all external dependencies required by the `market_data` module.

## Overview

The `market_data` module requires external services and Python packages for production use. **All dependencies are designed with graceful degradation** - the module can function in test mode without external services or credentials.

### ✅ Works Without Credentials

The system is designed to work seamlessly even when Zerodha credentials are missing:

- **In-Memory Storage**: Works without Redis
- **CSV Data Source**: Works without Zerodha API
- **Unit Testing**: Complete test suite works offline
- **API Service**: Gracefully handles missing data

### ⚠️ Requires Credentials

Only these features require Zerodha credentials:
- Zerodha historical data replay (`data_source="zerodha"`)
- Live market data collection
- Options chain data from Zerodha API

**The system will clearly indicate when credentials are required and will not fail silently.**

## System Services

### Redis (Required for Production)

**Purpose**: Market data storage (ticks, OHLC bars, prices, indicators)

**Configuration:**
```bash
REDIS_HOST="localhost"  # Default
REDIS_PORT="6379"        # Default
```

**Docker Setup:**
```bash
# Start Redis
docker-compose -f docker-compose.data.yml up -d redis

# Verify
redis-cli ping  # Should return PONG
```

**Data Stored:**
- Market ticks: `tick:{instrument}:{timestamp}`
- Latest prices: `price:{instrument}:latest`
- OHLC bars: `ohlc:{instrument}:{timeframe}:{timestamp}`
- Technical indicators: `indicators:{instrument}:{name}`

**Fallback**: Module uses `InMemoryMarketStore` when Redis is unavailable (testing mode)

### MongoDB (Optional)

**Purpose**: Optional storage for prompts, logs, and other application data

**Configuration:**
```bash
# Default connection (if needed)
MONGO_HOST="localhost"
MONGO_PORT="27017"
MONGO_USERNAME="admin"
MONGO_PASSWORD="admin"
```

**Docker Setup:**
```bash
# Start MongoDB
docker-compose -f docker-compose.data.yml up -d mongodb

# Verify
mongosh --eval "db.adminCommand('ping')"
```

**Note**: MongoDB is optional and only used if other modules require it.

## Python Packages

### Required Packages

```bash
pip install redis kiteconnect python-dotenv uvicorn fastapi
```

**Package Details:**

1. **redis** (>=4.0.0)
   - Redis client for Python
   - Used by: `RedisMarketStore`, `api_service.py`
   - Fallback: In-memory storage if unavailable

2. **kiteconnect** (>=4.0.0)
   - Zerodha Kite Connect API client
   - Used by: `HistoricalTickReplayer` (Zerodha data source), `ZerodhaProvider`
   - Required for: Real market data access
   - Installation: `pip install kiteconnect`

3. **python-dotenv** (>=0.19.0)
   - Environment variable management
   - Used by: All modules for configuration
   - Installation: `pip install python-dotenv`

4. **uvicorn** (>=0.20.0)
   - ASGI server for FastAPI
   - Used by: `api_service.py`
   - Installation: `pip install uvicorn`

5. **fastapi** (>=0.100.0)
   - Web framework for API service
   - Used by: `api_service.py`
   - Installation: `pip install fastapi`

### Optional Packages

```bash
pip install pandas numpy  # For technical indicators
```

1. **pandas** (>=1.5.0)
   - Data analysis library
   - Used by: `TechnicalIndicatorsService`
   - Fallback: Basic calculations if unavailable

2. **numpy** (>=1.20.0)
   - Numerical computing
   - Used by: `TechnicalIndicatorsService`
   - Fallback: Basic calculations if unavailable

## Zerodha Kite Connect

### API Credentials

**Required for real market data:**

1. **KITE_API_KEY**
   - Get from: https://kite.zerodha.com/apps/
   - Set in environment: `export KITE_API_KEY="your_key"`

2. **KITE_API_SECRET**
   - Get from: https://kite.zerodha.com/apps/
   - Set in environment: `export KITE_API_SECRET="your_secret"`

3. **KITE_ACCESS_TOKEN**
   - Generated via: `python -m market_data.tools.kite_auth`
   - Expires: Daily (24 hours)
   - Auto-refresh: Via `kite_auth.py` script

### Setup Instructions

1. **Create Zerodha App:**
   - Go to https://kite.zerodha.com/apps/
   - Create new app
   - Note API Key and Secret

2. **Configure Redirect URI:**
   - Add redirect URI: `http://127.0.0.1:<PORT>/login` (use `127.0.0.1` for local auth)
   - The auth helper will pick an available local port (starting at 5000) and print the exact redirect URI to use — **ensure the redirect URI configured in your Kite app matches the printed URI**.

3. **Generate Access Token (interactive):**
   ```bash
   # Runs the in-package CLI which opens a browser and captures the token
   python -m market_data.tools.kite_auth
   ```
   - Opens browser for login
   - Captures request token on the configured redirect URI
   - Exchanges request token for an access token and writes `credentials.json`

4. **Automatic token refresh (optional):**
   - The `market_data` package includes an auth service that can monitor tokens and trigger interactive re-login when needed.
   - Environment variables to control behavior:
     - `KITE_ALLOW_INTERACTIVE_LOGIN` (default `1`) — if set to `0`, the service will not launch a browser automatically.
     - `KITE_TOKEN_MAX_AGE_HOURS` (default `23`) — token age (in hours) after which the token is considered stale and will trigger a re-login attempt.

5. **Verify Credentials:**
   ```python
   from kiteconnect import KiteConnect
   kite = KiteConnect(api_key="...")
   kite.set_access_token("...")
   profile = kite.profile()  # Should return user profile
   ```

**Notes:**
- Prefer running the in-package CLI (`python -m market_data.tools.kite_auth`) instead of calling a top-level script. If you see references to older helper scripts (e.g., `auto_login.py`), prefer the in-package commands instead.

## Docker Compose Services

### docker-compose.data.yml

**Services:**

1. **redis**
   - Image: `redis:7-alpine`
   - Port: `6379`
   - Volume: `redis-data` (persistent storage)
   - Health check: `redis-cli ping`

2. **mongodb**
   - Image: `mongo:7`
   - Port: `27017`
   - Volume: `mongo-data` (persistent storage)
   - Credentials: `admin/admin` (change in production)
   - Health check: `mongosh --eval "db.adminCommand('ping')"`

**Usage:**
```bash
# Start all services
docker-compose -f docker-compose.data.yml up -d

# Start specific service
docker-compose -f docker-compose.data.yml up -d redis

# Stop services
docker-compose -f docker-compose.data.yml down

# View logs
docker-compose -f docker-compose.data.yml logs -f

# Remove volumes (clears data)
docker-compose -f docker-compose.data.yml down -v
```

## Environment Variables

### Required (Production)

```bash
# Zerodha API
KITE_API_KEY="your_api_key"
KITE_API_SECRET="your_api_secret"

# Redis (if using Redis storage)
REDIS_HOST="localhost"
REDIS_PORT="6379"
```

### Optional

```bash
# Zerodha Access Token (auto-generated if not set)
KITE_ACCESS_TOKEN="your_token"

# Instrument Configuration
INSTRUMENT_SYMBOL="BANKNIFTY"

# MongoDB (if needed)
MONGO_HOST="localhost"
MONGO_PORT="27017"
MONGO_USERNAME="admin"
MONGO_PASSWORD="admin"
```

## Testing Without External Dependencies

The module is designed to work without external dependencies for testing:

1. **In-Memory Storage:**
   ```python
   store = build_store()  # No redis_client = in-memory
   ```

2. **Mock Services:**
   - Use `InMemoryMarketStore` instead of `RedisMarketStore`
   - Use CSV data source instead of Zerodha API
   - Mock KiteConnect for unit tests

3. **Test Mode:**
   ```bash
   # Run tests without Docker
   pytest market_data/tests/ -m "not integration"
   ```

## Production Checklist

- [ ] Redis running and accessible
- [ ] Zerodha API credentials configured
- [ ] Access token generated and valid
- [ ] Environment variables set
- [ ] Docker services started (if using Docker)
- [ ] Health checks passing
- [ ] Data persistence configured (volumes)

## Troubleshooting

### Redis Connection Issues

```bash
# Check Redis is running
redis-cli ping

# Check connection from Python
python -c "import redis; r = redis.Redis(); r.ping()"
```

### Zerodha Authentication Issues

```bash
# Regenerate access token (interactive)
python -m market_data.tools.kite_auth

# Verify token
python -c "from kiteconnect import KiteConnect; kite = KiteConnect('key'); kite.set_access_token('token'); print(kite.profile())"
```

### Docker Issues

```bash
# Check service status
docker-compose -f docker-compose.data.yml ps

# View logs
docker-compose -f docker-compose.data.yml logs redis

# Restart services
docker-compose -f docker-compose.data.yml restart
```

