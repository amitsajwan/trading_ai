# API Services Setup Guide

This guide explains how to set up and use the new microservices API architecture.

## Quick Start

### 1. Create Environment Files

Create `.env` files for each module (copy from `.env.example` if available):

```bash
# Market Data Module
cp market_data/.env.example market_data/.env
# Edit market_data/.env with your configuration

# News Module  
cp news_module/.env.example news_module/.env
# Edit news_module/.env with your configuration

# Engine Module
cp engine_module/.env.example engine_module/.env
# Edit engine_module/.env with your configuration
```

### 2. Start Services

Start all services using Docker Compose:

```bash
docker compose up -d market-data-api news-api engine-api
```

Or start all services:

```bash
docker compose up -d
```

### 3. Verify Services

Check service health:

```bash
# Market Data API
curl http://localhost:8004/health

# News API
curl http://localhost:8005/health

# Engine API
curl http://localhost:8006/health
```

## API Endpoints

### Market Data API (Port 8004)

- **Health**: `GET /health`
- **Latest Tick**: `GET /api/v1/market/tick/{instrument}`
- **OHLC Data**: `GET /api/v1/market/ohlc/{instrument}?timeframe=minute&limit=100`
- **Options Chain**: `GET /api/v1/options/chain/{instrument}`
- **Technical Indicators**: `GET /api/v1/technical/indicators/{instrument}`

See `market_data/API_CONTRACT.md` for detailed documentation.

### News API (Port 8005)

- **Health**: `GET /health`
- **Latest News**: `GET /api/v1/news/{instrument}?limit=10&hours=24`
- **Sentiment**: `GET /api/v1/news/{instrument}/sentiment?hours=24`
- **Collect News**: `POST /api/v1/news/collect`

See `news_module/API_CONTRACT.md` for detailed documentation.

### Engine API (Port 8006)

- **Health**: `GET /health`
- **Analyze**: `POST /api/v1/analyze`
- **Signals**: `GET /api/v1/signals/{instrument}?limit=10`
- **Initialize**: `POST /api/v1/orchestrator/initialize`

See `engine_module/API_CONTRACT.md` for detailed documentation.

## Configuration

### Market Data Module

Key environment variables:
- `REDIS_HOST` - Redis host (default: localhost)
- `REDIS_PORT` - Redis port (default: 6379)
- `MARKET_DATA_API_PORT` - API port (default: 8004)
- `KITE_API_KEY` - Zerodha API key (for live data)
- `KITE_API_SECRET` - Zerodha API secret

### News Module

Key environment variables:
- `MONGODB_URI` - MongoDB connection string
- `NEWS_API_PORT` - API port (default: 8005)
- `NEWS_SOURCES` - News sources (default: default)
- `OPENAI_API_KEY` - For advanced sentiment analysis

### Engine Module

Key environment variables:
- `REDIS_HOST` - Redis host
- `MONGODB_URI` - MongoDB connection string
- `ENGINE_API_PORT` - API port (default: 8006)
- `LLM_SELECTION_STRATEGY` - LLM selection strategy
- `OPENAI_API_KEY`, `GROQ_API_KEY`, etc. - LLM API keys

## Usage Examples

### Python Client

```python
import requests

# Market Data
response = requests.get("http://localhost:8004/api/v1/market/tick/BANKNIFTY")
tick = response.json()
print(f"Price: {tick['last_price']}")

# News Sentiment
response = requests.get("http://localhost:8005/api/v1/news/BANKNIFTY/sentiment")
sentiment = response.json()
print(f"Sentiment: {sentiment['sentiment_trend']}")

# Engine Analysis
response = requests.post("http://localhost:8006/api/v1/analyze", json={
    "instrument": "BANKNIFTY",
    "context": {"market_hours": True}
})
analysis = response.json()
print(f"Decision: {analysis['decision']}, Confidence: {analysis['confidence']}")
```

### JavaScript/TypeScript Client

```typescript
// Market Data
const tickResponse = await fetch('http://localhost:8004/api/v1/market/tick/BANKNIFTY');
const tick = await tickResponse.json();

// News
const newsResponse = await fetch('http://localhost:8005/api/v1/news/BANKNIFTY?limit=5');
const news = await newsResponse.json();

// Engine
const analysisResponse = await fetch('http://localhost:8006/api/v1/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    instrument: 'BANKNIFTY',
    context: { market_hours: true }
  })
});
const analysis = await analysisResponse.json();
```

## Integration with Dashboard

The dashboard should be updated to use these APIs instead of direct database access:

```python
# Old way (direct access)
from market_data.api import build_store
store = build_store(redis_client)
tick = store.get_latest_tick("BANKNIFTY")

# New way (via API)
import requests
response = requests.get("http://market-data-api:8004/api/v1/market/tick/BANKNIFTY")
tick = response.json()
```

## Troubleshooting

### Service Not Starting

1. Check Docker logs:
   ```bash
   docker compose logs market-data-api
   docker compose logs news-api
   docker compose logs engine-api
   ```

2. Verify dependencies:
   - MongoDB and Redis must be running
   - Check health endpoints

3. Check environment variables:
   - Ensure `.env` files are properly configured
   - Verify Redis and MongoDB connection strings

### API Returns 503

- Service dependencies not initialized
- Check service logs for initialization errors
- Verify Redis/MongoDB connectivity

### API Returns 404

- Resource not found
- Check if data exists in Redis/MongoDB
- Verify instrument symbol is correct

## Next Steps

1. Update dashboard to use APIs
2. Add API gateway for unified access
3. Implement authentication/authorization
4. Add rate limiting
5. Set up monitoring and alerting

