# 🚀 Quick Start Guide

## Starting the Trading System

### Option A: Docker (Recommended)

**Start all instruments simultaneously:**
```bash
manage_trading.bat start all
```

**OR start specific instruments:**
```bash
manage_trading.bat start banknifty  # Bank Nifty
manage_trading.bat start nifty      # Nifty 50  
manage_trading.bat start btc        # Bitcoin
```

**Access dashboards:**
- Bank Nifty: http://localhost:8002
- Nifty 50: http://localhost:8003
- Bitcoin: http://localhost:8001

### Option B: Local Development

**Use this single command to start everything:**

```bash
python scripts/start_all.py
```

This will:
- ✅ Configure the instrument (default: BANKNIFTY for Indian markets)
- ✅ Verify LLM providers (Ollama/Groq/Gemini/OpenAI)
- ✅ Start the data feed (Zerodha Kite WebSocket for Indian markets)
- ✅ Launch the trading service with all agents
- ✅ Start the dashboard on port 8888

## Supported Instruments

The system supports multiple instruments:

| Instrument | Command | Market Hours |
|------------|---------|--------------|
| **Bank Nifty** | `python scripts/start_all.py --instrument BANKNIFTY` | 9:15-15:30 IST |
| **Nifty 50** | `python scripts/start_all.py --instrument NIFTY` | 9:15-15:30 IST |
| **Bitcoin** | `python scripts/start_all.py --instrument BTC` | 24/7 |

## Options

### Skip data verification (useful for testing without live data):
```bash
python scripts/start_all.py --skip-data-verification
```

### Trade a different instrument:
```bash
# Start with Bank Nifty (default)
python scripts/start_all.py --instrument BANKNIFTY

# Start with Nifty 50
python scripts/start_all.py --instrument NIFTY

# Start with Bitcoin
python scripts/start_all.py --instrument BTC
```

## Accessing the Dashboard

Once started, open your browser to:
**http://localhost:8888**

The dashboard shows:
- 📊 Current market data (live from Zerodha/Binance)
- 🤖 Agent analysis (Technical, Fundamental, Sentiment, Macro)
- 💼 Portfolio positions and P&L
- 📈 Trading performance metrics
- ⚠️ System health and alerts

## System Architecture Overview

### Core Components
- **Data Ingestion**: Real-time market data from Zerodha Kite or Binance
- **Agent System**: 10+ specialized LLM agents for market analysis
- **Portfolio Manager**: Synthesizes agent inputs into trading decisions
- **Risk Management**: Multi-layered risk controls and circuit breakers
- **Execution**: Order placement and position management
- **Learning Agent**: Continuous improvement through trade analysis

### Data Flow
```
Market Data → Redis Cache → LLM Agents → Portfolio Manager → Risk Check → Execution
                     ↓
                MongoDB Storage
```

## What Happened to Other Files?

All duplicate/deprecated files have been removed:
- ❌ `monitoring/dashboard.py` (removed - duplicate)
- ❌ `start_trading_system.py` (removed - deprecated)
- ✅ `dashboard_pro.py` (consolidated dashboard)
- ✅ `scripts/start_all.py` (single entry point)

## Stopping the System

Press `Ctrl+C` in the terminal where `start_all.py` is running.
All components will shut down gracefully.

Press `Ctrl+C` in the terminal where `start_all.py` is running.
All components will shut down gracefully.

## Need Help?

Check the README.md for detailed documentation.
