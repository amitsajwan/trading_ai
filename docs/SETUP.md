# Setup Guide

Complete setup instructions for the GenAI Trading System.

## Prerequisites

- **Python**: 3.9 or higher
- **MongoDB**: 4.4 or higher (local or remote)
- **Redis**: 6.0 or higher (optional but recommended)
- **LLM Provider**: Ollama (local) OR cloud API key (Groq, Gemini, etc.)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup LLM Provider

**Option A: Ollama (Recommended - FREE, No Rate Limits)**

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1:8b

# Start Ollama (runs in background)
ollama serve
```

**Option B: Cloud Provider (Free Tiers Available)**

Get a free API key from one of:
- **Groq**: [console.groq.com](https://console.groq.com) - 100K tokens/day free
- **Google Gemini**: [aistudio.google.com](https://aistudio.google.com/app/apikey) - 1500 req/day free
- **OpenRouter**: [openrouter.ai](https://openrouter.ai) - Limited free tier

### 3. Configure Environment

Create `.env` file in project root:

```bash
# LLM Configuration (choose one)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# OR use cloud provider:
# LLM_PROVIDER=groq
# GROQ_API_KEY=your_key_here

# Instrument Configuration
INSTRUMENT_SYMBOL=BTC-USD       # BTC-USD, NIFTY BANK, NIFTY 50
INSTRUMENT_NAME=Bitcoin         # Bitcoin, Bank Nifty, Nifty 50
DATA_SOURCE=CRYPTO              # CRYPTO or ZERODHA
MARKET_24_7=true                # true for crypto, false for stocks

# Database
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=crypto_trading
REDIS_HOST=localhost
REDIS_PORT=6379

# Trading (always start in paper mode!)
PAPER_TRADING_MODE=true
```

### 4. Setup Databases

**MongoDB:**
```bash
# Docker (easiest)
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Or install locally: https://www.mongodb.com/try/download/community
```

**Redis (Optional):**
```bash
# Docker
docker run -d -p 6379:6379 --name redis redis:latest

# Or install locally
# System works without Redis but with reduced performance
```

### 5. Initialize MongoDB Schema

```bash
python mongodb_schema.py
```

### 6. Verify Setup

```bash
python scripts/diagnose_llm_system.py
```

This checks:
- ✅ LLM provider availability
- ✅ Environment configuration
- ✅ Database connections
- ✅ Instrument configuration

### 7. Start the System

```bash
python scripts/start_all.py
```

Access dashboard at: http://localhost:8888

## Instrument Configuration

### Bitcoin (Crypto)

```bash
python scripts/configure_instrument.py BTC
```

Or manually set in `.env`:
```bash
INSTRUMENT_SYMBOL=BTC-USD
INSTRUMENT_NAME=Bitcoin
DATA_SOURCE=CRYPTO
MARKET_24_7=true
MACRO_DATA_ENABLED=false
```

### Bank Nifty (Indian Stocks)

Requires Zerodha Kite Connect credentials.

```bash
python scripts/configure_instrument.py BANKNIFTY
```

Or manually set in `.env`:
```bash
INSTRUMENT_SYMBOL=NIFTY BANK
INSTRUMENT_NAME=Bank Nifty
DATA_SOURCE=ZERODHA
MARKET_24_7=false
MACRO_DATA_ENABLED=true
KITE_API_KEY=your_key
KITE_API_SECRET=your_secret
```

Then authenticate:
```bash
python auto_login.py
```

## Running the System

### Option 1: All-in-One (Recommended)

```bash
python scripts/start_all.py
```

### Option 2: Separate Components

```bash
# Terminal 1: Dashboard
python -m monitoring.dashboard

# Terminal 2: Trading Service
python -m services.trading_service
```

### Option 3: Docker

```bash
docker-compose up -d
```

## Configuration Reference

### LLM Providers

| Provider | Env Variable | Notes |
|----------|--------------|-------|
| Ollama | `LLM_PROVIDER=ollama` | Local, free, no limits |
| Groq | `GROQ_API_KEY` | Fast, 100K tokens/day free |
| Gemini | `GOOGLE_API_KEY` | 1500 req/day free |
| OpenRouter | `OPENROUTER_API_KEY` | Multiple free models |
| Together AI | `TOGETHER_API_KEY` | $25 free credits |
| OpenAI | `OPENAI_API_KEY` | Paid only |

The system automatically falls back between providers if one fails.

### Trading Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PAPER_TRADING_MODE` | `true` | Simulate trades without real money |
| `MAX_POSITION_SIZE_PCT` | `5.0` | Max position as % of portfolio |
| `MAX_LEVERAGE` | `2.0` | Maximum leverage allowed |
| `DEFAULT_STOP_LOSS_PCT` | `1.5` | Default stop loss percentage |
| `DEFAULT_TAKE_PROFIT_PCT` | `3.0` | Default take profit percentage |

### Market Hours

| Instrument | Hours | Config |
|------------|-------|--------|
| Crypto | 24/7 | `MARKET_24_7=true` |
| Bank Nifty | 9:15-15:30 IST | `MARKET_24_7=false` |

## Troubleshooting

### No LLM Provider Available

```bash
# Run diagnostics
python scripts/diagnose_llm_system.py

# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve
```

### MongoDB Connection Issues

```bash
# Check MongoDB is running
mongod --version

# Start with Docker if needed
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### Rate Limit Errors

The system automatically falls back between LLM providers. If all are rate-limited:

1. Add more API keys to `.env`
2. Use Ollama (local, no limits)
3. Wait for rate limit reset

### No Price Data

1. Check `DATA_SOURCE` matches your instrument
2. For crypto: Binance WebSocket connects automatically
3. For stocks: Run `python auto_login.py` first

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Docker deployment
- AWS EC2 setup
- MongoDB Atlas configuration
- Security best practices
- Monitoring and alerting
