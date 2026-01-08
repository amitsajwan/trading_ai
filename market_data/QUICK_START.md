# Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Start Redis

```powershell
# Using Docker
docker-compose -f docker-compose.data.yml up -d redis

# Or use existing Redis instance
# Ensure Redis is running on localhost:6379
```

### Step 2: Choose Your Mode

**Option A: Live Mode (Real-time data)**
```powershell
python start_local.py --provider zerodha
```

**Option B: Historical Mode (Replay past data)**
```powershell
python start_local.py --provider historical --historical-source zerodha --historical-speed 10 --historical-from 2026-01-07
```

### Step 3: Verify It's Working

```powershell
# Check health
python -c "import requests; import json; r = requests.get('http://localhost:8004/health'); print(json.dumps(r.json(), indent=2))"

# Or use verification script
cd market_data
python verify_modes.py
```

---

## 📋 Mode Comparison

| Feature | Live Mode | Historical Mode |
|---------|-----------|----------------|
| **Command** | `--provider zerodha` | `--provider historical` |
| **Data Source** | Zerodha API (real-time) | Zerodha API or CSV (historical) |
| **Update Frequency** | Every 2-5 seconds | Configurable speed |
| **Virtual Time** | Disabled | Enabled |
| **Timestamps** | Current time (IST) | Historical time (IST) |
| **Use Case** | Live trading, real-time analysis | Backtesting, strategy testing |

---

## 🔧 Common Commands

### Live Mode
```powershell
# Start live data collection
python start_local.py --provider zerodha
```

### Historical Mode
```powershell
# Instant replay (for quick testing)
python start_local.py --provider historical --historical-source zerodha --historical-speed 0 --historical-from 2026-01-07

# Real-time speed replay
python start_local.py --provider historical --historical-source zerodha --historical-speed 1.0 --historical-from 2026-01-07

# Fast replay (10x speed)
python start_local.py --provider historical --historical-source zerodha --historical-speed 10 --historical-from 2026-01-07

# From CSV file (no credentials needed)
python start_local.py --provider historical --historical-source data/historical.csv --historical-speed 0
```

### Standalone API (Data Already in Redis)
```powershell
cd market_data
$env:PYTHONPATH = './src'; python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
```

---

## 🔄 Switching Modes

**From Live to Historical:**
1. Stop live collectors (Ctrl+C)
2. Start historical replay with desired date/speed
3. API continues running (no restart needed)

**From Historical to Live:**
1. Stop historical replay (Ctrl+C)
2. Clear virtual time: `python -c "import redis; r=redis.Redis(); r.delete('system:virtual_time:enabled'); r.delete('system:virtual_time:current')"`
3. Start live collectors
4. API continues running (no restart needed)

---

## ✅ Verification

**Automatic Verification:**
```powershell
cd market_data
python verify_modes.py
```

**Manual Verification:**
```powershell
# Health check
curl http://localhost:8004/health

# Latest tick
curl http://localhost:8004/api/v1/market/tick/BANKNIFTY

# Latest price
curl http://localhost:8004/api/v1/market/price/BANKNIFTY
```

---

## 📚 Next Steps

- **README.md** - Complete documentation
- **API_CONTRACT.md** - All API endpoints
- **HISTORICAL_SIMULATION_README.md** - Detailed historical replay guide
- **START_API.md** - API startup reference

---

## 🐛 Troubleshooting

**No data in API:**
- Check if collectors/replay are running
- Verify Redis has data: `redis-cli keys "tick:*"`
- Check credentials (for Zerodha data)

**API not starting:**
- Check port 8004 is free: `netstat -ano | findstr :8004`
- Verify Redis is running: `redis-cli ping`
- Check PYTHONPATH is set correctly

**Wrong mode detected:**
- Check virtual time status
- Verify data timestamps in Redis
- Ensure correct command arguments

