# Historical Mode: Depth & Options Chain Handling

**Purpose:** Explain how **Market Depth** and **Options Chain** data work in **Historical Replay Mode** vs **Real-Time Live Mode**.

---

## 📊 Overview

**Important:** Both modes use **REAL Zerodha data**, not mock data!

- **Real-Time Mode:** Real-time data from Zerodha WebSocket/REST API
- **Historical Mode:** Real historical data from Zerodha Historical API

The `ZerodhaOptionsChainAdapter` uses **real Zerodha API** (`kite.quote()` or `kite.ltp()`) in both modes.

### Key Differences

| Feature | Real-Time (Live) | Historical Replay |
|---------|------------------|-------------------|
| **Market Depth** | ✅ Real data from `kite.quote()` (continuous) | ❌ Not available (uses synthetic fallback) |
| **Options Chain** | ✅ Real data from `kite.quote()` (real-time bid/ask) | ✅ Real data from `kite.ltp()` (last traded price) |
| **LTP/OHLC** | ✅ Real-time from Zerodha WebSocket/REST | ✅ Real historical from Zerodha `historical_data()` API |
| **Data Source** | Live Zerodha WebSocket/REST | Zerodha Historical API / CSV (real data) |
| **Update Frequency** | Continuous (every 2-5 seconds) | On-demand (API call) |

---

## 🔍 Market Depth in Historical Mode

### Real-Time (Live) Mode

**How it works:**
1. **`DepthCollector`** runs continuously (every 5 seconds)
2. Fetches market depth from Zerodha API: `kite.quote([symbol])`
3. Stores in Redis:
   ```redis
   depth:BANKNIFTY:buy → [{"price": 47500, "quantity": 100, "orders": 5}, ...]
   depth:BANKNIFTY:sell → [{"price": 47501, "quantity": 150, "orders": 8}, ...]
   depth:BANKNIFTY:timestamp → "2026-01-XX 15:30:00"
   ```

**Component:** `collectors/depth_collector.py`
```python
class DepthCollector:
    def collect_once(self):
        # Fetch quote with depth
        quote = self.kite.quote([f"{exchange}:{symbol}"])
        depth = quote['depth']
        
        # Store in Redis
        self.r.set(f"depth:{symbol}:buy", json.dumps(depth['buy']))
        self.r.set(f"depth:{symbol}:sell", json.dumps(depth['sell']))
```

**Key Points:**
- ✅ Continuously updated (every 5 seconds)
- ✅ Real-time bid/ask levels
- ✅ Only works during market hours
- ✅ Requires active market connection

---

### Historical Replay Mode

**How it works:**
1. **`DepthCollector` is NOT started** in historical mode
2. Historical replay only replays **OHLC tick data** (no depth data)
3. API endpoint provides **synthetic depth** fallback:
   ```python
   # If no depth data in Redis, generate synthetic depth from latest tick
   latest_tick = store.get_latest_tick(instrument)
   if latest_tick:
       depth_mid = latest_tick.last_price
       # Generate 5 levels of synthetic bid/ask around last price
       for level in range(1, 6):
           buy_depth.append({'price': depth_mid - level, 'quantity': base_qty * level})
           sell_depth.append({'price': depth_mid + level, 'quantity': base_qty * level})
   ```

**API Endpoint:** `GET /api/market/depth/{instrument}`
```python
async def get_market_depth(instrument: str):
    # 1. Try to read real depth from Redis
    buy_depth = redis_client.get(f"depth:{instrument}:buy")
    sell_depth = redis_client.get(f"depth:{instrument}:sell")
    
    # 2. If not found, generate synthetic depth from latest tick
    if not buy_depth or not sell_depth:
        latest_tick = store.get_latest_tick(instrument)
        if latest_tick:
            # Generate synthetic depth
            buy_depth, sell_depth = generate_synthetic_depth(latest_tick)
```

**Key Points:**
- ❌ **No real depth data** (historical OHLC doesn't include depth)
- ✅ **Synthetic depth** generated from latest tick price
- ✅ API endpoint still works (falls back to synthetic)
- ⚠️ **Less accurate** than real-time depth

**Why no real depth in historical mode?**
- Zerodha Historical API (`kite.historical_data()`) only provides **OHLC data**, not depth
- Historical depth data is not available from Zerodha API
- Historical replay focuses on **price movements** (ticks/OHLC), not order book

---

## 📈 Options Chain in Historical Mode

### Real-Time (Live) Mode

**How it works:**
1. Options Chain API endpoint calls `get_options_client()`
2. Detects **live mode** (checks `system:virtual_time:enabled` in Redis)
3. Creates `ZerodhaOptionsChainAdapter` with `use_live_quotes=True`
4. Uses `kite.quote()` API for **real-time bid/ask prices**:
   ```python
   # Live mode: use quote() for real-time bid/ask
   options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=True)
   
   # Fetches real-time data
   quote = kite.quote([f"NFO:{option_symbol}"])
   bid = quote['depth']['buy'][0]['price']  # Real-time bid
   ask = quote['depth']['sell'][0]['price']  # Real-time ask
   ```

**Component:** `api_service.py` → `get_options_client()`
```python
def get_options_client():
    # Detect mode
    virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
    is_live_mode = (virtual_time_enabled != "1")
    
    if is_live_mode:
        # Live mode: use quote() for real-time bid/ask
        options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=True)
    else:
        # Historical mode: use ltp() for last traded price
        options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=False)
```

**Key Points:**
- ✅ **Real-time bid/ask** from `kite.quote()`
- ✅ **Current prices** (updated continuously)
- ✅ Requires active market connection

---

### Historical Replay Mode

**How it works:**
1. Options Chain API endpoint calls `get_options_client()`
2. Detects **historical mode** (checks `system:virtual_time:enabled == "1"` in Redis)
3. Creates `ZerodhaOptionsChainAdapter` with `use_live_quotes=False`
4. Uses `kite.ltp()` API for **REAL last traded price**:
   ```python
   # Historical mode: use ltp() for REAL last traded price
   options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=False)
   
   # Fetches REAL last traded price from Zerodha (works after hours)
   ltp_dict = kite.ltp([f"NFO:{option_symbol}"])
   last_price = ltp_dict[f"NFO:{option_symbol}"]['last_price']  # Real last traded price from Zerodha
   ```
   
**Key Point:** This is **REAL Zerodha data** - `ZerodhaOptionsChainAdapter` uses the real Zerodha API.

**Component:** `api_service.py` → `get_options_client()`
```python
def get_options_client():
    # Check Redis for virtual time status
    virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
    
    if virtual_time_enabled == "1":
        # Historical mode detected
        print("Using Zerodha Options Chain (historical mode - ltp() API)")
        options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=False)
    else:
        # Live mode
        print("Using Zerodha Options Chain (LIVE mode - quote() API)")
        options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=True)
```

**Key Points:**
- ✅ **Last traded price** from `kite.ltp()` (works after hours)
- ⚠️ **No real-time bid/ask** (only last price available)
- ✅ Works in historical mode (doesn't require live market)
- ⚠️ **Less accurate** for current prices (shows last traded, not current bid/ask)

**Why different API in historical mode?**
- `kite.quote()` requires **active market** (returns empty during market closed)
- `kite.ltp()` works **anytime** (returns last traded price even after hours)
- Historical mode often runs when market is closed, so `ltp()` is more reliable

---

## 🔄 Enhanced Options Chain in Historical Mode

### IV and Greeks Calculation

**Both modes use the same calculation:**
- ✅ **IV Calculation**: Uses `GreeksCalculator.calculate_implied_volatility()`
- ✅ **Greeks Calculation**: Uses `GreeksCalculator.calculate_greeks()`

**Component:** `providers/enhanced_options_chain.py`
```python
class EnhancedOptionsChainAdapter(ZerodhaOptionsChainAdapter):
    def _calculate_implied_volatility(self, option_data, underlying_price, ...):
        # Uses GreeksCalculator (same for both modes)
        iv = self._greeks_calculator.calculate_implied_volatility(...)
        return iv
    
    def _calculate_greeks(self, option_data, underlying_price, ...):
        # Uses GreeksCalculator (same for both modes)
        greeks = self._greeks_calculator.calculate_greeks(...)
        return greeks
```

**Key Points:**
- ✅ **Same IV/Greeks calculation** in both modes
- ✅ Uses Black-Scholes model (independent of market mode)
- ✅ Requires valid option prices (last_price or ltp)

**Data Flow:**
```
Historical Mode:
Real Zerodha API (ltp) → EnhancedOptionsChainAdapter → IV/Greeks Calculation → API Response
     ↑
  REAL data (last traded price)

Live Mode:
Real Zerodha API (quote) → EnhancedOptionsChainAdapter → IV/Greeks Calculation → API Response
     ↑                                    ↑
  REAL data (bid/ask)            (SAME CALCULATION CODE)
```

---

## 📊 Comparison Table

| Aspect | Live Mode | Historical Mode |
|--------|-----------|-----------------|
| **Market Depth** | ✅ Real-time (every 5s) | ❌ Synthetic (from latest tick) |
| **Depth Collector** | ✅ Running (`DepthCollector`) | ❌ Not started |
| **Depth Data Source** | `kite.quote()` (real-time) | Synthetic generation |
| **Options Chain** | ✅ Real-time bid/ask | ✅ Last traded price |
| **Options API Used** | `kite.quote()` | `kite.ltp()` |
| **Options Mode Detection** | Checks `system:virtual_time:enabled` | Checks `system:virtual_time:enabled` |
| **IV Calculation** | ✅ Same (`GreeksCalculator`) | ✅ Same (`GreeksCalculator`) |
| **Greeks Calculation** | ✅ Same (`GreeksCalculator`) | ✅ Same (`GreeksCalculator`) |
| **Works After Hours** | ❌ No (requires active market) | ✅ Yes (uses last traded price) |

---

## 🔧 Implementation Details

### Depth Handling in API

**File:** `api_service.py`
```python
@app.get("/api/market/depth/{instrument}")
async def get_market_depth(instrument: str):
    # 1. Try Redis (real depth from live mode)
    buy_depth = redis_client.get(f"depth:{instrument}:buy")
    sell_depth = redis_client.get(f"depth:{instrument}:sell")
    
    # 2. Fallback to synthetic (for historical mode)
    if not buy_depth or not sell_depth:
        latest_tick = store.get_latest_tick(instrument)
        if latest_tick:
            # Generate synthetic depth
            depth_mid = latest_tick.last_price
            buy_depth = []
            sell_depth = []
            for level in range(1, 6):
                buy_depth.append({
                    'price': round(depth_mid - level, 2),
                    'quantity': (latest_tick.volume or 100) * level
                })
                sell_depth.append({
                    'price': round(depth_mid + level, 2),
                    'quantity': (latest_tick.volume or 100) * level
                })
```

**Key Points:**
- ✅ **Mode-agnostic API** (works for both modes)
- ✅ **Automatic fallback** to synthetic depth
- ⚠️ Historical mode depth is **less accurate** (synthetic)

---

### Options Chain Mode Detection

**File:** `api_service.py` → `get_options_client()`
```python
def get_options_client():
    # Detect mode by checking Redis virtual time
    try:
        redis_client = get_redis_client()
        virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
        
        if virtual_time_enabled == "1":
            # Historical mode: use ltp() (works after hours)
            is_live_mode = False
            options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=False)
        else:
            # Live mode: use quote() (real-time bid/ask)
            is_live_mode = True
            options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=True)
    except:
        # Fallback to env var check
        provider_name = os.getenv("TRADING_PROVIDER", "").lower()
        is_live_mode = (provider_name in ('zerodha', 'kite'))
```

**Key Points:**
- ✅ **Automatic mode detection** (checks Redis virtual time)
- ✅ **Falls back to env vars** if Redis check fails
- ✅ **Uses appropriate Zerodha API** based on mode

---

## 🎯 Summary

### Market Depth

**Live Mode:**
- ✅ Real-time depth collected continuously
- ✅ Accurate bid/ask levels
- ❌ Requires active market

**Historical Mode:**
- ❌ No real depth data (not available in historical API)
- ✅ Synthetic depth generated from latest tick
- ⚠️ Less accurate (estimated, not real)

---

### Options Chain

**Live Mode:**
- ✅ Real-time bid/ask from `kite.quote()`
- ✅ Current market prices
- ❌ Requires active market

**Historical Mode:**
- ✅ Last traded price from `kite.ltp()`
- ✅ Works after hours
- ⚠️ Not real-time (shows last price, not current bid/ask)

**Common (Both Modes):**
- ✅ **IV calculation** (same code)
- ✅ **Greeks calculation** (same code)
- ✅ Enhanced options chain adapter
- ✅ Same API endpoint

---

## 💡 Key Insights

1. **Both modes use REAL Zerodha data**: Not mock data! Both `quote()` and `ltp()` are real Zerodha APIs
2. **Historical mode uses real historical data**: OHLC data from `kite.historical_data()` is real historical data
3. **Depth is not historical**: Historical replay only provides OHLC tick data, not order book depth (so uses synthetic fallback)
4. **Options chain uses real data in both modes**: 
   - Live: Real-time bid/ask from `kite.quote()` (real Zerodha API)
   - Historical: Last traded price from `kite.ltp()` (real Zerodha API)
5. **Options chain adapts**: Automatically uses different Zerodha APIs based on mode (`quote()` vs `ltp()`)
6. **IV/Greeks work everywhere**: Calculations are independent of market mode (same code)
7. **`ZerodhaOptionsChainAdapter`**: Uses **real Zerodha API** in both modes

---

## 🔍 Future Improvements

### Potential Enhancements

1. **Historical Depth Storage**: If historical depth data becomes available, could store it in Redis during replay
2. **Better Synthetic Depth**: Improve synthetic depth generation using volume/volatility data
3. **Historical Options Chain**: Fetch historical options chain data and store it for replay

**Current Limitation:**
- Historical depth is not available (Zerodha Historical API doesn't provide order book depth)
- Options chain in historical mode uses last traded price (real Zerodha data) instead of real-time bid/ask
- Synthetic depth fallback is functional but less accurate than real depth

**Clarification:**
- Both modes use **REAL Zerodha data**, not mock data
- Historical mode uses real historical OHLC data from Zerodha
- Options chain in both modes uses real Zerodha API (`quote()` or `ltp()`)
- Only depth in historical mode is synthetic (because historical depth doesn't exist in Zerodha API)
