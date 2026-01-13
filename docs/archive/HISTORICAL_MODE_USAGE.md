# Historical Mode Usage - start_local.py ✅

## Overview

`start_local.py` **does support historical mode with date parameters** for when the market is down or for backtesting. All the signal lifecycle features work with historical mode!

---

## Quick Start - Historical Mode

### Basic Usage (with date):
```bash
python start_local.py --provider historical --historical-from 2026-01-08
```

### With Zerodha Historical Data:
```bash
python start_local.py --provider historical --historical-source zerodha --historical-from 2026-01-08
```

### With CSV File:
```bash
python start_local.py --provider historical --historical-source path/to/data.csv --historical-from 2026-01-08
```

---

## Command Line Arguments

### Historical Mode Options:

1. **`--provider historical`** or **`--provider replay`**
   - Enables historical mode
   - Uses historical data instead of live market data
   - Works with signal lifecycle system

2. **`--historical-from YYYY-MM-DD`** ⭐ **DATE PARAMETER**
   - Start date for historical replay
   - Format: `YYYY-MM-DD` (e.g., `2026-01-08`)
   - Example: `--historical-from 2026-01-08`

3. **`--historical-source zerodha|path/to/file.csv`**
   - Data source for historical data
   - `zerodha`: Use Zerodha API historical data (requires credentials)
   - `path/to/file.csv`: Use CSV file with historical data
   - Default: Zerodha (if credentials available)

4. **`--historical-speed FLOAT`**
   - Playback speed multiplier
   - `1.0` = real-time
   - `2.0` = 2x speed
   - `0.5` = half speed
   - Default: `1.0`

5. **`--historical-ticks`**
   - Use tick-level replayer instead of bar-level
   - More detailed but slower
   - Optional flag

6. **`--allow-missing-credentials`**
   - Allow startup without Zerodha credentials
   - **Required** for CSV-based historical runs
   - Optional for Zerodha (will prompt for credentials if missing)

7. **`--skip-validation`**
   - Skip health checks
   - Faster startup for testing
   - Optional flag

---

## Complete Examples

### Example 1: Zerodha Historical (Today's Date)
```bash
python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-08
```

### Example 2: Zerodha Historical (Custom Speed)
```bash
python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-08 \
  --historical-speed 2.0
```

### Example 3: CSV File Historical
```bash
python start_local.py \
  --provider historical \
  --historical-source ./data/historical_data.csv \
  --historical-from 2026-01-08 \
  --allow-missing-credentials
```

### Example 4: Tick-Level Historical (Most Detailed)
```bash
python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-08 \
  --historical-ticks \
  --historical-speed 1.0
```

---

## How It Works with Signal Lifecycle

### Historical Mode + Signal Lifecycle Flow:

```
1. Historical Data Replay Starts
   ↓
2. Market Data Service receives historical ticks
   ↓
3. Redis stores historical tick data
   ↓
4. Redis Tick Subscriber processes historical ticks
   ↓
5. SignalMonitor checks conditions on each tick
   ↓
6. Signals trigger when conditions met (in historical time)
   ↓
7. Trades execute (simulated)
   ↓
8. UI shows signals and trades in real-time (replay speed)
```

### ✅ Signal Lifecycle Features Work:
- ✅ Orchestrator cycles run on historical data
- ✅ Signals are created from historical analysis
- ✅ Conditions are checked against historical ticks
- ✅ Trades execute (simulated) when conditions met
- ✅ UI shows signals and trades in real-time
- ✅ All monitoring and execution works

---

## What Happens During Startup

### Step 1: Historical Data Source
```
📈 Step 1: Historical Data Source
   🚀 Starting market-data runner in historical mode...
   📅 Starting from date: 2026-01-08
   ✅ Started HistoricalDataReplay (source=zerodha, speed=1.0, date=2026-01-08)
   ✅ Historical data verified
```

### Step 4: Engine API
```
🤖 Step 4: Engine API
   ✅ SignalMonitor initialized
   ✅ Redis tick subscriber started for real-time signal monitoring
   ✅ Orchestrator initialized successfully with signal monitoring support
```

### Step 5: Dashboard
```
🖥️  Step 5: Dashboard UI
   ✅ Dashboard UI healthy
```

---

## Environment Variables Alternative

You can also use environment variables instead of command-line arguments:

```bash
export TRADING_PROVIDER=historical
export HISTORICAL_SOURCE=zerodha
export HISTORICAL_FROM=2026-01-08
export HISTORICAL_SPEED=1.0
export HISTORICAL_TICKS=0

python start_local.py
```

---

## Verification

After starting with historical mode, verify:

1. **Historical Data**:
   ```bash
   curl http://localhost:8004/api/v1/market/tick/BANKNIFTY
   # Should return historical tick data
   ```

2. **Signal Monitoring**:
   - Check Engine API logs for "Redis tick subscriber started"
   - Historical ticks should trigger signal checks

3. **UI**:
   - Open: `http://localhost:8888/trading`
   - Signals should appear as historical data is replayed
   - Trades execute when conditions are met (in historical time)

---

## Troubleshooting

### Issue: "No historical data available"
**Solution**:
- Check date is valid: `YYYY-MM-DD` format
- Verify Zerodha credentials if using `--historical-source zerodha`
- Check if data exists for that date

### Issue: "Invalid date format"
**Solution**:
- Use format: `YYYY-MM-DD`
- Example: `2026-01-08` not `01-08-2026` or `08/01/2026`

### Issue: "Zerodha credentials required"
**Solution**:
- Use `--allow-missing-credentials` with CSV source
- Or provide Zerodha credentials
- Or use CSV file: `--historical-source path/to/data.csv`

### Issue: Historical ticks not triggering signals
**Solution**:
- Check Redis tick subscriber is running (Engine API logs)
- Verify tick data is being published to Redis
- Check SignalMonitor has active signals

---

## Quick Reference

```bash
# Most Common Use Case (Zerodha Historical)
python start_local.py --provider historical --historical-from 2026-01-08

# CSV Historical (No Credentials Needed)
python start_local.py --provider historical --historical-source ./data.csv --historical-from 2026-01-08 --allow-missing-credentials

# Fast Replay (2x Speed)
python start_local.py --provider historical --historical-from 2026-01-08 --historical-speed 2.0

# Skip Validation (Faster Startup)
python start_local.py --provider historical --historical-from 2026-01-08 --skip-validation
```

---

## Summary

✅ **Historical mode is fully supported**  
✅ **Date parameter works**: `--historical-from YYYY-MM-DD`  
✅ **Signal lifecycle works with historical data**  
✅ **All features available in historical mode**  
✅ **Perfect for testing when market is down**  

**Ready to use!** 🚀
