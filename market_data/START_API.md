# Starting the Market Data API

## 🚀 Quick Start

**From `market_data/` folder:**
```powershell
cd market_data
$env:PYTHONPATH = './src'; python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
```

**That's it!** The API will start on port 8004 and serve data from Redis.

---

## 📊 How It Works

The API service is **mode-agnostic**:
- Reads data from Redis (regardless of source)
- Same API code for both live and historical modes
- No restart needed when switching modes

**Data Flow:**
```
Live Collectors / Historical Replay → Redis → API Service → REST Endpoints
```

---

## 🔧 Environment Variables

**Optional:**
- `MARKET_DATA_API_PORT` (default: `8004`)
- `MARKET_DATA_API_HOST` (default: `0.0.0.0`)

**Required:**
- Redis must be running (default: `localhost:6379`)

---

## 📝 Complete Workflows

### Workflow 1: Historical Mode

**Step 1: Start Historical Replay (from project root)**
```powershell
python start_local.py --provider historical --historical-source zerodha --historical-speed 10 --historical-from 2026-01-07
```

**Step 2: Start API (from market_data/)**
```powershell
cd market_data
$env:PYTHONPATH = './src'; python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
```

**Result:** API serves historical data from Redis.

---

### Workflow 2: Live Mode

**Step 1: Start Live Collectors (from project root)**
```powershell
python start_local.py --provider zerodha
```

**Note:** This automatically starts the API service too, so Step 2 is optional.

**Step 2: Start API (if not auto-started)**
```powershell
cd market_data
$env:PYTHONPATH = './src'; python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
```

**Result:** API serves live data from Redis (updated every 2-5 seconds).

---

### Workflow 3: API Only (Data Already in Redis)

**Just start the API:**
```powershell
cd market_data
$env:PYTHONPATH = './src'; python -c "from market_data.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
```

**Result:** API serves whatever data is in Redis (from previous session).

---

## ✅ Verification

**After starting API, verify it's working:**
```powershell
# Health check
python -c "import requests; import json; r = requests.get('http://localhost:8004/health'); print(json.dumps(r.json(), indent=2))"

# Or use verification script
cd market_data
python verify_modes.py
```

---

## 🎯 Key Points

1. **API is Mode-Agnostic**: Same code works for live and historical
2. **Redis is the Bridge**: All data flows through Redis
3. **No Restart Needed**: Switch modes without restarting API
4. **Standalone Option**: Can run API independently if data exists in Redis

---

## 🐛 Troubleshooting

**Port 8004 already in use:**
```powershell
# Find and kill process
netstat -ano | findstr :8004
taskkill /PID <PID> /F
```

**API starts but no data:**
- Check Redis has data: `redis-cli keys "tick:*"`
- Verify collectors/replay are running
- Check Redis connection: `redis-cli ping`

**PYTHONPATH issues:**
- Always set `PYTHONPATH` to `./src` when running from `market_data/` folder
- Or use absolute path: `$env:PYTHONPATH = 'C:\code\zerodha\market_data\src'`

---

## 📚 Related Documentation

- **README.md** - Complete module documentation
- **QUICK_START.md** - 3-step quick start guide
- **API_CONTRACT.md** - All API endpoints
- **verify_modes.py** - Mode verification script
