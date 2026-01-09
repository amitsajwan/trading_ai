# Architecture Improvements Plan

## Issues Identified

### 1. Data Source: Redis vs API
**Current State:**
- React UI only uses REST APIs (axios calls to `/api/*` endpoints)
- All data goes through HTTP requests, even for frequently accessed data
- No direct Redis connection from UI (by design - browsers can't connect to Redis directly)

**Solution:**
- **Option A (Recommended)**: Add WebSocket server that reads from Redis pub/sub and pushes real-time data to clients
- **Option B**: Optimize existing APIs to read directly from Redis (they should already, but verify)
- **Option C**: Create lightweight Redis proxy API for high-frequency reads

### 2. WebSocket Implementation
**Current State:**
- React UI has `useWebSocket` hook but no backend WebSocket server
- `VITE_WS_URL` not configured
- No real-time updates - only polling

**Solution:**
- ~~Add Socket.IO server to Market Data API (port 8004) for tick updates~~ **DEPRECATED**
- ~~Add Socket.IO server to Engine API (port 8006) for signal/decision updates~~ **DEPRECATED**
- ✅ **NEW:** Redis WebSocket Gateway (port 8889) - direct Redis pub/sub to WebSocket forwarding
- Connect React UI to Redis WebSocket Gateway
- Gateway forwards events from Redis pub/sub to WebSocket clients

### 3. Trading Instruments: Futures & Options Focus
**Current State:**
- System defaults to spot BANKNIFTY trading
- Orchestrator analyzes BANKNIFTY (spot)
- Trade execution widget doesn't support Options

**Solution:**
- Update default instrument to BANKNIFTY Futures (nearest expiry)
- Update orchestrator to work with F&O instruments
- Enhance trade execution to support Options (strike, expiry, CE/PE)
- Support Options strategies (Iron Condor, Spreads, etc.)

### 4. Trade Execution: Options Support
**Current State:**
- TradeExecutionWidget only supports spot trades
- Missing Options fields (strike, expiry, option type)
- Backend `TradeExecutionRequest` already supports Options but UI doesn't use it

**Solution:**
- Add instrument type selector (Spot / Futures / Options / Strategy)
- Add Options fields: Strike, Expiry, Option Type (CE/PE)
- Load available expiries and strikes from Options Chain API
- Integrate with existing Options Chain widget data

## Implementation Status

### ✅ COMPLETED: Trade Execution Options Support
- ✅ Enhanced TradeExecutionWidget with Options fields (strike, expiry, CE/PE)
- ✅ Added Strategy support (Iron Condor, Spreads, Straddle, Strangle)
- ✅ Integrated with Options Chain API for expiries/strikes
- ✅ Defaults to FUTURES (not spot)
- ✅ Trade execution API supports Options fields

### ✅ COMPLETED: WebSocket Implementation (Migrated to Redis WebSocket Gateway)
- ✅ **DEPRECATED:** Socket.IO removed from Market Data API and Engine API
- ✅ **NEW:** Redis WebSocket Gateway (port 8889) - direct Redis pub/sub to WebSocket forwarding
- ✅ Gateway subscribes to all Redis channels (market:tick:*, engine:signal:*, engine:decision:*, indicators:*)
- ✅ Gateway is a dumb forwarder - no business logic, only forwards messages
- ✅ UI connects directly to gateway (ws://localhost:8889/ws)
- ✅ Real-time tick, signal, decision, and indicator updates via direct Redis connection
- ✅ Sequence IDs added to all messages for gap detection
- ✅ Authentication, ACL, and guardrails implemented

### ✅ COMPLETED: Redis Pub/Sub Architecture
- ✅ `store_tick` publishes to Redis pub/sub (market:tick:* channels)
- ✅ `save_signal` publishes to Redis pub/sub (engine:signal:* channels)
- ✅ Agent decisions published to Redis pub/sub (engine:decision:* channels)
- ✅ Technical indicators published to Redis pub/sub (indicators:* channels)
- ✅ Redis WebSocket Gateway subscribes to Redis pub/sub and forwards to UI
- ✅ APIs are for reference/fallback (Redis pub/sub is primary real-time source)

### ✅ COMPLETED: Futures & Options Focus
- ✅ Defaults updated to Futures (comments added)
- ✅ Orchestrator uses Futures (nearest expiry) as default
- ✅ Trade Execution Widget defaults to FUTURES
- ✅ System focuses on Futures & Options trading, not spot BANKNIFTY
