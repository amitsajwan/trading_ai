# Complete API Endpoints Summary

## 🎯 All Available API Endpoints

### Market Data API (Port 8004)

#### Health & Status
- `GET /health` - Service health check

#### Market Data
- `GET /api/v1/market/tick/{instrument}` - Latest tick data
- `GET /api/v1/market/ohlc/{instrument}` - OHLC bars (with timeframe & limit params)
- `GET /api/v1/market/price/{instrument}` - **NEW** - Direct Redis price access
- `GET /api/v1/market/raw/{instrument}` - **NEW** - Raw Redis data

#### Options Chain
- `GET /api/v1/options/chain/{instrument}` - Options chain data

#### Technical Indicators
- `GET /api/v1/technical/indicators/{instrument}` - **ENHANCED** - All technical indicators
  - RSI, SMA, EMA, MACD, Bollinger Bands, ATR, ADX, Volume indicators, etc.

### News API (Port 8005)

#### Health & Status
- `GET /health` - Service health check

#### News Data
- `GET /api/v1/news/{instrument}` - Latest news (now with yfinance support)
- `GET /api/v1/news/{instrument}/sentiment` - Sentiment summary
- `POST /api/v1/news/collect` - Trigger news collection

**News Sources:**
- RSS feeds (MoneyControl, Economic Times, Business Standard)
- **NEW**: Yahoo Finance (yfinance) - for BANKNIFTY, NIFTY, etc.

### Engine API (Port 8006)

#### Health & Status
- `GET /health` - Service health check

#### Analysis & Signals
- `POST /api/v1/analyze` - Run orchestrator analysis
- `GET /api/v1/signals/{instrument}` - Get trading signals
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

