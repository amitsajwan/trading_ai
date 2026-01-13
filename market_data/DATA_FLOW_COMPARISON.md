# Historical vs Real-Time Data Flow Comparison

**Purpose:** Compare how market data is created in **Historical Replay Mode** vs **Real-Time Live Mode**.

---

## 📊 Overview

**Important:** Both modes use **REAL Zerodha data**, not mock data!

- **Real-Time Mode:** Real-time data from Zerodha WebSocket/REST API
- **Historical Mode:** Real historical data from Zerodha Historical API (`kite.historical_data()`)

Both modes use the **same data flow architecture** but populate data differently:

```
┌─────────────────────────────────────────────────────────┐
│           DATA SOURCE (REAL Zerodha Data)               │
├─────────────────────────────────────────────────────────┤
│  Historical: Zerodha Historical API/CSV → Replayer     │
│              (REAL historical OHLC data)                │
│  Real-Time:  Zerodha WebSocket/REST → LTPCollector    │
│              (REAL real-time prices)                    │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│           MarketTick (Same Structure)                   │
│  {instrument, timestamp, last_price, volume}            │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│           RedisMarketStore (Same Code)                  │
│  - store_tick()                                         │
│  - Automatic candle building                            │
│  - Technical indicators update                          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Redis Storage (Same Keys)                  │
│  - tick:{instrument}:{timestamp}                        │
│  - tick:{instrument}:latest                             │
│  - price:{instrument}:latest                            │
│  - ohlc:{instrument}:{timeframe}:{timestamp}            │
│  - indicators:{instrument}:{timeframe}:*                │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│           Market Data API (Same Code)                   │
│  Reads from Redis, mode-agnostic                        │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 Mode 1: Real-Time (Live) Data Flow

### Data Source
- **Zerodha WebSocket** or **REST API polling** (REAL Zerodha data)
- Real-time market prices during market hours
- Uses current system time
- **Not mock data** - all data comes from real Zerodha API

### Components

#### 1. **LTPDataCollector** (`collectors/ltp_collector.py`)
```python
class LTPDataCollector:
    """Real-time LTP collector for Zerodha"""
    
    def collect_once(self):
        # 1. Fetch current quote from Zerodha
        quote = self.kite.quote([f"{exchange}:{symbol}"])
        price = quote['last_price']
        
        # 2. Create MarketTick with CURRENT time
        tick = MarketTick(
            instrument="BANKNIFTY",
            timestamp=datetime.now(),  # Current time
            last_price=price,
            volume=quote.get('volume')
        )
        
        # 3. Store in RedisMarketStore
        self.market_memory.store_tick(tick)
        
    def run_forever(self, interval_seconds=2.0):
        while True:
            self.collect_once()
            time.sleep(2.0)  # Poll every 2 seconds
```

**Key Characteristics:**
- ✅ **Timestamp:** Current system time (`datetime.now()`)
- ✅ **Update Frequency:** Every 2 seconds (configurable)
- ✅ **Data Freshness:** < 5 seconds lag
- ✅ **Virtual Time:** **DISABLED**
- ✅ **Running:** Continuous loop (runs forever)
- ✅ **Time Control:** Real-time (no speed control)

### Data Flow Steps

```
1. Zerodha WebSocket/REST API
   ↓
2. LTPDataCollector.collect_once()
   ↓
3. Fetch quote → Extract price/volume
   ↓
4. Create MarketTick(timestamp=datetime.now())
   ↓
5. RedisMarketStore.store_tick(tick)
   ↓
6. RedisMarketStore automatically:
   - Stores tick in Redis
   - Builds OHLC candles (via CandleBuilder)
   - Updates technical indicators (via TechnicalIndicatorsService)
   ↓
7. Data available in Redis:
   - tick:BANKNIFTY:{timestamp}
   - tick:BANKNIFTY:latest
   - price:BANKNIFTY:latest
   - ohlc:BANKNIFTY:1min:{timestamp}
   - indicators:BANKNIFTY:1min:*
```

### Redis Keys Created
```redis
# Latest tick
tick:BANKNIFTY:latest → {"instrument": "BANKNIFTY", "timestamp": "2026-01-XX 15:30:00", "last_price": 47500.0}

# Price (quick lookup)
price:BANKNIFTY:latest → "47500.0"
price:BANKNIFTY:latest_ts → "2026-01-XX 15:30:00"

# OHLC candles (auto-built from ticks)
ohlc_sorted:BANKNIFTY:1min → [sorted set of OHLC bars]

# Technical indicators (auto-updated)
indicators:BANKNIFTY:1min:rsi_14 → "65.5"
indicators:BANKNIFTY:1min:macd_value → "12.3"
```

---

## 📜 Mode 2: Historical Replay Data Flow

### Data Source
- **Zerodha Historical API** (`kite.historical_data()`) - **REAL historical data** OR
- **CSV file** (local historical data - typically real data exported)
- Past market prices with original timestamps
- **Not mock data** - historical data is real Zerodha historical OHLC data

### Components

#### 1. **HistoricalTickReplayer** (`adapters/historical_tick_replayer.py`)
```python
class HistoricalTickReplayer(MarketIngestion):
    """Replay historical ticks in the same order as live data"""
    
    async def _replay_loop(self):
        # 1. Load historical ticks from source
        ticks = self._load_ticks()  # From Zerodha API or CSV
        
        # 2. Replay ticks in chronological order
        for tick in ticks:
            # Option A: Rebase mode (shift ticks to "now")
            if self.rebase:
                tick.original_timestamp = tick.timestamp
                tick.timestamp = tick.timestamp + rebase_offset
            
            # Option B: Virtual time mode (set system virtual time)
            else:
                _set_system_virtual_time(tick.timestamp)  # Set Redis virtual time
            
            # 3. Store tick (same as live mode)
            self.store.store_tick(tick)
            
            # 4. Sleep to simulate real-time speed
            if self.speed > 0:
                await asyncio.sleep(sleep_duration)
            # speed=0.0 means instant replay (no sleep)
```

**Key Characteristics:**
- ✅ **Timestamp:** Original historical timestamp (or rebased)
- ✅ **Update Frequency:** Based on `speed` parameter
  - `speed=0.0`: Instant (all ticks immediately)
  - `speed=1.0`: Real-time speed (same as live)
  - `speed=10`: 10x faster than real-time
- ✅ **Data Freshness:** Historical (past data)
- ✅ **Virtual Time:** **ENABLED** (via Redis key `system:virtual_time:current`)
- ✅ **Running:** One-time replay (stops when data exhausted)
- ✅ **Time Control:** Configurable speed (0.0 to N)

### Data Flow Steps

```
1. Zerodha Historical API / CSV File
   ↓
2. HistoricalTickReplayer._load_ticks()
   - Fetches historical OHLC data (1-minute bars)
   - Converts OHLC bars to ticks (one tick per bar)
   - Preserves original timestamps
   ↓
3. HistoricalTickReplayer._replay_loop()
   - Iterates through ticks in chronological order
   - Sets virtual time (Redis key: system:virtual_time:current)
   - Creates MarketTick(timestamp=historical_time)
   ↓
4. RedisMarketStore.store_tick(tick)
   ↓
5. RedisMarketStore automatically:
   - Stores tick in Redis (SAME code as live mode)
   - Builds OHLC candles (via CandleBuilder)
   - Updates technical indicators (via TechnicalIndicatorsService)
   ↓
6. Data available in Redis (SAME keys as live mode):
   - tick:BANKNIFTY:{timestamp}
   - tick:BANKNIFTY:latest
   - price:BANKNIFTY:latest
   - ohlc:BANKNIFTY:1min:{timestamp}
   - indicators:BANKNIFTY:1min:*
```

### Historical Data Loading

#### From Zerodha API:
```python
def _load_from_zerodha(self):
    # Fetch historical OHLC data
    data = self.kite.historical_data(
        instrument_token=token,
        from_date=from_date,
        to_date=to_date,
        interval="minute",  # 1-minute bars
        oi=True
    )
    
    # Convert OHLC bars to ticks (one tick per bar)
    ticks = []
    for bar in data:
        tick = MarketTick(
            instrument=self.instrument_symbol,
            timestamp=bar['date'],  # Original timestamp
            last_price=bar['close'],
            volume=bar.get('volume', 0)
        )
        ticks.append(tick)
    
    return ticks
```

#### From CSV:
```python
def _load_from_csv(self):
    # CSV format: Date,Time,Open,High,Low,Close,Volume
    ticks = []
    with open(csv_path, 'r') as f:
        for row in csv.DictReader(f):
            timestamp = datetime.combine(row['Date'], row['Time'])
            tick = MarketTick(
                instrument=self.instrument_symbol,
                timestamp=timestamp,
                last_price=float(row['Close']),
                volume=int(row['Volume'])
            )
            ticks.append(tick)
    return ticks
```

### Redis Keys Created (Same as Live Mode)
```redis
# Latest tick (updates as replay progresses)
tick:BANKNIFTY:latest → {"instrument": "BANKNIFTY", "timestamp": "2025-01-15 15:30:00", "last_price": 47500.0}

# Virtual time (system-wide)
system:virtual_time:enabled → "1"
system:virtual_time:current → "2025-01-15 15:30:00"

# OHLC candles (auto-built, same as live)
ohlc_sorted:BANKNIFTY:1min → [sorted set of OHLC bars]

# Technical indicators (auto-updated, same as live)
indicators:BANKNIFTY:1min:rsi_14 → "65.5"
```

---

## 🔍 Key Differences

| Aspect | Real-Time (Live) | Historical Replay |
|--------|------------------|-------------------|
| **Data Source** | Zerodha WebSocket/REST API | Zerodha Historical API / CSV |
| **Timestamp** | `datetime.now()` (current time) | Original historical timestamp |
| **Update Frequency** | Fixed (2 seconds) | Configurable (`speed` parameter) |
| **Virtual Time** | Disabled (real-time) | Enabled (via Redis key) |
| **Running** | Continuous loop (forever) | One-time replay (exhausts data) |
| **Time Control** | No control (real-time) | Speed control (0.0 to N) |
| **Data Freshness** | < 5 seconds | Historical (past data) |
| **Stop Condition** | Manual (Ctrl+C) | Automatic (data exhausted) |
| **Collector Component** | `LTPDataCollector` | `HistoricalTickReplayer` |
| **Redis Store Code** | ✅ **SAME** (`RedisMarketStore`) | ✅ **SAME** (`RedisMarketStore`) |
| **Candle Builder Code** | ✅ **SAME** (`CandleBuilder`) | ✅ **SAME** (`CandleBuilder`) |
| **Indicators Code** | ✅ **SAME** (`TechnicalIndicatorsService`) | ✅ **SAME** (`TechnicalIndicatorsService`) |
| **API Code** | ✅ **SAME** (mode-agnostic) | ✅ **SAME** (mode-agnostic) |

---

## 🔧 Common Components (Used by Both Modes)

### 1. **RedisMarketStore** (`adapters/redis_store.py`)
**Same code for both modes:**
```python
class RedisMarketStore(MarketStore):
    def store_tick(self, tick: MarketTick) -> None:
        # 1. Store tick in Redis
        self.redis.setex(f"tick:{tick.instrument}:{timestamp}", TTL, json.dumps(tick))
        
        # 2. Auto-build OHLC candles (if enabled)
        if self._enable_candle_building:
            self._process_tick_for_ohlc(tick)  # Uses CandleBuilder
        
        # 3. Auto-update technical indicators (if enabled)
        if self._enable_technical_indicators:
            self._technical_service.update_tick(tick.instrument, tick_dict)
```

### 2. **CandleBuilder** (`adapters/candle_builder.py`)
**Same code for both modes:**
```python
class CandleBuilder:
    """Builds OHLC candles from ticks (works for both live and historical)"""
    
    def process_tick(self, tick: MarketTick) -> Optional[OHLCBar]:
        # Aggregates ticks into time-based candles
        # Emits OHLCBar when candle closes
        # Called automatically by RedisMarketStore
```

### 3. **TechnicalIndicatorsService** (`technical_indicators_service.py`)
**Same code for both modes:**
```python
class TechnicalIndicatorsService:
    """Calculates technical indicators (works for both live and historical)"""
    
    def update_tick(self, instrument, tick_dict):
        # Updates indicators from tick data
        # Called automatically by RedisMarketStore
    
    def update_candle(self, instrument, candle_dict):
        # Updates indicators from OHLC candle
        # Called when candle closes
```

### 4. **Market Data API** (`api_service.py`)
**Same code for both modes (mode-agnostic):**
```python
@app.get("/api/market/tick/latest")
async def get_latest_tick(instrument: str):
    # Reads from Redis: tick:{instrument}:latest
    # Works for both live and historical (doesn't know the difference)
    return store.get_latest_tick(instrument)

@app.get("/api/market/ohlc")
async def get_ohlc(instrument: str, timeframe: str):
    # Reads from Redis: ohlc_sorted:{instrument}:{timeframe}
    # Works for both live and historical (doesn't know the difference)
    return store.get_ohlc(instrument, timeframe)
```

---

## 🎯 Virtual Time Mechanism (Historical Mode Only)

Historical mode uses **virtual time** to simulate past market conditions:

### How It Works:
1. **Redis Key:** `system:virtual_time:current`
   - Set by `HistoricalTickReplayer` for each tick
   - Contains the current virtual timestamp

2. **Reading Virtual Time:**
   ```python
   import redis
   r = redis.Redis()
   virtual_time_str = r.get("system:virtual_time:current")
   virtual_time = datetime.fromisoformat(virtual_time_str)
   ```

3. **Strategy/Agent Code:**
   - Can check `system:virtual_time:current` to get "current" time
   - In historical mode: Returns virtual time (past date)
   - In live mode: This key doesn't exist (use `datetime.now()`)

### Example:
```python
# Historical mode (virtual time enabled)
system:virtual_time:enabled → "1"
system:virtual_time:current → "2025-01-15 15:30:00"

# Strategy code
if redis.get("system:virtual_time:enabled") == "1":
    current_time = datetime.fromisoformat(redis.get("system:virtual_time:current"))
else:
    current_time = datetime.now()
```

---

## 🔄 Rebase Mode (Alternative to Virtual Time)

Instead of setting system-wide virtual time, ticks can be **rebased** to appear as "now":

```python
# Rebase mode: Shift all ticks by offset
first_tick_time = ticks[0].timestamp  # e.g., 2025-01-15 09:15:00
target_time = datetime.now()  # e.g., 2026-01-XX 10:00:00
offset = target_time - first_tick_time  # e.g., 365 days

# Each tick timestamp is shifted
tick.original_timestamp = tick.timestamp  # Preserve original
tick.timestamp = tick.timestamp + offset  # Shift to "now"
```

**Benefits:**
- ✅ No need to check virtual time (use `datetime.now()`)
- ✅ Original timestamp preserved in `original_timestamp` field
- ✅ Strategy code doesn't need to change

---

## 📈 Data Creation Summary

### Real-Time Mode:
1. **LTPCollector** runs every 2 seconds
2. Fetches current quote from Zerodha
3. Creates `MarketTick` with current time
4. Stores via `RedisMarketStore.store_tick()`
5. `RedisMarketStore` automatically:
   - Stores tick in Redis
   - Builds OHLC candles
   - Updates technical indicators
6. API serves data from Redis (mode-agnostic)

### Historical Mode:
1. **HistoricalTickReplayer** loads historical data (once)
2. Fetches from Zerodha API or CSV file
3. Converts to `MarketTick` objects (preserving timestamps)
4. Replays ticks in chronological order
5. Sets virtual time (or rebases timestamps)
6. Stores via `RedisMarketStore.store_tick()` (SAME code)
7. `RedisMarketStore` automatically:
   - Stores tick in Redis
   - Builds OHLC candles (SAME code)
   - Updates technical indicators (SAME code)
8. API serves data from Redis (mode-agnostic, SAME code)

---

## ✅ Key Takeaway

**Both modes use REAL Zerodha data, not mock data:**
- **Real-Time Mode:** Real-time data from Zerodha WebSocket/REST API
- **Historical Mode:** Real historical data from Zerodha Historical API
- **Options Chain:** Real Zerodha API in both modes (`quote()` or `ltp()`)

**The data creation logic is identical after the tick is created:**
- Same `RedisMarketStore` code
- Same `CandleBuilder` code
- Same `TechnicalIndicatorsService` code
- Same API code
- Same Redis keys

**The only difference is:**
- How ticks are **created** (Live: WebSocket/REST, Historical: Historical API/CSV)
- How ticks are **timed** (Live: `datetime.now()`, Historical: original or rebased)
- How ticks are **emitted** (Live: continuous loop, Historical: replay loop)

**Note:** The `ZerodhaOptionsChainAdapter` uses **real Zerodha API** (`kite.quote()` or `kite.ltp()`) in both modes!

This ensures **strategy code works identically** in both modes with **real market data**! 🎯
