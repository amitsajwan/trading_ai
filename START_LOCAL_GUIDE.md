# start_local.py - Complete Usage Guide

Complete guide for running the trading system in **Real/Live mode** and **Historical mode** using `start_local.py`.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Real/Live Mode](#reallive-mode)
3. [Historical Mode](#historical-mode)
4. [Command Line Options](#command-line-options)
5. [Environment Variables](#environment-variables)
6. [Troubleshooting](#troubleshooting)
7. [Examples](#examples)

---

## Quick Start

### Real/Live Mode (Zerodha)
```bash
python start_local.py --provider zerodha
```

### Historical Mode (Zerodha)
```bash
python start_local.py --provider historical --historical-source zerodha --historical-from 2026-01-09
```

### Historical Mode (CSV)
```bash
python start_local.py --provider historical --historical-source ./data/historical.csv --historical-from 2026-01-09 --allow-missing-credentials
```

---

## Real/Live Mode

Runs the system with **live market data** from Zerodha API. Requires Zerodha credentials.

### Prerequisites

1. **Zerodha API Credentials** (required):
   - `KITE_API_KEY` - Your Zerodha API key
   - `KITE_API_SECRET` - Your Zerodha API secret
   - `KITE_ACCESS_TOKEN` - Your access token (auto-refreshed)

2. **Credentials Setup**:
   - Place credentials in `.env` file or `credentials.json`
   - Or set environment variables

### Basic Usage

```bash
# Start with Zerodha live data
python start_local.py --provider zerodha
```

### What Happens

1. **Market Data API** (port 8004) - Fetches live ticks, OHLC, options chain
2. **News API** (port 8005) - Fetches market news
3. **Engine API** (port 8006) - Runs 15 AI agents, generates signals
4. **User API** (port 8007) - Manages trades and positions
5. **Dashboard** (port 8888) - Web UI at http://localhost:8888

### Features Available

- ✅ Live market data (BANKNIFTY, NIFTY, etc.)
- ✅ Real-time options chain
- ✅ Live signal generation
- ✅ Paper trading execution
- ✅ Real-time WebSocket updates
- ✅ Full trading dashboard

### Command Options

- `--provider zerodha` - Use Zerodha live data (default if credentials available)
- `--skip-validation` - Skip health checks (faster startup)

---

## Historical Mode

Runs the system with **historical market data** for backtesting or when market is closed. Supports Zerodha API or CSV files.

### Prerequisites

**Option 1: Zerodha Historical Data** (requires credentials)
- Same credentials as Real/Live mode
- Zerodha API provides historical data

**Option 2: CSV File** (no credentials needed)
- CSV file with historical tick/bar data
- Use `--allow-missing-credentials` flag

### Basic Usage

```bash
# Zerodha historical data
python start_local.py --provider historical --historical-source zerodha --historical-from 2026-01-09

# CSV file historical data
python start_local.py --provider historical --historical-source ./data/historical.csv --historical-from 2026-01-09 --allow-missing-credentials
```

### What Happens

1. **Historical Replay** - Loads data from specified date
2. **Virtual Time** - System time synchronized to historical date
3. **Signal Generation** - Agents analyze historical data
4. **Paper Trading** - Trades execute based on historical conditions
5. **Dashboard** - Shows historical replay in real-time

### Features Available

- ✅ Historical data replay (Zerodha or CSV)
- ✅ Virtual time synchronization
- ✅ Signal generation on historical data
- ✅ Backtesting capabilities
- ✅ Full trading dashboard
- ✅ All features work as in live mode

---

## Command Line Options

### Provider Selection

- `--provider zerodha` - Real/Live mode with Zerodha
- `--provider historical` - Historical mode
- `--provider replay` - Alias for historical

### Historical Mode Options

- `--historical-source zerodha|path/to/file.csv` - Data source
  - `zerodha`: Use Zerodha API (requires credentials)
  - `path/to/file.csv`: Use CSV file (no credentials needed)
  
- `--historical-from YYYY-MM-DD` - **Required** - Start date for replay
  - Format: `YYYY-MM-DD` (e.g., `2026-01-09`)
  - Example: `--historical-from 2026-01-09`

- `--historical-speed FLOAT` - Playback speed multiplier
  - `1.0` = real-time (default)
  - `2.0` = 2x speed
  - `0.5` = half speed

- `--historical-ticks` - Use tick-level replayer
  - More detailed but slower
  - Preserves per-tick timestamps

### General Options

- `--allow-missing-credentials` - Allow startup without Zerodha credentials
  - Required for CSV-based historical runs
  - Optional for Zerodha (will prompt for credentials)

- `--skip-validation` - Skip health checks
  - Faster startup for testing
  - Not recommended for production

---

## Environment Variables

You can use environment variables instead of command-line arguments:

### Real/Live Mode
```bash
export TRADING_PROVIDER=zerodha
python start_local.py
```

### Historical Mode
```bash
export TRADING_PROVIDER=historical
export HISTORICAL_SOURCE=zerodha
export HISTORICAL_FROM=2026-01-09
export HISTORICAL_SPEED=1.0
export HISTORICAL_TICKS=0

python start_local.py
```

---

## Examples

### Example 1: Real/Live Mode (Default)
```bash
python start_local.py --provider zerodha
```

### Example 2: Historical Mode - Zerodha (Today's Date)
```bash
python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-09
```

### Example 3: Historical Mode - Zerodha (Fast Replay)
```bash
python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-09 \
  --historical-speed 2.0
```

### Example 4: Historical Mode - CSV File
```bash
python start_local.py \
  --provider historical \
  --historical-source ./data/historical_data.csv \
  --historical-from 2026-01-09 \
  --allow-missing-credentials
```

### Example 5: Historical Mode - Tick-Level (Most Detailed)
```bash
python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-09 \
  --historical-ticks \
  --historical-speed 1.0
```

### Example 6: Skip Validation (Faster Startup)
```bash
python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-09 \
  --skip-validation
```

---

## Troubleshooting

### Issue: "No ticks loaded for replay"

**Cause**: Historical data not found for the specified date.

**Solutions**:
- Verify date format: `YYYY-MM-DD` (e.g., `2026-01-09`)
- Check if Zerodha has data for that date (market was open)
- Verify Zerodha credentials if using `--historical-source zerodha`
- Try a different date
- For CSV: Verify file path and format

### Issue: "Zerodha credentials required"

**Cause**: Missing or invalid Zerodha credentials.

**Solutions**:
- Provide Zerodha credentials in `.env` or `credentials.json`
- Use CSV file instead: `--historical-source ./data.csv --allow-missing-credentials`
- Check credentials are valid: `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_ACCESS_TOKEN`

### Issue: "Invalid date format"

**Cause**: Date format incorrect.

**Solution**: Use `YYYY-MM-DD` format:
- ✅ Correct: `2026-01-09`
- ❌ Wrong: `01-09-2026`, `09/01/2026`, `2026/01/09`

### Issue: "Port already in use"

**Cause**: Previous instance still running.

**Solution**: 
- Kill processes on ports 8004, 8005, 8006, 8007, 8888
- Or restart the application (it will clean ports automatically)

### Issue: "Historical ticks not triggering signals"

**Cause**: Redis tick subscriber not running or data not loading.

**Solutions**:
- Check Engine API logs for "Redis tick subscriber started"
- Verify tick data is being published to Redis
- Check SignalMonitor has active signals
- Verify historical data loaded successfully

### Issue: "LLM API errors (401, 429)"

**Cause**: LLM API keys invalid or rate limited.

**Solution**: 
- System handles this gracefully with fallbacks
- Check logs for which provider is working
- Update API keys if needed (not critical for basic operation)

---

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| Market Data API | 8004 | http://localhost:8004 |
| News API | 8005 | http://localhost:8005 |
| Engine API | 8006 | http://localhost:8006 |
| User API | 8007 | http://localhost:8007 |
| Dashboard | 8888 | http://localhost:8888 |

---

## Verification

After starting, verify services are running:

```bash
# Check Market Data API
curl http://localhost:8004/health

# Check Engine API
curl http://localhost:8006/health

# Check Dashboard
curl http://localhost:8888
```

### Expected Startup Sequence

1. **Market Data API** - Starts first (port 8004)
2. **News API** - Starts second (port 8005)
3. **Historical Replay** - Loads data (if historical mode)
4. **Engine API** - Initializes agents (port 8006, takes 30-60s)
5. **User API** - Starts (port 8007)
6. **Dashboard** - Starts last (port 8888)

---

## Summary

### Real/Live Mode
- ✅ Uses Zerodha live market data
- ✅ Requires Zerodha credentials
- ✅ Full real-time trading capabilities
- ✅ Best for live trading and testing

### Historical Mode
- ✅ Uses historical data (Zerodha or CSV)
- ✅ Supports backtesting
- ✅ Works when market is closed
- ✅ All features available as in live mode

### Data Sources
- ✅ **Zerodha API** - Real and historical data (requires credentials)
- ✅ **CSV Files** - Historical data only (no credentials needed)

### Not Supported
- ❌ Synthetic data generation
- ❌ Mock data providers
- ❌ Simulated market data

---

**Ready to use!** 🚀

For more details, see:
- [README.md](README.md) - System overview
- [CREDENTIALS_TROUBLESHOOTING.md](CREDENTIALS_TROUBLESHOOTING.md) - Credentials setup
