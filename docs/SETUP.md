# Setup Guide

Complete setup instructions for the GenAI Trading System.

## Prerequisites

- **Python**: 3.9 or higher
- **MongoDB**: 4.4 or higher (local or remote)
- **Redis**: 6.0 or higher (optional but recommended)
- **Zerodha Kite Connect**: Active account with API access
- **LLM Provider**: OpenAI, Azure OpenAI, Groq, Ollama, Hugging Face, Together AI, or Google Gemini

## Installation Steps

### 1. Clone Repository

```bash
git clone <repository-url>
cd zerodha
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Databases

#### MongoDB

**Local Installation**:
```bash
# Windows (using MongoDB installer)
# Download from https://www.mongodb.com/try/download/community

# Linux
sudo apt-get install mongodb

# macOS
brew install mongodb-community

# Start MongoDB
mongod
```

**Docker**:
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

#### Redis (Optional but Recommended)

**Local Installation**:
```bash
# Windows (using WSL or installer)
# Download from https://redis.io/download

# Linux
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
redis-server
```

**Docker**:
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

**Note**: System works without Redis but with reduced performance. Redis is used for hot data caching.

### 4. Configure Environment Variables

Create `.env` file in project root:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Zerodha Kite Connect (Required)
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret

# MongoDB (Required)
MONGODB_URI=mongodb://localhost:27017/
MONGODH_DB_NAME=zerodha_trading

# Redis (Optional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# LLM Provider (Required - choose one)
LLM_PROVIDER=groq  # Options: groq, openai, azure, ollama, huggingface, together, gemini
LLM_MODEL=llama-3.3-70b-versatile  # Model name varies by provider

# Groq (if using Groq)
GROQ_API_KEY=your_groq_api_key

# OpenAI (if using OpenAI)
OPENAI_API_KEY=your_openai_api_key

# Azure OpenAI (if using Azure)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your_azure_api_key
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Ollama (if using Ollama - local)
OLLAMA_BASE_URL=http://localhost:11434

# Hugging Face (if using Hugging Face)
HUGGINGFACE_API_KEY=your_huggingface_api_key

# Together AI (if using Together AI)
TOGETHER_API_KEY=your_together_api_key

# Google Gemini (if using Gemini)
GOOGLE_API_KEY=your_google_api_key

# News API (Optional - for news collection)
NEWS_API_KEY=your_news_api_key
NEWS_UPDATE_INTERVAL_MINUTES=5

# Trading Configuration
PAPER_TRADING_MODE=true  # Start in paper trading mode
MARKET_OPEN_TIME=09:15:00
MARKET_CLOSE_TIME=15:30:00

# Risk Management
MAX_POSITION_SIZE_PCT=5.0
MAX_LEVERAGE=2.0
DEFAULT_STOP_LOSS_PCT=1.5
DEFAULT_TAKE_PROFIT_PCT=3.0
```

### 5. Initialize MongoDB Schema

```bash
python mongodb_schema.py
```

This creates all required collections and indexes.

### 6. Authenticate with Zerodha

```bash
python auto_login.py
```

This will:
1. Open browser for Zerodha login
2. Generate access token
3. Save credentials to `credentials.json`

**Note**: Access token expires daily. You may need to re-authenticate.

### 7. Verify Setup

```bash
python scripts/verify_setup.py
```

This checks:
- MongoDB connection
- Redis connection (if configured)
- Zerodha credentials
- LLM provider configuration
- Environment variables

## Running the System

### Option 1: Unified Trading Service (Recommended)

Starts all components in a single process:

```bash
python -m services.trading_service
```

Or:

```bash
python start_trading_system.py
```

This starts:
- Data ingestion (Zerodha WebSocket)
- Trading graph (60-second analysis cycle)
- Position monitoring
- All agents

### Option 2: Start All Services Script

```bash
python scripts/start_all.py
```

This starts:
- Monitoring dashboard
- Data feed
- Trading service

### Option 3: Separate Components

**Start Data Ingestion**:
```bash
python -m data.run_ingestion
```

**Start Trading Graph**:
```bash
python -m trading_orchestration.main
```

**Start Monitoring Dashboard**:
```bash
python -m monitoring.dashboard
```

Access dashboard at `http://localhost:8888`

## Configuration Details

### LLM Provider Setup

See [LLM_PROVIDER_GUIDE.md](../LLM_PROVIDER_GUIDE.md) for detailed setup instructions for each provider.

**Quick Setup**:
- **Groq**: Free tier available, fast responses
- **OpenAI**: Paid, high quality
- **Ollama**: Local, free, requires model download
- **Together AI**: Free tier available
- **Hugging Face**: Free tier available

### Paper Trading Mode

System starts in paper trading mode by default (`PAPER_TRADING_MODE=true`). Trades are simulated without real money.

To switch to live trading:
1. Set `PAPER_TRADING_MODE=false` in `.env`
2. Ensure sufficient capital in Zerodha account
3. Start with small position sizes
4. Monitor closely

### Market Hours

Default: 09:15:00 to 15:30:00 IST (Indian Standard Time)

Configure in `.env`:
```env
MARKET_OPEN_TIME=09:15:00
MARKET_CLOSE_TIME=15:30:00
```

System runs analysis every 60 seconds during market hours.

## Troubleshooting

### MongoDB Connection Issues

**Error**: `Connection refused`

**Solution**:
1. Check if MongoDB is running: `mongod --version`
2. Check MongoDB port: Default is 27017
3. Verify connection string in `.env`

### Redis Connection Issues

**Error**: `Redis not available`

**Solution**:
1. System works without Redis (fallback mode)
2. To use Redis: Install and start Redis server
3. Check Redis port: Default is 6379

### Zerodha Authentication Issues

**Error**: `credentials.json not found`

**Solution**:
1. Run `python auto_login.py`
2. Complete browser login
3. Verify `credentials.json` exists

**Error**: `Access token expired`

**Solution**:
1. Re-run `python auto_login.py`
2. Access tokens expire daily

### LLM Provider Issues

**Error**: `API key not configured`

**Solution**:
1. Check `.env` file has correct API key
2. Verify provider name matches (e.g., `LLM_PROVIDER=groq`)
3. Test API key with provider's test endpoint

**Error**: `Rate limit exceeded`

**Solution**:
1. Switch to different LLM provider
2. See [FREE_LLM_GUIDE.md](../FREE_LLM_GUIDE.md) for free alternatives
3. Use `scripts/switch_llm_provider.py` to switch providers

### Data Feed Issues

**Error**: `No current price available`

**Solution**:
1. Check Zerodha WebSocket connection
2. Verify instrument token is correct
3. Check market is open
4. Review logs for WebSocket errors

### Agent Analysis Issues

**Error**: `No analysis available`

**Solution**:
1. Check LLM provider is working
2. Verify agents are receiving data
3. Check MongoDB for stored analysis
4. Review agent logs

## Next Steps

After setup:

1. **Monitor Dashboard**: Check `http://localhost:8888` for system status
2. **Review Agent Analysis**: Check dashboard for agent outputs
3. **Paper Trading**: Test system in paper trading mode
4. **Review Trades**: Check MongoDB `trades` collection
5. **Adjust Configuration**: Tune risk parameters, thresholds, etc.

## Production Deployment

For production deployment:

1. Use environment variables (not `.env` file)
2. Set up proper logging (file-based)
3. Use production MongoDB (MongoDB Atlas, etc.)
4. Use production Redis (AWS ElastiCache, etc.)
5. Set up monitoring and alerts
6. Use process manager (systemd, PM2, etc.)
7. Enable SSL/TLS for API connections
8. Set up backup strategy

See [DEPLOYMENT.md](../DEPLOYMENT.md) for production deployment guide.

