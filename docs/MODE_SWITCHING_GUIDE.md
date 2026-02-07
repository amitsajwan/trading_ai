# Mode Switching Guide

**Last Updated:** February 5, 2026

This guide explains how to work with LIVE and HISTORICAL execution modes in the trading system.

---

## Table of Contents

1. [Understanding Modes](#understanding-modes)
2. [How to Switch Modes](#how-to-switch-modes)
3. [Verifying Current Mode](#verifying-current-mode)
4. [Cleaning Mode Data](#cleaning-mode-data)
5. [Troubleshooting](#troubleshooting)
6. [Best Practices](#best-practices)

---

## Understanding Modes

### LIVE Mode
- **Purpose:** Real-time trading with current market data
- **Data Source:** Live Zerodha WebSocket feeds
- **Timestamps:** Current system time (IST)
- **Redis Keys:** Prefixed with `live:`
- **MongoDB:** Collections prefixed with `live_`
- **Visual Indicator:** 🔴 Green badge "[LIVE]"

**Use Cases:**
- Live trading
- Paper trading simulation
- Real-time market monitoring
- Production deployment

### HISTORICAL Mode
- **Purpose:** Backtesting with historical data
- **Data Source:** Historical CSV/database replay
- **Timestamps:** Virtual time (configurable historical date)
- **Redis Keys:** Prefixed with `historical:`
- **MongoDB:** Collections prefixed with `historical_`
- **Visual Indicator:** 🔵 Blue badge "[HISTORICAL (YYYY-MM-DD)]"

**Use Cases:**
- Strategy backtesting
- Historical analysis
- Algorithm development
- Performance simulation

### Key Differences

| Aspect | LIVE Mode | HISTORICAL Mode |
|--------|-----------|-----------------|
| Time Source | `datetime.now()` | `system:virtual_time:current` |
| Data Freshness | Real-time | Replayed from history |
| Redis Prefix | `live:` | `historical:` |
| Virtual Time | Disabled | Enabled |
| Trading | Real/Paper | Simulation only |

---

## How to Switch Modes

### Method 1: Docker Compose (Recommended)

#### Switch to LIVE Mode

```bash
# 1. Stop current services
docker-compose down

# 2. Set environment variable (optional - live is default)
export EXECUTION_MODE=live

# 3. Start services
docker-compose up -d

# 4. Verify logs
docker-compose logs -f market-data-api | grep "Mode validation"
```

#### Switch to HISTORICAL Mode

```bash
# 1. Stop current services
docker-compose down

# 2. Set environment variable
export EXECUTION_MODE=historical

# 3. Start with historical configuration
docker-compose -f docker-compose.yml -f docker-compose.historical.yml up -d

# 4. Start historical replay service
python market_data/src/market_data/adapters/historical_tick_replayer.py \
    --date 2026-01-15 \
    --instrument BANKNIFTY26FEBFUT \
    --speed 1

# 5. Verify virtual time is set
redis-cli GET system:virtual_time:enabled  # Should return "1"
redis-cli GET system:virtual_time:current  # Should return ISO timestamp
```

### Method 2: Direct Python Execution

```python
# In your Python code or startup script
import os
os.environ["EXECUTION_MODE"] = "live"  # or "historical"

# Then start your services
from market_data.api import build_store
store = build_store()
# Mode will be automatically detected
```

### Method 3: Environment File

Create a `.env` file in your project root:

```bash
# .env file
EXECUTION_MODE=live  # or historical
REDIS_HOST=localhost
REDIS_PORT=6379
```

Then load it:
```bash
docker-compose --env-file .env up -d
```

---

## Verifying Current Mode

### 1. Check UI Dashboard

- Open http://localhost:8008
- Look at the top-right corner
- **Green badge "LIVE"** = Live mode
- **Blue badge "HISTORICAL (date)"** = Historical mode

### 2. Check API Endpoint

```bash
# Using curl
curl http://localhost:8004/api/v1/system/mode

# Expected response:
{
  "mode": "live",
  "virtual_time_enabled": false,
  "virtual_time": null,
  "system_time": "2026-02-05T14:30:00+05:30",
  "effective_time": "2026-02-05T14:30:00+05:30",
  "redis_mode": "live"
}
```

### 3. Check Environment Variable

```bash
echo $EXECUTION_MODE
# Should output: live or historical
```

### 4. Check Redis

```bash
# Check execution mode
redis-cli GET system:execution_mode

# Check virtual time status
redis-cli GET system:virtual_time:enabled
redis-cli GET system:virtual_time:current

# Check for mode-prefixed keys
redis-cli KEYS "live:*" | head -5
redis-cli KEYS "historical:*" | head -5
```

### 5. Check Service Logs

```bash
# Docker
docker-compose logs market-data-api | grep -i "mode"

# Expected output:
# Market Data API: Mode validation: LIVE
# Market Data API: Redis client created: localhost:6379 (mode=LIVE)
```

---

## Cleaning Mode Data

### Clear Data for Specific Mode

Using Python:
```python
import redis
from redis_key_manager import clear_mode_data

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Clear historical data
clear_mode_data(redis_client, "historical")

# Clear live data (careful in production!)
clear_mode_data(redis_client, "live")
```

### Clear All Redis Data (Nuclear Option)

```bash
# WARNING: This deletes EVERYTHING in Redis!
redis-cli FLUSHDB

# Or more selective:
redis-cli --scan --pattern "historical:*" | xargs redis-cli DEL
redis-cli --scan --pattern "live:*" | xargs redis-cli DEL
```

### Clear MongoDB Collections

```python
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['trading_db']

# Drop historical collections
db.historical_signals.drop()
db.historical_trades.drop()
db.historical_positions.drop()

# Drop live collections (careful!)
# db.live_signals.drop()
# db.live_trades.drop()
# db.live_positions.drop()
```

---

## Troubleshooting

### Problem 1: Mode Mismatch Error

**Symptom:**
```
Mode mismatch: EXECUTION_MODE=live, Redis system:execution_mode=historical
```

**Solution:**
```bash
# Update Redis to match environment
redis-cli SET system:execution_mode live

# Or restart services to sync
docker-compose restart
```

### Problem 2: Virtual Time Enabled in Live Mode

**Symptom:**
```
CRITICAL: Virtual time is enabled but EXECUTION_MODE=live
```

**Solution:**
```bash
# Disable virtual time
redis-cli DEL system:virtual_time:enabled
redis-cli DEL system:virtual_time:current

# Restart services
docker-compose restart market-data-api
```

### Problem 3: No Data After Mode Switch

**Symptom:**
- UI shows no charts
- Empty options chain
- No indicators

**Possible Causes & Solutions:**

1. **Old mode data still cached:**
   ```bash
   # Clear cache and restart
   redis-cli FLUSHDB
   docker-compose restart
   ```

2. **Services not started in new mode:**
   ```bash
   # Check which services are running
   docker-compose ps
   
   # Restart with correct mode
   export EXECUTION_MODE=live
   docker-compose up -d
   ```

3. **Historical replay not started:**
   ```bash
   # For historical mode, start replay service
   python -m market_data.adapters.historical_tick_replayer \
       --date 2026-01-15 \
       --speed 1
   ```

### Problem 4: Stale Timestamp Warning

**Symptom:**
```
data_availability: stale_data_for_BANKNIFTY26FEBFUT_age_300s
```

**Solution:**
```bash
# Check if data publisher is running
docker-compose ps | grep publisher

# In live mode: Check WebSocket connection
docker-compose logs websocket-tick-collector

# In historical mode: Check replay service
docker-compose logs historical-replayer
```

### Problem 5: UI Badge Shows "Loading..." Forever

**Symptom:**
- Mode badge stuck on loading spinner

**Solution:**
1. **Check API is accessible:**
   ```bash
   curl http://localhost:8004/api/v1/system/mode
   ```

2. **Check browser console for errors:**
   - Open browser DevTools (F12)
   - Look for JavaScript errors
   - Check Network tab for failed requests

3. **Verify CORS settings:**
   ```bash
   # Check API logs for CORS errors
   docker-compose logs market-data-api | grep CORS
   ```

### Problem 6: Orphaned Keys from Other Mode

**Symptom:**
```
Found 1234 keys with 'historical:' prefix
```

**This is a WARNING, not an error.** Data from other modes won't interfere.

**To clean up (optional):**
```python
from redis_key_manager import clear_mode_data
import redis

r = redis.Redis()
clear_mode_data(r, "historical")  # Remove old historical data
```

---

## Best Practices

### 1. Always Verify Mode After Switch

```bash
# Quick verification checklist:
✓ Check UI badge color (green=live, blue=historical)
✓ curl http://localhost:8004/api/v1/system/mode
✓ redis-cli GET system:execution_mode
✓ Check logs for "Mode validation: PASSED"
```

### 2. Use Clear Naming for Historical Runs

```bash
# Set a run ID for historical backtests
redis-cli SET system:run_id "backtest_$(date +%Y%m%d_%H%M%S)"

# This helps identify data later
```

### 3. Never Mix Live and Historical Data

- **Don't** start historical replay while in live mode
- **Don't** switch modes without stopping services first
- **Do** use `clear_mode_data()` if unsure about data integrity

### 4. Document Your Mode Configuration

```bash
# Create a mode_config.txt for each deployment
echo "Mode: LIVE" > mode_config.txt
echo "Started: $(date)" >> mode_config.txt
echo "Purpose: Production trading" >> mode_config.txt
```

### 5. Use Docker Compose Profiles

Add to `docker-compose.yml`:
```yaml
services:
  historical-replayer:
    profiles: ["historical"]
    # ...
  
  live-tick-collector:
    profiles: ["live"]
    # ...
```

Then start with:
```bash
docker-compose --profile live up -d
docker-compose --profile historical up -d
```

### 6. Monitor Mode in Production

Set up alerts for:
- Mode mismatches (ENV vs Redis)
- Virtual time enabled in production
- Unexpected mode switches
- Stale data timestamps

### 7. Test Mode Switching in Staging

Before production deployment:
```bash
# Test complete cycle
1. Start in live mode → Verify
2. Switch to historical → Verify
3. Run backtest → Verify data separation
4. Switch back to live → Verify no contamination
5. Check both mode's data exists separately
```

---

## Quick Reference Commands

### Check Current State
```bash
# Mode
echo $EXECUTION_MODE
redis-cli GET system:execution_mode

# Virtual Time
redis-cli GET system:virtual_time:enabled
redis-cli GET system:virtual_time:current

# API Status
curl -s http://localhost:8004/api/v1/system/mode | jq .

# Data Keys
redis-cli DBSIZE
redis-cli KEYS "live:*" | wc -l
redis-cli KEYS "historical:*" | wc -l
```

### Quick Mode Switch
```bash
# To LIVE
export EXECUTION_MODE=live && docker-compose restart

# To HISTORICAL  
export EXECUTION_MODE=historical && docker-compose restart
```

### Emergency Reset
```bash
# Stop everything
docker-compose down

# Clear Redis
redis-cli FLUSHDB

# Clear virtual time
redis-cli DEL system:virtual_time:enabled
redis-cli DEL system:virtual_time:current

# Restart fresh
export EXECUTION_MODE=live
docker-compose up -d
```

---

## FAQ

**Q: Can I run both modes simultaneously?**  
A: Not recommended. While technically possible with separate Redis databases, it's error-prone. Use separate environments instead.

**Q: Will switching modes delete my data?**  
A: No. Data from each mode is isolated with prefixes. Historical data remains in `historical:*` keys when you switch to live mode.

**Q: How do I know which mode to use?**  
A: Use **LIVE** for real trading/monitoring. Use **HISTORICAL** for backtesting/development.

**Q: Can I change mode without restarting?**  
A: Not currently. Hot-swapping mode requires service restart to reload configuration and reinitialize Redis clients.

**Q: What happens if I forget to set EXECUTION_MODE?**  
A: Default is `live` mode. The system will log a warning if Redis has a different mode stored.

**Q: Is paper trading live or historical mode?**  
A: **LIVE mode** with `USE_MOCK_KITE=1`. You get real-time data but simulated trades.

---

## Support

If you encounter issues not covered here:

1. Check service logs: `docker-compose logs -f market-data-api`
2. Verify Redis keys: `redis-cli KEYS "*mode*"`
3. Test API endpoint: `curl http://localhost:8004/api/v1/system/mode`
4. Review startup logs for "Mode validation" messages

For critical issues, collect:
- Current mode: `echo $EXECUTION_MODE`
- Redis mode: `redis-cli GET system:execution_mode`
- Service logs: `docker-compose logs --tail=100 > logs.txt`
- API response: `curl http://localhost:8004/api/v1/system/mode > mode.json`

---

**Remember:** Mode isolation prevents data contamination. Always verify mode before running critical operations! 🛡️
