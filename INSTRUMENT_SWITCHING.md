# Multi-Symbol Trading System

This system now supports **running multiple trading instruments simultaneously** using separate Docker containers for each symbol.

## Supported Instruments

- **BTC**: Bitcoin trading via Binance (Port 8001)
- **BANKNIFTY**: Bank Nifty index via Zerodha (Port 8002)
- **NIFTY**: Nifty 50 index via Zerodha (Port 8003)

## Running Multiple Containers

### Quick Start - Run All Systems

```bash
# Start all trading systems (BTC, Bank Nifty, Nifty 50)
./manage_trading.bat start all

# Or on Linux/Mac:
./manage_trading.sh start all
```

### Individual System Control

```bash
# Start specific systems
./manage_trading.bat start btc          # Only Bitcoin
./manage_trading.bat start banknifty    # Only Bank Nifty
./manage_trading.bat start nifty        # Only Nifty 50

# Stop systems
./manage_trading.bat stop btc
./manage_trading.bat stop all

# Restart systems
./manage_trading.bat restart banknifty

# View logs
./manage_trading.bat logs btc

# Check status
./manage_trading.bat status
```

## Dashboard Access

Once running, access the dashboards at:

- **BTC Dashboard**: http://localhost:8001
- **Bank Nifty Dashboard**: http://localhost:8002
- **Nifty 50 Dashboard**: http://localhost:8003

## Architecture

Each symbol runs in its own container pair:
- `trading-bot-{symbol}`: Background trading logic
- `backend-{symbol}`: Web dashboard

All containers share the same MongoDB and Redis instances for data persistence.

## Data Sources (Best Practices)

### Crypto (BTC)
- **Prices**: Binance WebSocket (real-time streaming)
- **News**: Finnhub API (crypto category)

### Indian Markets (Bank Nifty / Nifty 50)
- **Prices**: Zerodha Kite Connect WebSocket (real-time)
- **News**: Finnhub API (general category)

## Configuration Files

Each instrument has its own `.env` file:
- `.env.btc` - Bitcoin configuration
- `.env.banknifty` - Bank Nifty configuration
- `.env.nifty` - Nifty 50 configuration

## Legacy Single-Container Mode

If you prefer the old switching approach:

```bash
# Switch environments (old way)
python scripts/utils/switch_env.py btc
docker-compose up -d backend trading-bot
```

## Adding New Instruments

1. Create a new `.env.<instrument>` file
2. Add services to `docker-compose.yml` with unique ports
3. Update `manage_trading.bat` and `manage_trading.sh`

## Fixed Issues

- ✅ Removed hardcoded "NIFTY BANK" references
- ✅ Made instrument keys dynamic
- ✅ Added multi-provider news support
- ✅ Improved configurability for different exchanges
- ✅ **NEW**: Simultaneous multi-symbol trading

## News API Support

The system now supports multiple news providers:
- **Finnhub**: For crypto and general news
- **NewsAPI**: Legacy support

Set `NEWS_API_PROVIDER=finnhub` in the env files.

## Adding New Instruments

1. Create a new `.env.<instrument>` file with appropriate settings
2. Update `scripts/utils/switch_env.py` to include the new instrument
3. Test the configuration

## Fixed Issues

- Removed hardcoded "NIFTY BANK" references
- Made instrument keys dynamic
- Added multi-provider news support
- Improved configurability for different exchanges