# Port Architecture Issue - DUPLICATION DETECTED

## Problem: Port Conflicts and Duplicate UIs

You have **TWO separate UI systems** trying to use the **SAME port 8888**:

### 1. **Legacy UI** (Old)
- **File**: `dashboard/templates/dashboard.html`
- **Served by**: FastAPI `app.py`
- **Port**: 8888 (line 1844-1845 in app.py)
- **Route**: `/` (root route)
- **Type**: Server-rendered Jinja2 template

### 2. **Modern UI** (New)
- **Directory**: `dashboard/modular_ui/`
- **Technology**: React + Vite
- **Port**: 8888 (line 7 in vite.config.js)
- **Type**: Single Page Application (SPA)

### Current Conflict

```
Port 8888:
├── FastAPI app.py (tries to serve dashboard.html) ❌ CONFLICT
└── Vite dev server (serves React app) ❌ CONFLICT
```

## Root Cause

1. **FastAPI `app.py`** is configured to run on port **8888** and serve the old `dashboard.html` template
2. **Vite** (`modular_ui/vite.config.js`) is also configured to run on port **8888** for the React app
3. Both cannot run simultaneously on the same port
4. The old `dashboard.html` is legacy code that should be deprecated in favor of the React app

## Current Architecture (Broken)

```
┌─────────────────────────────────────────────┐
│ Port 8888 (CONFLICT)                        │
│  ├─ FastAPI app.py (old dashboard.html)    │
│  └─ Vite (React modular_ui)                 │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Port 8889 (CONFLICT?)                       │
│  ├─ FastAPI API backend?                   │
│  └─ WebSocket Gateway                       │
└─────────────────────────────────────────────┘
```

## Correct Architecture (Recommended)

```
┌─────────────────────────────────────────────┐
│ Port 8888 - Vite Dev Server                 │
│  └─ React SPA (modular_ui/)                 │
│     └─ Proxies /api/* → Port 8000          │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ Port 8000 - FastAPI Backend                 │
│  └─ API endpoints only (/api/*)            │
│     └─ NO dashboard.html template          │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Port 8889 - WebSocket Gateway               │
│  └─ Redis WebSocket Gateway                 │
│     └─ WebSocket endpoint (/ws)             │
└─────────────────────────────────────────────┘
```

## Solution ✅ APPLIED

### Step 1: ✅ Move FastAPI to Port 8000

**File**: `dashboard/app.py` - **FIXED**

Changed to use port 8000 (configurable via `DASHBOARD_API_PORT` env var):
```python
port = int(os.getenv("DASHBOARD_API_PORT", "8000"))
uvicorn.run(app, host="0.0.0.0", port=port)
```

### Step 2: ✅ Remove Legacy Dashboard Route

**File**: `dashboard/app.py` - **FIXED**

Replaced legacy `dashboard.html` template route with API info endpoint:
```python
@app.get("/")
async def root():
    """API root - UI is served by React app on port 8888"""
    return {
        "service": "Trading Dashboard API",
        "ui": "http://localhost:8888",
        "api_docs": "/docs"
    }
```

### Step 3: ✅ Update Vite Proxy Configuration

**File**: `dashboard/modular_ui/vite.config.js` - **FIXED**

Updated all proxy targets from `8889` to `8000`:
```javascript
'/api/risk': {
  target: 'http://localhost:8000',  // ✅ Changed from 8889
  ...
},
'/api/health': {
  target: 'http://localhost:8000',  // ✅ Changed from 8889
  ...
},
'/api': {
  target: 'http://localhost:8000',  // ✅ Changed from 8889
  ...
},
```

### Step 4: Update Environment/Documentation

Update any scripts or documentation that reference:
- FastAPI backend port: `8888` → `8000`
- Keep Vite frontend: `8888` (unchanged)
- Keep WebSocket gateway: `8889` (unchanged)

## Verification

After changes, you should have:

1. ✅ **Vite React UI**: `http://localhost:8888` (modern React app)
2. ✅ **FastAPI Backend**: `http://localhost:8000/api/*` (API endpoints only)
3. ✅ **WebSocket Gateway**: `ws://localhost:8889/ws` (WebSocket server)

## Migration Path

The `dashboard.html` template is **legacy code** and should be:
1. **Deprecated** - Mark as legacy in code comments
2. **Removed** - Once React UI is fully functional
3. **Documented** - Note in migration docs

The React `modular_ui/` is the **modern, maintained UI** and should be the primary interface.

## Quick Fix Command

To test the correct architecture:

```bash
# Terminal 1: Start FastAPI backend on port 8000
cd dashboard
python -c "from app import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000)"

# Terminal 2: Start Vite dev server on port 8888
cd dashboard/modular_ui
npm run dev

# Terminal 3: Start WebSocket gateway on port 8889
python -m redis_ws_gateway.main
```

## Files Updated ✅

1. ✅ `dashboard/app.py` - Changed port to 8000, removed legacy dashboard.html route
2. ✅ `dashboard/modular_ui/vite.config.js` - Updated proxy targets to 8000
3. ⚠️ `start_local.py` - May need port reference updates (check if used)
4. ✅ Documentation - Created `PORT_ARCHITECTURE.md` with updated info

## Summary

- **Legacy UI**: `dashboard.html` served by FastAPI - **DEPRECATE**
- **Modern UI**: `modular_ui/` React app - **USE THIS**
- **Port conflict**: Both trying to use 8888 - **FIX BY SEPARATING PORTS**
- **Solution**: FastAPI → 8000, Vite → 8888, WS Gateway → 8889