# Quick Setup Guide

## Prerequisites

- Python 3.9+
- MongoDB (running on localhost:27017)
- Redis (running on localhost:6379)

## Initial Setup

### 1. Clone and Setup Virtual Environment

```bash
# Clone repository
git clone <repo-url>
cd zerodha

# Setup virtual environment (auto-creates .venv)
python scripts/setup_venv.py
```

### 2. Configure Environment

Copy `.env.example` to `.env` (if exists) or create `.env` with:

```bash
# LLM Configuration
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434

# Database
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=zerodha_trading
REDIS_HOST=localhost
REDIS_PORT=6379

# News API (optional)
NEWS_API_KEY=your_key_here

# Zerodha Credentials (for Bank Nifty/Nifty)
KITE_API_KEY=your_key
KITE_API_SECRET=your_secret
```

### 3. Start System

**For Bitcoin:**
```bash
python scripts/start_all.py BTC
```

**For Bank Nifty:**
```bash
python scripts/start_all.py BANKNIFTY
```

**For Nifty 50:**
```bash
python scripts/start_all.py NIFTY
```

The script will:
1. ✅ Auto-configure `.env` for selected instrument
2. ✅ Use `.venv` virtual environment
3. ✅ Start dashboard (http://localhost:8888)
4. ✅ Start trading service

## Manual Configuration

If you want to manually configure instrument:

```bash
python scripts/configure_instrument.py BTC
# or
python scripts/configure_instrument.py BANKNIFTY
# or
python scripts/configure_instrument.py NIFTY
```

## Stop System

```bash
python scripts/stop_all.py
```

Or press `Ctrl+C` in the terminal running `start_all.py`

## Virtual Environment

The system **always uses `.venv`** if it exists. To recreate:

```bash
# Remove old venv
rm -rf .venv  # Linux/Mac
rmdir /s .venv  # Windows

# Create new venv
python scripts/setup_venv.py
```

## Environment Variables

All configuration is in **single `.env` file**. The instrument flag updates these variables:

- `INSTRUMENT_SYMBOL` - Trading symbol
- `INSTRUMENT_NAME` - Display name
- `DATA_SOURCE` - ZERODHA or CRYPTO
- `MARKET_24_7` - true for crypto, false for stocks
- `MACRO_DATA_ENABLED` - true for stocks, false for crypto
- `NEWS_QUERY` - News search query
- And more...

## Troubleshooting

### Virtual Environment Not Found

```bash
python scripts/setup_venv.py
```

### Missing Dependencies

```bash
# Activate venv manually
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install requirements
pip install -r requirements.txt
```

### Wrong Instrument Active

Check `.env` file or reconfigure:
```bash
python scripts/configure_instrument.py BTC
```

## File Structure

```
.
├── .venv/              # Virtual environment (auto-created)
├── .env                # Single config file (auto-updated)
├── requirements.txt    # Python dependencies
├── scripts/
│   ├── setup_venv.py           # Setup virtual environment
│   ├── configure_instrument.py # Configure instrument flag
│   ├── start_all.py            # Start system with flag
│   └── stop_all.py             # Stop all services
└── ...
```

