# Complete API Endpoints Summary

**Last Updated**: January 15, 2026
**Status**: ✅ Standardized - Complete API reference for all services.

## 🎯 Service Architecture Overview

The trading system consists of 6 core modules, each exposing REST APIs:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dashboard     │    │   Engine        │    │   User          │
│   (Port 8888)   │    │   (Port 8006)   │    │   (Port 8007)   │
│ • Web UI        │    │ • Analysis      │    │ • Trading       │
│ • Real-time WS  │    │ • Signals       │    │ • Portfolio     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Market Data    │    │   GenAI         │    │   News          │
│  (Port 8004)    │    │  (Port 8008)    │    │  (Port 8005)    │
│ • Live/History  │    │ • LLM Orchest.  │    │ • RSS/News      │
│ • Technical Ind.│    │ • Multi-Prov.   │    │ • Sentiment     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📊 Dashboard API (Port 8888)

### System Management
- `GET /api/system-health` - System health check
- `GET /api/system-status` - Complete system status
- `GET /api/config` - System configuration

### Trading Operations
- `GET /api/latest-analysis` - Latest trading analysis
- `GET /api/latest-signal` - Latest trading signal
- `POST /api/execute-signal` - Execute trading signal
- `GET /api/portfolio` - Portfolio summary
- `GET /api/performance` - Performance analytics

### Market Data
- `GET /api/market-data` - Market data overview
- `GET /api/technical-indicators/{instrument}` - Technical indicators
- `GET /api/options-chain/{instrument}` - Options chain

### WebSocket
- `WS /ws` - Real-time updates stream
  - Events: `market_update`, `signal_update`, `decision_update`, `portfolio_update`

## 📈 Market Data API (Port 8004)

### Health & Status
- `GET /health` - Service health check

### Live Market Data
- `GET /api/v1/market/tick/{instrument}` - Latest tick data
- `GET /api/v1/market/price/{instrument}` - Current price (Redis direct)
- `GET /api/v1/market/ohlc/{instrument}` - OHLC bars (params: `timeframe`, `limit`)
- `GET /api/v1/market/raw/{instrument}` - Raw Redis data (params: `limit`)

### Options & Derivatives
- `GET /api/v1/options/chain/{instrument}` - Options chain (requires Kite API)

### Technical Analysis
- `GET /api/v1/technical/indicators/{instrument}` - All technical indicators
  - RSI, MACD, Bollinger Bands, SMA, EMA, ADX, ATR, Volume, etc.

### Historical Replay
- `POST /api/v1/market/replay/start` - Start historical replay
- `POST /api/v1/market/replay/stop` - Stop historical replay
- `GET /api/v1/market/replay/status` - Replay status

## 🤖 Engine API (Port 8006)

### Health & Status
- `GET /health` - Service health check

### Analysis & Signals
- `POST /api/v1/analyze` - Run orchestrator analysis cycle
- `GET /api/v1/analysis/status` - Current analysis status
- `GET /api/v1/signals/{instrument}` - Trading signals for instrument
- `GET /api/v1/agents/{agent_id}/signal` - Individual agent signals

### Orchestrator Control
- `POST /api/v1/orchestrator/initialize` - Initialize orchestrator
- `GET /api/v1/orchestrator/status` - Orchestrator status
- `POST /api/v1/orchestrator/pause` - Pause analysis cycles
- `POST /api/v1/orchestrator/resume` - Resume analysis cycles

## 👤 User API (Port 8007)

### Health & Status
- `GET /health` - Service health check

### User Management
- `POST /api/v1/users` - Create user account
- `GET /api/v1/users/{user_id}` - Get user details
- `PUT /api/v1/users/{user_id}` - Update user profile
- `DELETE /api/v1/users/{user_id}` - Delete user account

### Portfolio & Trading
- `GET /api/v1/users/{user_id}/portfolio` - User portfolio
- `POST /api/v1/users/{user_id}/trades` - Execute trade
- `GET /api/v1/users/{user_id}/trades` - Trade history
- `GET /api/v1/users/{user_id}/performance` - Performance metrics

### Risk Management
- `GET /api/v1/risk/{user_id}` - Risk profile assessment
- `PUT /api/v1/risk/{user_id}` - Update risk settings
- `GET /api/v1/risk/{user_id}/limits` - Current risk limits

## 🧠 GenAI API (Port 8008)

### Health & Status
- `GET /health` - Service health check

### LLM Generation
- `POST /api/v1/generate` - Generate LLM response
- `POST /api/v1/generate/stream` - Streaming LLM response
- `GET /api/v1/providers` - Available LLM providers
- `GET /api/v1/providers/status` - Provider health status

### Prompt Management
- `POST /api/v1/prompts` - Save prompt template
- `GET /api/v1/prompts` - List prompt templates
- `GET /api/v1/prompts/{name}` - Get prompt template
- `PUT /api/v1/prompts/{name}` - Update prompt template
- `DELETE /api/v1/prompts/{name}` - Delete prompt template

## 📰 News API (Port 8005)

### Health & Status
- `GET /health` - Service health check

### News Data
- `GET /api/v1/news/latest` - Latest news items (params: `limit`, `instrument`)
- `GET /api/v1/news/{instrument}` - News for specific instrument
- `GET /api/v1/news/{instrument}/sentiment` - Sentiment analysis (params: `hours`)
- `POST /api/v1/news/collect` - Trigger news collection

### Sentiment Analysis
- `POST /api/v1/news/analyze` - Analyze custom text sentiment
- `GET /api/v1/news/sources` - Available news sources
- `GET /api/v1/news/{instrument}/trends` - Sentiment trends

## 🔄 Data Flow Architecture

```
Zerodha Kite API / RSS Feeds / Historical Data
                  ↓
             Redis Cache
                  ↓
    ┌─────┬─────┬─────┬─────┬─────┐
    │Dash │Mkt  │Eng  │User │GenAI│
    │board│Data │API  │API  │API  │
    └─────┴─────┴─────┴─────┴─────┘
                  ↓
        UI / External Clients
```

## 🚀 Quick Start Examples

### System Health Check
```bash
# Dashboard
curl http://localhost:8888/api/system-health

# All services
for port in 8004 8005 8006 8007 8008; do
  curl -s http://localhost:$port/health
done
```

### Trading Workflow
```bash
# 1. Get market data
curl http://localhost:8004/api/v1/market/price/BANKNIFTY

# 2. Run analysis
curl -X POST http://localhost:8006/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"instrument": "BANKNIFTY"}'

# 3. Check signals
curl http://localhost:8006/api/v1/signals/BANKNIFTY

# 4. Execute trade (if signal conditions met)
curl -X POST http://localhost:8888/api/execute-signal \
  -H "Content-Type: application/json" \
  -d '{"signal_id": "signal_123"}'
```

### Real-time Monitoring
```bash
# WebSocket connection for live updates
wscat -c ws://localhost:8888/ws
```

## 📝 API Standards

### Response Format
All APIs return JSON responses with consistent structure:

```json
{
  "status": "success|error",
  "data": { ... },
  "message": "Optional message",
  "timestamp": "ISO 8601 timestamp"
}
```

### Error Handling
- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `404` - Not Found
- `500` - Internal Server Error

### Authentication
- API keys via headers: `X-API-Key`
- JWT tokens for user sessions
- Service-to-service authentication via mutual TLS

### Rate Limiting
- 1000 requests/minute per IP
- 10000 requests/minute per API key
- Burst limits: 100 requests/second

## 🔧 Development

### API Documentation
- **OpenAPI/Swagger**: Available at `/docs` for each service
- **ReDoc**: Available at `/redoc` for each service
- **Postman Collection**: Available in `docs/` directory

### Testing
```bash
# Run API tests
cd dashboard && python tests/test_smoke.py

# Load testing
ab -n 1000 -c 10 http://localhost:8888/api/system-health
```

### Monitoring
- **Health Checks**: All services expose `/health` endpoints
- **Metrics**: Prometheus metrics at `/metrics` (where available)
- **Logs**: Structured JSON logging to stdout

#### Health & Status
- `GET /health` - Service health check

#### Analysis & Signals
- `POST /api/v1/analyze` - Run orchestrator analysis
- `GET /api/v1/signals/{instrument}` - Get trading signals
  - Signals include new metadata fields: `execution_mode`, `parsed_conditions`, `reason_hash`, and `entry_price` to support conditional execution, visibility into parsed conditions, and deduplication.
- `POST /api/v1/orchestrator/initialize` - Initialize orchestrator

## 📊 Data Flow

```
Zerodha Kite API / Collectors
         ↓
    Redis Store
         ↓
  Market Data API
         ↓
    UI / Engine
```

## 🔑 Configuration

### Environment Variables (`market_data/.env.banknifty`)

```bash
# Zerodha API
KITE_API_KEY=anbel41tccg186z0
KITE_API_SECRET=hvfug2sn5h1xe1ky3qbuj1gsntd9kk86

# LLM APIs
GROQ_API_KEY=gsk_...
AI21_API_KEY=...
COHERE_API_KEY=...

# Infrastructure
MONGODB_URI=mongodb://mongodb:27017/zerodha_trading
REDIS_HOST=redis
REDIS_PORT=6379
```

## 🚀 Quick Start Examples

### Get Latest Price
```bash
curl http://localhost:8004/api/v1/market/price/BANKNIFTY
```

### Get Technical Indicators
```bash
curl http://localhost:8004/api/v1/technical/indicators/BANKNIFTY
```

### Get Options Chain
```bash
curl http://localhost:8004/api/v1/options/chain/BANKNIFTY
```

### Get News
```bash
curl http://localhost:8005/api/v1/news/BANKNIFTY?limit=10
```

### Get Trading Signals
```bash
curl http://localhost:8006/api/v1/signals/BANKNIFTY
```

## 📝 Notes

1. **Market Data**: Requires collectors to be running (LTP, Depth collectors)
2. **Options Chain**: Requires Kite API credentials
3. **Technical Indicators**: Calculated automatically as data arrives
4. **News**: Uses yfinance for Indian indices (BANKNIFTY → ^NSEBANK, NIFTY → ^NSEI)
5. **All APIs**: Support CORS and return JSON responses

## 🔄 Data Collection

Once market data collectors start (with API keys configured), all endpoints will automatically have data:
- Price data → `/api/v1/market/price/{instrument}`
- OHLC data → `/api/v1/market/ohlc/{instrument}`
- Technical indicators → `/api/v1/technical/indicators/{instrument}`
- Options chain → `/api/v1/options/chain/{instrument}`

