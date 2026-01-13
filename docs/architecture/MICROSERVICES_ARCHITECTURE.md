# Microservices Architecture

This document describes the microservices architecture for the Zerodha trading system.

## Overview

The system is organized into independent modules, each with its own REST API service:

1. **Market Data API** (Port 8004) - Market data, options chain, technical indicators
2. **News API** (Port 8005) - News collection, sentiment analysis
3. **Engine API** (Port 8006) - Trading orchestrator, signals, agent analysis
4. **Dashboard Service** (Port 8888) - Main UI dashboard (existing)

## Architecture Principles

### 1. Module Independence
- Each module has its own API service
- Modules can be deployed independently
- Each module has its own `.env` file for configuration

### 2. API Contracts
- Each module exposes a well-defined REST API
- API contracts are documented in `{module}/API_CONTRACT.md`
- Health check endpoints for monitoring

### 3. Data Access Patterns
- **Engine Module**: Can access Redis/MongoDB directly for performance
- **UI/Dashboard**: Should use REST APIs for all data access
- **Internal Services**: Can use direct cache access for low latency

### 4. Service Communication
- Services communicate via HTTP REST APIs
- Services share Redis and MongoDB for data
- Service discovery via Docker container names

## Module APIs

### Market Data API (`market_data`)

**Base URL**: `http://localhost:8004`

**Endpoints**:
- `GET /health` - Health check
- `GET /api/v1/market/tick/{instrument}` - Latest tick data
- `GET /api/v1/market/ohlc/{instrument}` - OHLC bars
- `GET /api/v1/options/chain/{instrument}` - Options chain
- `GET /api/v1/technical/indicators/{instrument}` - Technical indicators

**Configuration**: `market_data/.env.example`

### News API (`news_module`)

**Base URL**: `http://localhost:8005`

**Endpoints**:
- `GET /health` - Health check
- `GET /api/v1/news/{instrument}` - Latest news
- `GET /api/v1/news/{instrument}/sentiment` - Sentiment summary
- `POST /api/v1/news/collect` - Trigger news collection

**Configuration**: `news_module/.env.example`

### Engine API (`engine_module`)

**Base URL**: `http://localhost:8006`

**Endpoints**:
- `GET /health` - Health check
- `POST /api/v1/analyze` - Run orchestrator analysis
- `GET /api/v1/signals/{instrument}` - Get trading signals
- `POST /api/v1/orchestrator/initialize` - Initialize orchestrator

**Configuration**: `engine_module/.env.example`

## Docker Services

All API services are defined in `docker-compose.yml`:

```yaml
services:
  market-data-api:
    ports: ["8004:8004"]
    environment:
      - REDIS_HOST=redis
      - MONGODB_URI=mongodb://mongodb:27017/zerodha_trading
  
  news-api:
    ports: ["8005:8005"]
    environment:
      - MONGODB_URI=mongodb://mongodb:27017/zerodha_trading
  
  engine-api:
    ports: ["8006:8006"]
    environment:
      - REDIS_HOST=redis
      - MONGODB_URI=mongodb://mongodb:27017/zerodha_trading
```

## Health Checks

All services expose a `/health` endpoint that returns:

```json
{
  "status": "healthy" | "degraded",
  "module": "module_name",
  "timestamp": "ISO timestamp",
  "dependencies": {
    "redis": "healthy",
    "mongodb": "healthy"
  }
}
```

## Environment Configuration

Each module should have its own `.env` file (use `.env.example` as template):

- `market_data/.env` - Market data configuration
- `news_module/.env` - News module configuration
- `engine_module/.env` - Engine module configuration

## Usage Examples

### From UI/Dashboard

```python
import requests

# Get market data
response = requests.get("http://market-data-api:8004/api/v1/market/tick/BANKNIFTY")
tick_data = response.json()

# Get news sentiment
response = requests.get("http://news-api:8005/api/v1/news/BANKNIFTY/sentiment")
sentiment = response.json()

# Run analysis
response = requests.post("http://engine-api:8006/api/v1/analyze", json={
    "instrument": "BANKNIFTY",
    "context": {"market_hours": True}
})
analysis = response.json()
```

### From Engine (Direct Cache Access)

```python
# Engine can access Redis directly for performance
import redis
r = redis.Redis(host="redis", port=6379)
price = r.get("price:BANKNIFTY:last_price")
```

## Migration Path

1. **Phase 1**: Create API services (✅ Done)
2. **Phase 2**: Update UI to use APIs instead of direct access
3. **Phase 3**: Add API gateway for unified access
4. **Phase 4**: Add service mesh for advanced routing

## Benefits

- **Scalability**: Each service can scale independently
- **Maintainability**: Clear separation of concerns
- **Testability**: Each API can be tested independently
- **Flexibility**: Services can be deployed separately
- **Monitoring**: Health checks enable proper monitoring

