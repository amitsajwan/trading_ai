# 🚀 Quick Start Guide

## Starting the Trading System

**Use this single command to start everything:**

```bash
python scripts/start_all.py
```

That's it! This will:
- ✅ Configure the instrument (default: BTC)
- ✅ Verify LLM providers (Ollama/Groq)
- ✅ Start the data feed (Binance WebSocket for crypto)
- ✅ Launch the trading service with all agents
- ✅ Start the dashboard on port 8888

## Options

### Skip data verification (useful for testing without live data):
```bash
python scripts/start_all.py --skip-data-verification
```

### Trade a different instrument:
```bash
python scripts/start_all.py --instrument NIFTY
```

## Accessing the Dashboard

Once started, open your browser to:
**http://localhost:8888**

The dashboard shows:
- 📊 Current market data
- 🤖 Agent analysis (Technical, Fundamental, Sentiment, Macro)
- 💼 Portfolio positions
- 📈 Trading performance metrics
- ⚠️ System health

## What Happened to Other Files?

All duplicate/deprecated files have been removed:
- ❌ `monitoring/dashboard.py` (removed - duplicate)
- ❌ `start_trading_system.py` (removed - deprecated)
- ✅ `dashboard_pro.py` (consolidated dashboard)
- ✅ `scripts/start_all.py` (single entry point)

## Stopping the System

Press `Ctrl+C` in the terminal where `start_all.py` is running.
All components will shut down gracefully.

## Need Help?

Check the README.md for detailed documentation.
