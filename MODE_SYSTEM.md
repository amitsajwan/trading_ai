# Live vs Historical Mode - System Architecture

> **Status:** Historical reference. For current runtime commands and source switching use `start_all.sh --help` and `market_data/README.md`.


## 🎯 Overview

The system operates in **two modes** that are **completely isolated** at the Redis layer:

- **LIVE**: Real-time market data from Zerodha WebSocket
- **HISTORICAL**: Test/replay data for development/backtesting

## 🔄 Mode Detection (Automatic)

```python
# From redis_key_manager.py
def get_execution_mode() -> str:
    """Auto-detect mode based on market hours"""
    
    # 1. Check environment variables (manual override)
    for var in ("EXECUTION_MODE", "TRADING_MODE", "ZERODHA_MODE", "MODE"):
        if mode := os.getenv(var):
            return mode  # live, historical, or paper
    
    # 2. Auto-detect based on IST market hours
    if market_is_open_ist():  # Mon-Fri, 09:15-15:30 IST
        return "live"
    else:
        return "historical"
```

**Current Status** (as of now):
- Time: 15:22 IST (3:22 PM)
- Market: CLOSED (closes at 15:30)
- Mode: `historical`

---

## 📊 LIVE Mode

### When It Activates
- **Auto**: Mon-Fri, 09:15-15:30 IST (Indian market hours)
- **Manual**: Set `MODE=live` in environment

### Data Source Options
**Choice 1**: Real Zerodha Kite WebSocket (when token available)  
**Choice 2**: Mock Kite WebSocket (for development/testing)

**Both use IDENTICAL event-driven flow:**
```
Data Source (Real Kite WebSocket OR Mock WebSocket)
    ↓
WebSocketTickCollector → EventEngine (EVENT_TICK)
    ↓
BarGenerator (subscribes to EVENT_TICK) → builds 1min/5min/15min/1h bars
    ↓
EventEngine (EVENT_BAR_1M, 5M, 15M, 1H) → RealTimeIndicatorHandler
    ↓
Redis: live:ohlc_sorted:BANKNIFTY26FEBFUT:5min
      live:indicators:BANKNIFTY26FEBFUT:5min
```

**Entry Point:**
```bash
# Run with Mock WebSocket (no credentials needed)
python simple_runner.py --websocket mock

# Run with Real WebSocket (requires credentials)
python simple_runner.py --websocket real
```

### Redis Key Pattern
```
live:ohlc_sorted:{instrument}:{timeframe}
live:price:{instrument}
live:tick:{instrument}
live:depth:{instrument}
```

### Characteristics
✅ **Swappable**: Real or Mock WebSocket - same code  
✅ **Production-ready**: Mock perfectly matches real structure  
✅ **Drop-in replacement**: Just swap data source, everything else identical  
⚠️ **Currently**: Using Mock WebSocket (market closed, no real token)  
⚠️ **Future**: Replace with real Kite WebSocket - zero code changes needed

---

## 🧪 HISTORICAL Mode

### When It Activates
- **Auto**: Outside market hours (Mon-Fri after 15:30, weekends)
- **Manual**: Set `MODE=historical` in environment

### Data Source Options
**Choice 1**: Mock WebSocket (synthetic ticks)  
**Choice 2**: Historical replay (past real data)  
**Choice 3**: Static injection (pre-generated OHLC)

**All use IDENTICAL event-driven flow (same as LIVE!):**
```
Data Source (Mock WebSocket OR Replay OR Static)
    ↓
WebSocketTickCollector → EventEngine (EVENT_TICK)
    ↓
BarGenerator (subscribes to EVENT_TICK) → builds 1min/5min/15min/1h bars
    ↓
EventEngine (EVENT_BAR_1M, 5M, 15M, 1H) → RealTimeIndicatorHandler
    ↓
Redis: historical:ohlc_sorted:BANKNIFTY26FEBFUT:5min
      historical:indicators:BANKNIFTY26FEBFUT:5min
```

**Only difference from LIVE: Redis prefix changes from `live:` to `historical:`**

### Redis Key Pattern
```
historical:ohlc_sorted:{instrument}:{timeframe}
historical:price:{instrument}
historical:tick:{instrument}
historical:depth:{instrument}
```

### Characteristics
✅ **Safe**: No real money, no live trading  
✅ **Predictable**: Static/replay data, reproducible  
✅ **No Auth**: Doesn't require live Kite connection  
✅ **Fast**: Can speed up/slow down time  
⚠️ **Test Data**: Not real current prices

---

## 🔑 Key Differences

| Aspect | LIVE | HISTORICAL |
|--------|------|------------|
| **Redis Prefix** | `live:*` | `historical:*` |
| **Upstream Source** | Real/Mock Kite WebSocket | Mock WebSocket/Replay/Static |
| **When Active** | Market hours (09:15-15:30 IST) | Outside market hours |
| **Authentication** | Optional (real needs token) | Not needed |
| **Use Case** | Trading/monitoring | Testing/development/backtest |

**CRITICAL**: Everything after the data source is **IDENTICAL CODE**:
- Same WebSocketTickCollector → EventEngine
- Same BarGenerator logic (event-driven)
- Same RealTimeIndicatorHandler (subscribes to bar events)
- Same Redis storage format
- Same API endpoints
- Same Dashboard code

**Only 2 things change**: 
1. **Upstream**: Which data source you plug in (Real/Mock WebSocket)
2. **Redis prefix**: `live:` or `historical:`

**That's it!** The entire event-driven pipeline is reusable.

---

## 🏗️ System Architecture (Swappable Upstream)

**Key Design: Only upstream changes, everything else is IDENTICAL**

```
┌─────────────────────────────────────────────────────────────┐
│  UPSTREAM (Swappable based on mode)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LIVE MODE:                                                  │
│    Real Kite WebSocket OR Mock WebSocket                    │
│         ↓                                                    │
│    Writes to: Redis live:*                                   │
│                                                              │
│  HISTORICAL MODE:                                            │
│    Mock WebSocket OR Replay OR Static                       │
│         ↓                                                    │
│    Writes to: Redis historical:*                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
              Redis: {mode}:ohlc_sorted:*
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  DOWNSTREAM (100% IDENTICAL CODE - Mode Agnostic)           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  redis_key_manager.py (auto-prefixes keys)                  │
│    ↓                                                         │
│  API (port 8004) - reads {mode}:* keys                      │
│    ↓                                                         │
│  Dashboard (port 8000) - displays data                      │
│    ↓                                                         │
│  Browser/UI - charts & visualization                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**The Event-Driven Pipeline (IDENTICAL for both modes):**
```
WebSocket (Mock/Real) → WebSocketTickCollector → EventEngine 
    ↓                                                   ↑
EVENT_TICK                                      AUTO-PREFIXED
    ↓                                           (live:/historical:)
BarGenerator (subscribes) → EVENT_BAR_* → RealTimeIndicatorHandler
    ↓                                              ↓
Redis (OHLC + Indicators) → API → UI         Indicators
     ↑
PLUGGABLE
(Real/Mock)
```

**Key Components:**
- **EventEngine**: VN.py-inspired message bus for event-driven architecture
- **BarGenerator**: Tick→OHLC aggregation (1min, 5min, 15min, 1h)
- **RealTimeIndicatorHandler**: Subscribes to bar events, calculates indicators
- **simple_runner.py**: Entry point to start pipeline with Mock/Real WebSocket

---

## � Drop-in Replacement Pattern

**How to swap Real ↔ Mock WebSocket with ZERO code changes:**

```python
# Option 1: Real Zerodha Kite WebSocket (when available)
kite_ws = KiteWebSocket(api_key, access_token)
kite_ws.on_ticks = tick_handler  # ← Same handler!
kite_ws.connect()

# Option 2: Mock WebSocket (for testing/after-hours)
mock_ws = MockKiteWebSocket()
mock_ws.on_ticks = tick_handler  # ← Same handler!
mock_ws.connect()
```

**Critical Requirements:**
1. **Identical Tick Format**: Mock MUST emit same format as Real Kite WebSocket
   ```python
   {
       'instrument_token': 256265,
       'last_price': 45000.0,
       'volume': 12345,
       'timestamp': datetime(2025, 1, 28, 10, 30, 0)
   }
   ```

2. **Same Handler**: Both call identical `tick_handler` function
3. **Mode-Agnostic Code**: Handler writes to auto-prefixed keys (doesn't know about modes)

**What changes when swapping:**
- Which WebSocket class you instantiate
- **That's it!**

**What stays identical (100% same code):**
- Tick handler (`handle_ticks()`)
- OHLC aggregator (`aggregate_to_ohlc()`)
- Redis storage (`store_ohlc()`)
- API endpoints (`GET /api/v1/market/ohlc`)
- Dashboard code
- UI components

**Testing Example:**
```python
# During market hours (with real connection)
ws = KiteWebSocket(api_key, token)
ws.on_ticks = handle_ticks  # Writes to live:*
ws.connect()

# After hours (testing)
ws = MockKiteWebSocket()
ws.on_ticks = handle_ticks  # Writes to historical:*
ws.connect()

# ↑ Only line 1 changed! Everything else identical.
```

---

## �🔄 Mode Switching

### Automatic (Recommended)
System automatically switches based on time:
```bash
# 09:15 IST - Market opens
Mode: historical → live
Keys: historical:* → live:*

# 15:30 IST - Market closes  
Mode: live → historical
Keys: live:* → historical:*
```

### Manual Override
```bash
# Force historical mode (for testing during market hours)
$env:MODE="historical"
python market_data/start_api.py

# Force live mode (for late-night testing with old data)
$env:MODE="live"
python market_data/start_api.py
```

---

## 💾 Data Isolation

**Critical**: Live and historical data **NEVER mix**

```redis
# Redis database at any point in time:

# Live data (from today's market session)
live:ohlc_sorted:BANKNIFTY26FEBFUT:5min → [100 bars from 09:15-15:30]
live:price:BANKNIFTY26FEBFUT → 51234.50

# Historical data (test/replay data)  
historical:ohlc_sorted:BANKNIFTY26FEBFUT:5min → [100 synthetic bars]
historical:price:BANKNIFTY26FEBFUT → 53163.99

# ✅ Both exist simultaneously, never conflict
# ✅ System reads from correct prefix based on mode
# ✅ No cross-contamination possible
```

---

## 🧪 Testing Both Modes

### Test Historical Mode (Now)
```powershell
# Check current data
docker exec zerodha-redis redis-cli ZRANGE "historical:ohlc_sorted:BANKNIFTY26FEBFUT:5min" 0 0

# Result: {"start_at": 1770424521, "open": 53441.04, ...}
```

### Test Live Mode (During Market Hours)
```powershell
# Tomorrow at 10:00 AM IST
docker exec zerodha-redis redis-cli ZRANGE "live:ohlc_sorted:BANKNIFTY26FEBFUT:5min" 0 0

# Result: Mock WebSocket data (same structure as real Zerodha)
```

---

## 🎯 Current System Status

```
Mode: historical (auto-detected, market closed)
API: http://localhost:8004 (serving historical data)
UI: test_dashboard.html (showing historical bars)

Redis Keys:
  historical:* → 5 keys (active, being read)
  live:* → 6 keys (dormant, from earlier session)
```

**When market opens tomorrow (09:15 IST)**:
1. Mode auto-switches to `live`
2. System starts reading `live:*` keys
3. Mock WebSocket generates data (currently)
4. Mock market data flows in
5. Dashboard shows simulated prices

**No code changes needed!**

**Note**: To connect to real Zerodha WebSocket:
1. Add valid Kite access token to config
2. Enable real WebSocket in market_data runner
3. Architecture remains identical

---

## 📝 Summary

**LIVE Mode**:
- Mock WebSocket data (currently)
- During market hours (09:15-15:30 IST)
- No authentication needed (mock mode)
- Keys: `live:*`

**HISTORICAL Mode**:
- Test/replay data  
- Outside market hours (or forced)
- No authentication needed
- Keys: `historical:*`

**Everything else**: Identical code, same API, same UI, same logic.

**Fail-Fast**: System validates mode is valid, keys are always prefixed, no silent fallbacks.

**Future**: Replace mock WebSocket with real Zerodha connection by adding Kite token.
