# 🔍 TRADING DASHBOARD DEBUGGING CHECKLIST

## 🎯 CURRENT STATUS
- ✅ Dashboard loads without React errors
- ✅ Signal flow works (mock signals display)
- ❌ Market data not displaying (shows "—" everywhere)
- ❌ Technical indicators not showing data
- ❌ WebSocket connection status shows "Waiting"

---

## 🔍 DEBUGGING WORKFLOW

### 1. 🔍 WEBSOCKET CONNECTION VERIFICATION
**Status:** IN PROGRESS - Enhanced debugging added
**Issue:** Gateway shows 0 subscribers for market ticks
**Root Cause:** Frontend WebSocket not connecting to gateway

**Checklist:**
- [x] WebSocket URL configured: `ws://localhost:8889/ws`
- [x] WebSocketProvider wraps App component
- [x] useWebSocket hook initializes on mount
- [x] connect() function called automatically
- [x] Enhanced logging added to connection process
- [ ] Browser console shows "🔌 WebSocket connection OPENED successfully"
- [ ] Gateway logs show client connection
- [ ] Gateway subscribes to Redis channels (should show 1+ subscribers)

### 2. 🔄 MARKET DATA FLOW
**Status:** IN PROGRESS - Data not reaching UI
**Issue:** MarketOverviewWidget shows empty data

**Debug Steps:**
- [x] Add console logging to MarketOverviewWidget
- [x] Verify Redux state updates (currentTick, indicators)
- [x] Check if useMarketTick hook is called
- [ ] Verify WebSocket receives market tick messages
- [ ] Check tick data format matches TickData interface
- [ ] Test manual tick publishing

**Expected:**
```javascript
console.log('📊 MarketOverviewWidget Debug:', {
  currentTick: { instrument: 'BANKNIFTY', last_price: 60123.45, ... },
  indicators: { BANKNIFTY: { rsi_14: 65.2, ... } },
  hasTickData: true,
  hasIndicators: true
})
```

### 3. 📊 TECHNICAL INDICATORS DISPLAY
**Status:** PENDING
**Issue:** TechnicalIndicatorsWidget shows "Unable to load indicators"

**Debug Steps:**
- [ ] Check if indicators data exists in Redux
- [ ] Verify widget uses correct data path
- [ ] Test with manual indicator publishing
- [ ] Check if RTK Query is interfering

### 4. 🎨 UI LAYOUT OPTIMIZATION
**Status:** PENDING
**Issue:** Too many components, cluttered display

**Optimization Plan:**
- [ ] Identify 3-4 most essential widgets
- [ ] Remove placeholder/empty components
- [ ] Focus on: Signals, Market Data, Quick Actions
- [ ] Improve responsive layout

---

## 🛠️ DEBUGGING TOOLS ADDED

### Console Logging
```javascript
// MarketOverviewWidget
console.log('📊 MarketOverviewWidget Debug:', { currentTick, indicators, ... })

// WebSocket Hook
console.log('🔌 Connecting to WebSocket:', wsUrl)
console.log('📊 Processing tick update:', latestTick)
```

### Test Scripts
- `test_signal.py` - Publishes mock signals ✅
- `test_market_tick.py` - Publishes mock market ticks

### Data Verification
- Check Redux DevTools for state updates
- Verify WebSocket message format
- Confirm gateway forwarding

---

## 🔧 IMMEDIATE FIXES NEEDED

### 1. ✅ WebSocket Code Fixed
**Problem:** Duplicate variable declaration causing compilation error
**Status:** FIXED - Removed duplicate `const ws = new WebSocket()` declaration
**Result:** Frontend compiles successfully without errors

### 2. 🔍 WebSocket Connection
**Problem:** Gateway not receiving frontend connections
**Possible Causes:**
- CORS issues
- Wrong WebSocket endpoint
- Vite proxy configuration
- Firewall/network issues

**Test:** Check browser console for enhanced WebSocket logging

### 2. Market Data Publishing
**Problem:** No market tick data in Redis
**Possible Causes:**
- Historical replay finished
- Live market data not running
- Wrong data format

**Test:** Run `test_market_tick.py` and check if data appears in UI

### 3. Redux State Updates
**Problem:** Data received but not updating UI
**Possible Causes:**
- Wrong action dispatching
- State not updating
- Component not re-rendering

**Test:** Check Redux DevTools for state changes

---

## 🎯 NEXT STEPS

1. **Verify WebSocket Connection**
   - Check browser dev tools Network tab
   - Confirm gateway receives connections
   - Test with simple WebSocket client

2. **Test Market Data Flow**
   - Run `python test_market_tick.py`
   - Check console logs for data processing
   - Verify Redux state updates

3. **Fix Technical Indicators**
   - Ensure widget uses Redux data correctly
   - Test with manual indicator publishing

4. **Simplify UI**
   - Remove non-working components
   - Focus on core functionality
   - Improve layout

---

## 📊 EXPECTED WORKING STATE

**Dashboard should show:**
- ✅ Current Signal: Real signals from WebSocket
- ✅ Market Overview: Live BANKNIFTY price & indicators
- ✅ Technical Indicators: RSI, MACD, ADX values
- ✅ Risk Summary: Portfolio status
- ✅ Quick Actions: Functional buttons

**Console should show (with enhanced debugging):**
```
🔌 Connecting to WebSocket: ws://localhost:8889/ws
🔌 WebSocket instance created: WebSocket {url: "ws://localhost:8889/ws", ...}
🔌 WebSocket connection OPENED successfully
📊 WebSocket signal received: engine:signal:BANKNIFTY
📊 Processing tick update: { instrument: 'BANKNIFTY', last_price: 60123.45, ... }
📊 MarketOverviewWidget Debug: { hasTickData: true, hasIndicators: true, ... }
```

**If connection fails, will show:**
```
🔌 WebSocket ERROR: [error object]
🔌 WebSocket connection CLOSED: [code] [reason]
```

---

## 🚨 BLOCKERS

1. **WebSocket Connection:** Gateway not receiving frontend connections
2. **Market Data Publishing:** No live market data in Redis
3. **Data Format Mismatch:** Frontend expects different format than backend sends

---

## 🎯 SUCCESS CRITERIA

- [ ] WebSocket shows "Connected" status
- [ ] MarketOverviewWidget displays real BANKNIFTY price
- [ ] TechnicalIndicatorsWidget shows RSI/MACD values
- [ ] Dashboard loads in <2 seconds
- [ ] No console errors
- [ ] Real-time updates work