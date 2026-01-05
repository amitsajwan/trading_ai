# Instrument Configuration Guide

This guide explains how to configure the GenAI Trading System for different instruments (Bitcoin, Bank Nifty, Nifty 50) using the multi-container Docker setup.

## Overview

The system now supports **simultaneous trading** of multiple instruments using separate Docker containers. Each instrument has its own environment configuration and optimized data sources:

| Instrument | Container | Data Source | News API | Market Hours |
|------------|-----------|-------------|----------|--------------|
| Bitcoin | trading-bot-btc | Binance WebSocket | Finnhub | 24/7 |
| Bank Nifty | trading-bot-banknifty | Zerodha Kite | EODHD | 9:15-15:30 IST |
| Nifty 50 | trading-bot-nifty | Zerodha Kite | EODHD | 9:15-15:30 IST |

## Multi-Container Setup

### Starting Individual Systems

Use the management scripts to start/stop individual trading systems:

**Windows:**
```batch
# Start all systems
manage_trading.bat start all

# Start specific system
manage_trading.bat start btc
manage_trading.bat start banknifty
manage_trading.bat start nifty

# Stop systems
manage_trading.bat stop all
manage_trading.bat stop btc
```

**Linux/Mac:**
```bash
# Start all systems
./manage_trading.sh start all

# Start specific system
./manage_trading.sh start btc
./manage_trading.sh start banknifty
./manage_trading.sh start nifty
```

### Container Ports

Each system runs on a unique port:
- BTC: http://localhost:8001
- Bank Nifty: http://localhost:8002
- Nifty 50: http://localhost:8003

## Environment Configuration

Each instrument uses a separate `.env` file:

### Bitcoin (.env.btc)
```bash
# Instrument
INSTRUMENT_SYMBOL=BTC-USD
INSTRUMENT_NAME=Bitcoin
DATA_SOURCE=CRYPTO
MARKET_24_7=true

# News API - Finnhub for crypto news
NEWS_API_KEY=your_finnhub_key
NEWS_API_PROVIDER=finnhub

# Database (shared)
MONGODB_URI=mongodb://mongodb:27017/
REDIS_HOST=redis

# Trading
PAPER_TRADING_MODE=true
```

### Bank Nifty (.env.banknifty)
```bash
# Instrument
INSTRUMENT_SYMBOL=NIFTY BANK
INSTRUMENT_NAME=Bank Nifty
DATA_SOURCE=ZERODHA
MARKET_24_7=false

# News API - EODHD for Indian market news
NEWS_API_KEY=your_eodhd_key
NEWS_API_PROVIDER=eodhd
EODHD_API_KEY=your_eodhd_key

# Database (shared)
MONGODB_URI=mongodb://mongodb:27017/
REDIS_HOST=redis

# Trading
PAPER_TRADING_MODE=true
```

## Instrument Key Normalization (Important)

For Zerodha instruments, all internal Redis keys and cache lookups use a single, normalized symbol family key:

- Bank Nifty → NIFTYBANK
- Nifty 50 → NIFTY

This affects Redis key prefixes such as `price:<KEY>:latest`, `tick:<KEY>:*`, `volume:<KEY>:latest`, `vwap:<KEY>:latest`, `oi:<KEY>:latest`, and `snapshot:<KEY>:latest`.

Why this matters:
- Consistency across collectors, APIs, and snapshot builders.
- Avoids mixing similar variants like "BANKNIFTY" vs "NIFTY BANK".
- Prevents stale or wrong data when switching environments.

Implications:
- Do not write or depend on `BANKNIFTY` keys. Use `NIFTYBANK` for Bank Nifty.
- The reset script and all collectors/APIs already use this normalization.


### Nifty 50 (.env.nifty)
```bash
# Instrument
INSTRUMENT_SYMBOL=NIFTY 50
INSTRUMENT_NAME=Nifty 50
DATA_SOURCE=ZERODHA
MARKET_24_7=false

# News API - EODHD for Indian market news
NEWS_API_KEY=your_eodhd_key
NEWS_API_PROVIDER=eodhd
EODHD_API_KEY=your_eodhd_key

# Database (shared)
MONGODB_URI=mongodb://mongodb:27017/
REDIS_HOST=redis

# Trading
PAPER_TRADING_MODE=true
```

## API Keys Setup

### 1. Zerodha Kite (Indian Markets)
- Get API key from [Zerodha Kite Connect](https://kite.trade/connect/login)
- Add to `.env.banknifty` and `.env.nifty`:
```bash
ZERODHA_API_KEY=your_zerodha_key
ZERODHA_API_SECRET=your_zerodha_secret
```

### 2. Binance (Crypto)
- Get API key from [Binance](https://www.binance.com/en/my/settings/api-management)
- Add to `.env.btc`:
```bash
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret
```

### 3. News APIs

**Finnhub (Crypto News):**
- Get free API key from [Finnhub](https://finnhub.io/)
- Used for Bitcoin trading
- 60 requests/minute free tier

**EODHD (Indian Market News):**
- Get free API key from [EODHD](https://eodhd.com/)
- Used for Bank Nifty and Nifty 50 trading
- Better coverage of Indian financial news
- Free tier: 20 requests/minute, 1000 requests/day

## News API Configuration

The system automatically selects the appropriate news API based on the instrument:

- **Crypto instruments (BTC)**: Uses Finnhub for global crypto news
- **Indian instruments (Bank Nifty, Nifty 50)**: Uses EODHD for Indian financial news

News collection runs continuously and feeds into the sentiment analysis agent.

## Database Setup

All containers share the same MongoDB and Redis instances:

```bash
# Start databases
docker-compose up -d mongodb redis

# Verify connections
docker-compose logs mongodb redis
```

## Monitoring

### Individual System Logs
```bash
# BTC system logs
docker-compose logs trading-bot-btc backend-btc

# Bank Nifty logs
docker-compose logs trading-bot-banknifty backend-banknifty

# Nifty 50 logs
docker-compose logs trading-bot-nifty backend-nifty
```

### Health Checks
Each container includes health checks for:
- Database connectivity
- API key validation
- News feed availability
- Trading execution status

## Troubleshooting

### Common Issues

1. **Container won't start**: Check environment file exists and has correct API keys
2. **No market data**: Verify API keys and network connectivity
3. **News not updating**: Check news API key and provider configuration
4. **Database connection failed**: Ensure MongoDB/Redis are running

### Diagnostic Commands
```bash
# Check all containers
docker-compose ps

# View logs for specific service
docker-compose logs <service-name>

# Restart specific system
manage_trading.bat restart btc
```

## Production Deployment

For production:
1. Set `PAPER_TRADING_MODE=false`
2. Use production API keys
3. Configure proper logging and monitoring
4. Set up backup strategies for databases
5. Monitor system health continuously

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production setup.