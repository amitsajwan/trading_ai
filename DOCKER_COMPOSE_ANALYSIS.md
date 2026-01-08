# Docker Compose Architecture Analysis

## Overview

This project uses **Docker Compose** to orchestrate a multi-service trading system with 2 main compose files:
- `docker-compose.yml` - Main production orchestration (425 lines)
- `docker-compose.data.yml` - Minimal data services setup (42 lines)

## Architecture Summary

### Network Topology
All services run on a **bridge network** called `trading-network`, enabling service-to-service communication using container names as hostnames.

### Infrastructure Services (Base Layer)

#### 1. **MongoDB** (`zerodha-mongodb`)
- **Image**: `mongo:7`
- **Port**: `27018:27017` (host:container)
- **Volume**: `mongo_data:/data/db` (persistent storage)
- **Database**: `zerodha_trading` (initialized)
- **Health Check**: MongoDB ping every 10s
- **Purpose**: Primary database for trading decisions, agent discussions, signals, and news storage

#### 2. **Redis** (`zerodha-redis`)
- **Image**: `redis:7-alpine`
- **Port**: `6380:6379` (host:container)
- **Volume**: `redis_data:/data` (persistent storage)
- **Health Check**: Redis CLI ping every 10s
- **Purpose**: 
  - Market data caching (ticks, OHLC)
  - Virtual time synchronization for historical replay
  - Real-time price distribution
  - Queue management

**Dependency Flow**: All application services depend on these infrastructure services with `condition: service_healthy` to ensure proper startup order.

---

## Application Services

### Trading Bot Services (Instrument-Specific)

Three trading bot instances for different instruments:

#### **1. Trading Bot - BTC** (`trading-bot-btc`)
- **Container**: `zerodha-trading-bot-btc`
- **Env File**: `.env.btc`
- **Dependencies**: MongoDB + Redis (healthy)
- **Command**: Default (from Dockerfile)
- **Purpose**: Bitcoin/Crypto trading automation

#### **2. Trading Bot - BankNifty** (`trading-bot-banknifty`)
- **Container**: `zerodha-trading-bot-banknifty`
- **Env File**: `.env.banknifty`
- **Dependencies**: MongoDB + Redis (healthy)
- **Volumes**: Includes `credentials.json` (read-only)
- **Purpose**: BankNifty options/futures trading

#### **3. Trading Bot - Nifty** (`trading-bot-nifty`)
- **Container**: `zerodha-trading-bot-nifty`
- **Env File**: `.env.nifty`
- **Dependencies**: MongoDB + Redis (healthy)
- **Volumes**: Includes `credentials.json` (read-only)
- **Purpose**: Nifty 50 index trading

**Common Configuration**:
- `MONGODB_URI=mongodb://mongodb:27017/zerodha_trading`
- `REDIS_HOST=redis`
- `REDIS_PORT=6379`
- `DEBUG_AGENT_OUTPUT=true`
- `LLM_SELECTION_STRATEGY=weighted`
- `LLM_SOFT_THROTTLE_FACTOR=0.8`

---

### Backend API Services (FastAPI)

Three backend instances for different instruments:

#### **1. Backend - BTC** (`backend-btc`)
- **Container**: `zerodha-backend-btc`
- **Port**: `8001:8000`
- **Command**: `python -m uvicorn dashboard_pro:app --host 0.0.0.0 --port 8000`
- **Env File**: `.env.btc`
- **Purpose**: BTC trading API and dashboard

#### **2. Backend - BankNifty** (`backend-banknifty`)
- **Container**: `zerodha-backend-banknifty`
- **Port**: `8002:8000`
- **Command**: `python -m uvicorn dashboard_pro:app --host 0.0.0.0 --port 8000`
- **Env File**: `.env.banknifty`
- **Dependencies**: 
  - MongoDB + Redis (healthy)
  - LTP + Depth collectors (started)
- **Purpose**: BankNifty trading API with real-time data collectors

#### **3. Backend - Nifty** (`backend-nifty`)
- **Container**: `zerodha-backend-nifty`
- **Port**: `8003:8000`
- **Command**: `python -m uvicorn dashboard_pro:app --host 0.0.0.0 --port 8000`
- **Env File**: `.env.nifty`
- **Dependencies**: 
  - MongoDB + Redis (healthy)
  - LTP + Depth collectors (started)
- **Purpose**: Nifty trading API with real-time data collectors

---

### Market Data Collectors

Real-time market data collection services:

#### **1. LTP Collector - BankNifty** (`ltp-collector-banknifty`)
- **Container**: `zerodha-ltp-collector-banknifty`
- **Command**: `python -m market_data.collectors.ltp_collector`
- **Dependencies**: MongoDB + Redis (healthy)
- **Health Check**: Validates Redis has recent price data (within 120 seconds)
- **Purpose**: Collects Last Traded Price (LTP) for BankNifty

#### **2. Depth Collector - BankNifty** (`depth-collector-banknifty`)
- **Container**: `zerodha-depth-collector-banknifty`
- **Command**: `python scripts/market_data.collectors.depth_collector.py`
- **Dependencies**: Redis (healthy) only
- **Health Check**: Same as LTP collector
- **Purpose**: Collects order book depth data for BankNifty

#### **3. LTP Collector - Nifty** (`ltp-collector-nifty`)
- **Container**: `zerodha-ltp-collector-nifty`
- **Command**: `python -m market_data.collectors.ltp_collector`
- **Dependencies**: MongoDB + Redis (healthy)
- **Health Check**: Validates Redis has recent price data (within 120 seconds)
- **Purpose**: Collects Last Traded Price (LTP) for Nifty 50

#### **4. Depth Collector - Nifty** (`depth-collector-nifty`)
- **Container**: `zerodha-depth-collector-nifty`
- **Command**: `python scripts/market_data.collectors.depth_collector.py`
- **Dependencies**: Redis (healthy) only
- **Health Check**: Same as LTP collector
- **Purpose**: Collects order book depth data for Nifty 50

**Health Check Logic**: 
- Checks Redis for recent price timestamps
- Validates data freshness (within 120 seconds)
- Key format: `price:{BANKNIFTY|NIFTY}:latest_ts`

---

### Core Orchestration Services

#### **1. Dashboard Service** (`dashboard-service`)
- **Container**: `zerodha-dashboard-service`
- **Port**: `8888:8888`
- **Command**: `python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8888`
- **Dependencies**: 
  - MongoDB + Redis (healthy)
  - LTP + Depth collectors (started)
- **Env**: BankNifty configuration
- **PYTHONPATH**: `/app:/app/market_data/src`
- **Purpose**: Main FastAPI trading cockpit dashboard

#### **2. Orchestrator Service** (`orchestrator-service`)
- **Container**: `zerodha-orchestrator-service`
- **Command**: `python run_orchestrator.py`
- **Dependencies**: MongoDB + Redis (healthy)
- **Env**: BankNifty configuration
- **Purpose**: 
  - Continuous multi-agent analysis cycles
  - Runs every 15 minutes (or 2 minutes in demo mode)
  - Generates trading signals from 4 specialized agents
  - Writes decisions to MongoDB (`agent_decisions`, `agent_discussions`)

**Orchestrator Features**:
- Market hours aware (skips when market closed)
- Virtual time support for historical replay
- Mode-aware database selection
- Continuous cycle execution with error handling

#### **3. Automatic Trading Service** (`automatic-trading-service`)
- **Container**: `zerodha-automatic-trading-service`
- **Command**: `python -m services.automatic_trading_runner`
- **Dependencies**: MongoDB + Redis (healthy)
- **Env**: 
  - `AUTOTRADE_USER_ID=paper_trader_user_id`
  - `AUTOTRADE_INSTRUMENT=BANKNIFTY`
- **Purpose**: Executes trades from orchestrator signals automatically

#### **4. Historical Replay Service** (`historical-replay-service`)
- **Container**: `zerodha-historical-replay-service`
- **Command**: `python -m services.historical_data_replay_service`
- **Dependencies**: Redis (healthy) only
- **Env**: 
  - `HISTORICAL_START_DATE=2024-01-01` (default)
  - `HISTORICAL_END_DATE=2024-01-31` (default)
  - `HISTORICAL_INTERVAL=minute` (default)
- **PYTHONPATH**: `/app:/app/market_data/src`
- **Purpose**: Replays historical market data for paper trading simulation

---

## Service Dependencies Graph

```
Infrastructure Layer:
┌──────────┐    ┌──────────┐
│ MongoDB  │    │  Redis   │
│  :27017  │    │  :6379   │
└────┬─────┘    └────┬─────┘
     │               │
     └───────┬───────┘
             │
             ▼
     [All services depend on these]

Application Layer:
┌─────────────────────────────────────────────────────────┐
│                   Trading Network                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Trading Bots:          Backends:                       │
│  ├─ BTC Bot             ├─ BTC (8001)                  │
│  ├─ BankNifty Bot       ├─ BankNifty (8002)            │
│  └─ Nifty Bot           └─ Nifty (8003)                │
│                                                          │
│  Data Collectors:       Core Services:                  │
│  ├─ LTP (BN)            ├─ Dashboard (8888)            │
│  ├─ Depth (BN)          ├─ Orchestrator                │
│  ├─ LTP (Nifty)         ├─ Auto Trading                │
│  └─ Depth (Nifty)       └─ Historical Replay           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Dependency Chain**:
1. **Infrastructure** (MongoDB, Redis) start first with health checks
2. **Data Collectors** start after infrastructure is healthy
3. **Backends** (BankNifty/Nifty) wait for collectors to start
4. **Dashboard** waits for collectors to start
5. **Trading Bots** and **Orchestrator** only need infrastructure
6. **Auto Trading** and **Historical Replay** depend on infrastructure

---

## Dockerfile Analysis

### Base Image
- **Image**: `python:3.12-slim`
- **Work Directory**: `/app`

### Build Process
1. **System Dependencies**: Installs `gcc` (needed for Python packages)
2. **Python Dependencies**: Installs from `requirements.txt`
3. **Code Copy**: Copies entire application (`.`)
4. **Logs Directory**: Creates `/app/logs`
5. **Environment**: 
   - `PYTHONUNBUFFERED=1` (real-time logs)
   - `PYTHONPATH=/app`

### Default Command
```bash
python -m services.trading_service
```

**Note**: Most services override this command in `docker-compose.yml`

---

## Environment Variables

### Common Environment Variables (All Services)

| Variable | Purpose | Example |
|----------|---------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://mongodb:27017/zerodha_trading` |
| `REDIS_HOST` | Redis hostname | `redis` (container name) |
| `REDIS_PORT` | Redis port | `6379` |
| `DEBUG_AGENT_OUTPUT` | Enable debug logging | `true` |
| `LLM_SELECTION_STRATEGY` | LLM provider selection | `weighted` |
| `LLM_SOFT_THROTTLE_FACTOR` | Throttle factor for LLM calls | `0.8` |

### Service-Specific Environment Variables

#### Orchestrator Service
- `DEMO_MODE`: Faster cycles (2 min vs 15 min)
- `FORCE_MARKET_OPEN`: Override market hours check
- `SIMULATION_MODE`: Enable simulation mode

#### Automatic Trading Service
- `AUTOTRADE_USER_ID`: User ID for paper trading
- `AUTOTRADE_INSTRUMENT`: Instrument symbol (BANKNIFTY)

#### Historical Replay Service
- `HISTORICAL_START_DATE`: Start date for replay
- `HISTORICAL_END_DATE`: End date for replay
- `HISTORICAL_INTERVAL`: Data interval (minute, hour, day)

#### Instrument-Specific Services
Each service uses an `.env` file:
- `.env.btc` - Bitcoin configuration
- `.env.banknifty` - BankNifty configuration
- `.env.nifty` - Nifty 50 configuration

**Note**: These files are not in the repository (should be in `.gitignore`)

---

## Volume Mounts

### Persistent Volumes
1. **`mongo_data`**: MongoDB database storage (`/data/db`)
2. **`redis_data`**: Redis data persistence (`/data`)

### Host-Container Volume Mounts

| Service | Host Path | Container Path | Purpose |
|---------|-----------|----------------|---------|
| All services | `./logs` | `/app/logs` | Log files |
| Trading Bots (BN/Nifty) | `./credentials.json` | `/app/credentials.json:ro` | Zerodha API credentials |
| Backends (BN/Nifty) | `./credentials.json` | `/app/credentials.json:ro` | Zerodha API credentials |
| Collectors | `./credentials.json` | `/app/credentials.json:ro` | Zerodha API credentials |
| Dashboard | `./credentials.json` | `/app/credentials.json:ro` | Zerodha API credentials |
| Orchestrator | `./credentials.json` | `/app/credentials.json:ro` | Zerodha API credentials |
| Auto Trading | `./credentials.json` | `/app/credentials.json:ro` | Zerodha API credentials |

**Note**: BTC services have credentials mount commented out (may use different auth)

---

## Health Checks

### Infrastructure Health Checks

#### MongoDB
```bash
mongosh --eval "db.adminCommand('ping')"
```
- **Interval**: 10s
- **Timeout**: 5s
- **Retries**: 5

#### Redis
```bash
redis-cli ping
```
- **Interval**: 10s
- **Timeout**: 5s
- **Retries**: 5

### Application Health Checks

#### LTP/Depth Collectors
Python script checks Redis for recent price data:
```python
# Checks if price:{BANKNIFTY|NIFTY}:latest_ts exists 
# and is within 120 seconds of current time
```
- **Interval**: 30s
- **Timeout**: 5s
- **Retries**: 5
- **Start Period**: 20s (grace period)

---

## Port Mapping

| Service | Host Port | Container Port | Purpose |
|---------|-----------|----------------|---------|
| MongoDB | 27018 | 27017 | Database access |
| Redis | 6380 | 6379 | Cache/queue access |
| Backend BTC | 8001 | 8000 | API access |
| Backend BankNifty | 8002 | 8000 | API access |
| Backend Nifty | 8003 | 8000 | API access |
| Dashboard | 8888 | 8888 | Main dashboard UI |

**Note**: Internal services communicate via container names (not ports)

---

## docker-compose.data.yml (Alternative Setup)

Minimal compose file for data services only:

### Services
1. **Redis**: Standard port `6379:6379` with AOF persistence
2. **MongoDB**: Standard port `27017:27017` with authentication
   - Username: `admin`
   - Password: `admin`

### Use Case
- Development/testing with separate data services
- Can run alongside main compose file (different ports)

---

## Module Dependencies

### Core Dependencies (from requirements.txt)

#### LLM & AI
- `langgraph>=0.2.0` - Multi-agent orchestration
- `langchain>=0.3.0` - LLM framework
- `openai>=1.0.0` - OpenAI API
- `groq>=0.4.0` - Groq API
- `google-genai>=0.8.0` - Google Gemini
- `cohere>=5.0.0` - Cohere API
- `ai21>=4.3.0` - AI21 Labs

#### Data & API
- `fastapi>=0.104.0` - API framework
- `uvicorn>=0.24.0` - ASGI server
- `kiteconnect>=4.0.0` - Zerodha API client
- `websocket-client>=1.6.0` - WebSocket support

#### Storage
- `redis>=5.0.0` - Redis client (async support)
- `pymongo>=4.6.0` - MongoDB client

#### Data Processing
- `pandas>=2.0.0` - Data manipulation
- `numpy>=1.24.0` - Numerical computing
- `pandas-ta>=0.3.14b0` - Technical indicators

---

## Service Communication Patterns

### 1. Database Access
- **MongoDB**: All services connect via `mongodb://mongodb:27017/zerodha_trading`
- **Redis**: All services connect via hostname `redis` and port `6379`

### 2. Inter-Service Communication
- Services communicate via FastAPI HTTP endpoints
- Dashboard → Backends: Direct HTTP calls
- Collectors → Redis: Direct writes
- Orchestrator → MongoDB: Direct writes

### 3. Data Flow

```
Zerodha API
    │
    ▼
[LTP/Depth Collectors] → Redis (Market Data Cache)
    │                        │
    │                        ▼
    │                  [All Services]
    │                        │
    └────────────────────────┘
             │
             ▼
    [Orchestrator] → MongoDB (Decisions)
             │
             ▼
    [Auto Trading] → Zerodha API (Execution)
```

---

## Restart Policies

All services use `restart: unless-stopped`:
- Services automatically restart on failure
- Services do NOT restart after system reboot (unless manually started)
- Provides resilience against transient failures

---

## Network Isolation

- **Network**: `trading-network` (bridge driver)
- **Isolation**: All services isolated from host network
- **Communication**: Services use container names as DNS hostnames
- **External Access**: Only exposed ports accessible from host

---

## Key Design Patterns

### 1. **Multi-Tenancy**
- Separate bot/backend instances per instrument (BTC, BankNifty, Nifty)
- Isolated via environment files (`.env.btc`, `.env.banknifty`, `.env.nifty`)

### 2. **Health-Check Dependencies**
- Services wait for dependencies to be healthy before starting
- Prevents race conditions and connection errors

### 3. **Read-Only Credentials**
- `credentials.json` mounted as read-only (`:ro`)
- Prevents accidental modification

### 4. **Centralized Logging**
- All services write to shared `./logs` directory
- Easy log aggregation and monitoring

### 5. **Virtual Time Synchronization**
- Redis-based virtual time for historical replay
- All services synchronized via `TimeService`

---

## Potential Issues & Considerations

### 1. **Resource Consumption**
- **17 services** total - significant memory/CPU usage
- Consider resource limits per service

### 2. **Port Conflicts**
- Ensure host ports (27018, 6380, 8001-8003, 8888) are available

### 3. **Missing Environment Files**
- `.env.btc`, `.env.banknifty`, `.env.nifty` must exist
- Services will fail without these files

### 4. **Credentials File**
- `credentials.json` must exist for most services
- BTC services have this commented out (different auth?)

### 5. **Health Check Failures**
- Collectors' health checks may fail if Redis data is stale
- Consider more lenient health checks during startup

### 6. **Network Bandwidth**
- Multiple WebSocket connections (Zerodha API)
- May need rate limiting or connection pooling

---

## Recommended Improvements

1. **Add Resource Limits**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '0.5'
         memory: 512M
   ```

2. **Environment Variable Validation**:
   - Add startup scripts to validate required env vars

3. **Log Rotation**:
   - Configure log rotation for persistent logs

4. **Monitoring**:
   - Add Prometheus metrics exporters
   - Add health check endpoints

5. **Secrets Management**:
   - Use Docker secrets or external secret manager
   - Avoid mounting `credentials.json` directly

6. **Service Scaling**:
   - Consider using Docker Swarm or Kubernetes for scaling

---

## Usage Examples

### Start All Services
```bash
docker-compose up -d
```

### Start Specific Service
```bash
docker-compose up -d orchestrator-service
```

### View Logs
```bash
docker-compose logs -f orchestrator-service
```

### Stop All Services
```bash
docker-compose down
```

### Stop and Remove Volumes
```bash
docker-compose down -v
```

### Rebuild After Code Changes
```bash
docker-compose build
docker-compose up -d
```

---

## Summary

The Docker Compose setup orchestrates a **complex multi-service trading system** with:

- **2 Infrastructure Services**: MongoDB, Redis
- **3 Trading Bot Instances**: BTC, BankNifty, Nifty
- **3 Backend API Instances**: BTC, BankNifty, Nifty
- **4 Data Collectors**: LTP/Depth for BankNifty and Nifty
- **4 Core Services**: Dashboard, Orchestrator, Auto Trading, Historical Replay

**Total: 16 services** all connected via a single bridge network with sophisticated dependency management and health checks.

The architecture supports:
- ✅ Multi-instrument trading (BTC, BankNifty, Nifty)
- ✅ Real-time market data collection
- ✅ Multi-agent AI orchestration
- ✅ Automated trade execution
- ✅ Historical data replay
- ✅ Web dashboard for monitoring and control


