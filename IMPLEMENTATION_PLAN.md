# 🎯 Implementation Plan: Mock WebSocket → EventEngine → Bars + Indicators Pipeline

> **Status:** Historical reference. For current runtime commands and source switching use `start_all.sh --help` and `market_data/README.md`.


**Goal**: Implement end-to-end event-driven data flow from Mock WebSocket to Dashboard.

**Architecture**: Uses EXISTING event-driven components (EventEngine, BarGenerator, TechnicalIndicatorsService)

**Scope**: 
- ✅ Mock WebSocket (NEW) → Tick Handler (EXISTING) → EventEngine (EXISTING)
- ✅ EventEngine → BarGenerator (EXISTING - multi-timeframe aggregation)
- ✅ Real-time indicator calculation triggered by bar events (EVENT-DRIVEN)
- ⏭️ **DEFERRED to Next Stage**: Option chain analysis, depth feed, options-specific indicators

---

## 📋 Overview

**Architecture Pattern**: Event-Driven with swappable data source

```
Mock/Real WebSocket (PLUGGABLE) 
       ↓
WebSocketTickCollector (EXISTING)
       ↓
EventEngine (EXISTING - Message Bus)
       ↓ (EVENT_TICK events)
BarGenerator (EXISTING - subscribes to ticks)
       ↓ (generates bars)
EventEngine (EVENT_BAR_1M, EVENT_BAR_5M, etc.)
       ↓
RealTimeIndicatorHandler (NEW - subscribes to bar events)
       ↓
Redis Storage (AUTO-PREFIXED: live: or historical:)
```

**Key Principles**: 
- **Event-Driven**: All components communicate via EventEngine
- **Real-Time**: Indicators calculated as bars close (event-driven)
- **Swappable**: Only data source changes (Mock ↔ Real), all else identical
- **Mode-Agnostic**: redis_key_manager adds live:/historical: prefix automatically

---

## 🎯 Phase 1: Mock WebSocket Implementation

**Goal**: Create mock WebSocket that emits ticks identical to Real Kite WebSocket format

### Deliverables:
1. **`market_data/src/websocket/mock_kite_websocket.py`**
   - Class: `MockKiteWebSocket`
   - Emits ticks matching Real Kite format exactly:
     ```python
     {
         'instrument_token': 256265,
         'last_price': 45000.0,
         'volume': 12345,
         'last_traded_quantity': 1,
         'average_traded_price': 44950.0,
         'volume_traded': 1234567,
         'total_buy_quantity': 50000,
         'total_sell_quantity': 48000,
         'ohlc': {
             'open': 44800.0,
             'high': 45100.0,
             'low': 44750.0,
             'close': 45000.0
         },
         'timestamp': datetime(2026, 2, 7, 10, 30, 0)
     }
     ```
   - Methods:
     - `connect()`: Start mock tick generation
     - `subscribe(instrument_tokens)`: Set instruments to simulate
     - `on_ticks(callback)`: Register tick handler
     - `close()`: Stop mock

2. **Tick Generation Strategies**:
   - **Option A**: Random walk (for testing)
   - **Option B**: Replay from CSV/database
   - **Option C**: Synthetic patterns (trending, ranging, volatile)
   
   Start with **Option A** (simplest), make it configurable later.

### Implementation Details:
```python
class MockKiteWebSocket:
    def __init__(self, tick_interval=1.0, price_volatility=0.002):
        self.tick_interval = tick_interval  # seconds between ticks
        self.price_volatility = price_volatility  # % price change per tick
        self.instruments = {}  # token -> current_state
        self.on_ticks_callback = None
        self.running = False
        
    def subscribe(self, instrument_tokens):
        # Initialize state for each instrument
        for token in instrument_tokens:
            self.instruments[token] = {
                'last_price': 45000.0,  # starting price
                'volume': 0
            }
    
    def connect(self):
        # Start background thread generating ticks
        self.running = True
        threading.Thread(target=self._tick_generator).start()
    
    def _tick_generator(self):
        while self.running:
            ticks = []
            for token, state in self.instruments.items():
                # Generate next tick (random walk)
                tick = self._generate_tick(token, state)
                ticks.append(tick)
            
            if self.on_ticks_callback:
                self.on_ticks_callback(ticks)
            
            time.sleep(self.tick_interval)
```

### Acceptance Criteria:
- ✅ Mock emits ticks every 1 second
- ✅ Tick format matches Real Kite WebSocket exactly
- ✅ Can subscribe to multiple instruments
- ✅ Price follows realistic random walk
- ✅ Volume increments realistically

---

## 🎯 Phase 2: EventEngine + Tick Handler (EXISTING - REUSED) ✅

**Status**: Already implemented and tested!

### What Exists:
1. **`market_data/src/market_data/event_engine.py`** (VN.py-inspired)
   - EventEngine: Thread-safe message bus
   - Event types: EVENT_TICK, EVENT_BAR, EVENT_BAR_1M, EVENT_BAR_5M, etc.
   - Subscribe/publish pattern for decoupled components
   - Used by existing strategy system

2. **`market_data/src/market_data/collectors/websocket_tick_collector.py`**
   - WebSocketTickCollector: Handles both Real and Mock WebSocket
   - Publishes ticks to Redis channels + EventEngine
   - **Supports EventEngine integration** (optional parameter)
   - Mode-agnostic tick processing

### Integration:
```python
# WebSocketTickCollector already supports EventEngine!
collector = WebSocketTickCollector(
    instruments=instruments,
    event_engine=event_engine  # ← Pass EventEngine here!
)

# Collector publishes EVENT_TICK to EventEngine automatically
# Any subscriber can react to ticks in real-time
```

### Acceptance Criteria:
- ✅ Works with both Real and Mock WebSocket
- ✅ Publishes to EventEngine (EVENT_TICK events)
- ✅ Thread-safe event processing
- ✅ Mode-agnostic (doesn't know about live/historical)
- ✅ Already tested in production

---

## 🎯 Phase 3: BarGenerator + Multi-Timeframe (EXISTING - REUSED) ✅

**Status**: Already implemented and tested!

### What Exists:
1. **`market_data/src/market_data/bar_generator.py`** (VN.py-inspired)
   - BarGenerator: Aggregates ticks → 1-minute bars
   - Multi-timeframe: 1min → X-minute bars (5, 15, 30, etc.)
   - Multi-hour support: 1min → X-hour bars
   - Callback-based architecture (event-driven compatible)

### How It Works:
```python
# Create BarGenerator that subscribes to EVENT_TICK
def on_1min_bar(bar: OHLCBar):
    # Store bar
    store.store_ohlc(...)
    # Publish bar event
    event_engine.put(Event(EVENT_BAR_1M, bar))

def on_5min_bar(bar: OHLCBar):
    event_engine.put(Event(EVENT_BAR_5M, bar))

# BarGenerator with multi-timeframe
bg = BarGenerator(
    on_bar=on_1min_bar,           # 1-minute bars
    window=5,                      # Aggregate to 5-minute
    on_window_bar=on_5min_bar,    # 5-minute bars
    interval=Interval.MINUTE
)

# Subscribe to EVENT_TICK
def on_tick(event: Event):
    bg.update_tick(event.data)

event_engine.register(EVENT_TICK, on_tick)
```

### Acceptance Criteria:
- ✅ Aggregates ticks into 1-minute bars
- ✅ Closes bar at minute boundary
- ✅ Builds 5min, 15min, 1h from 1min bars
- ✅ Event-driven via callbacks
- ✅ Mode-agnostic (doesn't know about live/historical)
- ✅ Already used in strategy system

---

## 🎯 Phase 3.5: Real-Time Indicator Calculation (NEW) ✅

**Goal**: Subscribe to bar events and calculate indicators in real-time (event-driven)

### Deliverables:
1. **`RealTimeIndicatorHandler`** (in simple_runner.py)
   - Subscribes to bar events (EVENT_BAR_1M, 5M, 15M, 1H)
   - Triggered when bar closes (event-driven)
   - Calculates indicators using existing TechnicalIndicatorsService
   - Stores with mode prefix automatically

### Implementation:
```python
class RealTimeIndicatorHandler:
    def __init__(self, event_engine, store):
        self.event_engine = event_engine
        self.store = store
        
        # Subscribe to bar events (event-driven!)
        event_engine.register(EVENT_BAR_1M, self._on_bar)
        event_engine.register(EVENT_BAR_5M, self._on_bar)
    
    def _on_bar(self, event: Event):
        bar = event.data
        
        # Get last N bars
        bars = self.store.get_ohlc(bar.instrument, bar.timeframe, limit=100)
        
        # Calculate indicators (EXISTING service)
        indicators_service = TechnicalIndicatorsService()
        indicators = indicators_service.calculate_indicators(
            instrument=bar.instrument,
            timeframe=bar.timeframe,
            bars=bars
        )
        
        # Store (mode prefix added automatically)
        indicators_service.store_indicators(bar.instrument, bar.timeframe, indicators)
```

### Acceptance Criteria:
- ✅ Subscribes to bar events (event-driven)
- ✅ Calculates indicators in real-time as bars close
- ✅ Uses existing TechnicalIndicatorsService (30+ indicators)
- ✅ Stores indicators with mode prefix
- ✅ RSI, MACD, SMA, EMA, Bollinger Bands, ATR, ADX, etc.

---

## 🎯 Phase 4: Event-Driven Pipeline Runner ✅

**Goal**: Wire Mock/Real WebSocket to event-driven pipeline (EventEngine → BarGenerator → Indicators)

**Status**: Implemented in `simple_runner.py`

### Deliverables:
1. **`simple_runner.py`** (root of project) - **COMPLETED**
   - Command-line: `python simple_runner.py --websocket [mock|real]`
   - EventDrivenPipelineRunner: Orchestrates everything
   - RealTimeIndicatorHandler: Event-driven indicator calculation
   - Swappable WebSocket source (Mock OR Real)

### Implementation:
```python
# simple_runner.py

class RealTimeIndicatorHandler:
    """Event subscriber that calculates indicators when bars close."""
    
    def __init__(self, event_engine, store):
        self.event_engine = event_engine
        self.store = store
        
        # Subscribe to all bar events (event-driven!)
        event_engine.register(EVENT_BAR_1M, self._on_bar)
        event_engine.register(EVENT_BAR_5M, self._on_bar)
        event_engine.register(EVENT_BAR_15M, self._on_bar)
        event_engine.register(EVENT_BAR_1H, self._on_bar)
    
    def _on_bar(self, event: Event):
        """Triggered when bar closes (event-driven)."""
        bar = event.data
        
        # Get last N bars
        bars = self.store.get_ohlc(bar.instrument, bar.timeframe, limit=100)
        
        if len(bars) < 14:  # Minimum for indicators
            return
        
        # Calculate indicators (EXISTING service)
        indicators_service = TechnicalIndicatorsService()
        indicators = indicators_service.calculate_indicators(...)
        
        # Store with mode prefix
        indicators_service.store_indicators(...)


class EventDrivenPipelineRunner:
    """Orchestrates Mock/Real WebSocket with event-driven pipeline."""
    
    def __init__(self, websocket_type='mock'):
        self.websocket_type = websocket_type
        
        # Core components (event-driven)
        self.event_engine = EventEngine()
        self.store = RedisMarketStore()
        
        # Real-time indicator calculator (subscribes to bar events)
        self.indicator_handler = RealTimeIndicatorHandler(
            event_engine=self.event_engine,
            store=self.store
        )
    
    def _setup_bar_generators(self, instruments):
        """Create BarGenerators that subscribe to EVENT_TICK."""
        
        for instrument in instruments:
            # Callback for 1-minute bars
            def on_1min_bar(bar):
                self.store.store_ohlc(...)
                self.event_engine.put(Event(EVENT_BAR_1M, bar))
            
            # Callback for 5-minute bars
            def on_5min_bar(bar):
                self.store.store_ohlc(...)
                self.event_engine.put(Event(EVENT_BAR_5M, bar))
            
            # BarGenerator with multi-timeframe
            bg = BarGenerator(
                on_bar=on_1min_bar,           # 1-minute bars
                window=5,                      # Aggregate to 5-minute
                on_window_bar=on_5min_bar,    # 5-minute bars
                interval=Interval.MINUTE
            )
            
            # Subscribe to EVENT_TICK
            def on_tick(event):
                if event.data.instrument_token == instrument:
                    bg.update_tick(event.data)
            
            self.event_engine.register(EVENT_TICK, on_tick)
    
    def _start_mock_websocket(self, instruments):
        """Start Mock WebSocket integrated with EventEngine."""
        
        ticker = create_mock_ticker(api_key="mock_key")
        
        # WebSocketTickCollector publishes to EventEngine
        collector = WebSocketTickCollector(
            instruments=instruments,
            event_engine=self.event_engine  # ← EventEngine integration!
        )
        
        # Connect Mock WebSocket to collector
        ticker.on_ticks = collector.handle_ticks
        ticker.on_connect = lambda: ticker.subscribe(instruments)
        
        ticker.connect()
        return ticker
    
    def run(self, instruments):
        """Start event-driven pipeline."""
        
        # 1. Start EventEngine
        self.event_engine.start()
        
        # 2. Setup BarGenerators (subscribe to EVENT_TICK)
        self._setup_bar_generators(instruments)
        
        # 3. Start WebSocket (Mock or Real)
        if self.websocket_type == 'mock':
            ticker = self._start_mock_websocket(instruments)
        else:
            ticker = self._start_real_websocket(instruments)
        
        # Event-driven pipeline now running!
        # EventEngine → BarGenerator → RealTimeIndicatorHandler
```

### Event Flow:
```
MockKiteTicker (or Real) 
    ↓ on_ticks callback
WebSocketTickCollector 
    ↓ event_engine.put(EVENT_TICK)
EventEngine 
    ↓ dispatch to subscribers
BarGenerator (subscribes to EVENT_TICK)
    ↓ aggregates ticks → bars
EventEngine 
    ↓ event_engine.put(EVENT_BAR_1M, 5M, 15M, 1H)
RealTimeIndicatorHandler (subscribes to EVENT_BAR_*)
    ↓ calculates indicators on bar close
Redis (with mode prefix: live:/ historical:)
```

### Usage:
```bash
# Run with Mock WebSocket (no credentials needed)
python simple_runner.py --websocket mock --verbose

# Run with Real WebSocket (needs credentials)
set KITE_API_KEY=your_key
set KITE_ACCESS_TOKEN=your_token
python simple_runner.py --websocket real --verbose
```

### Acceptance Criteria:
- ✅ Event-driven architecture (uses existing EventEngine + BarGenerator)
- ✅ Swappable between Mock and Real WebSocket
- ✅ Real-time indicator calculation (event-triggered on bar close)
- ✅ Mode-agnostic (live/historical prefix automatic)
- ✅ No duplication (reuses tested components)
- ✅ Single entry point for testing

---

## 🎯 Phase 5: Testing & Verification

**Goal**: End-to-end validation of the pipeline

### Test Cases:

#### Test 1: Historical Mode (Outside Market Hours)
```powershell
# Start Mock WebSocket (should write to historical:* keys)
cd c:\code\zerodha\market_data
python -m market_data.runner --websocket-type mock --instruments 256265

# Verify ticks flowing
redis-cli
> KEYS historical:ohlc_sorted:*
> ZRANGE historical:ohlc_sorted:256265:1min 0 -1 WITHSCORES

# Check API
curl http://localhost:8004/api/v1/market/ohlc/256265?timeframe=1min

# Check Dashboard
# Open browser: http://localhost:8000/
```

**Expected Results**:
- ✅ Redis keys have `historical:` prefix
- ✅ New bars appear every minute
- ✅ API returns growing list of bars
- ✅ Dashboard shows live updating chart

#### Test 2: Live Mode (During Market Hours 09:15-15:30 IST)
```powershell
# Same command, but run during market hours
python -m market_data.runner --websocket-type mock --instruments 256265

# Verify keys
redis-cli
> KEYS live:ohlc_sorted:*
> ZRANGE live:ohlc_sorted:256265:1min 0 -1 WITHSCORES
```

**Expected Results**:
- ✅ Redis keys have `live:` prefix
- ✅ Everything else identical to Test 1

#### Test 3: Mode Switching
```powershell
# Start at 09:14 IST (historical mode)
# Verify: historical:* keys

# Wait until 09:15 IST (automatic switch to live)
# Verify: Now writing to live:* keys

# Stop at 15:30 IST
# Verify: Switches back to historical:* keys
```

**Expected Results**:
- ✅ Automatic mode switch at market boundaries
- ✅ No code changes needed
- ✅ Same Mock WebSocket keeps running

---

## 🎯 Phase 6: Documentation & Cleanup

### Deliverables:
1. **Update `README.md`** with quick start:
   ```markdown
   ## Quick Start
   
   1. Start Redis:
      ```bash
      docker-compose up -d redis
      ```
   
   2. Start Mock WebSocket + Aggregator:
      ```bash
      cd market_data
      python -m market_data.runner --websocket-type mock
      ```
   
   3. Start API:
      ```bash
      python market_data/start_api.py
      ```
   
   4. Open Dashboard:
      ```
      http://localhost:8000/
      ```
   ```

2. **Create `TESTING.md`** with test scenarios

3. **Update `MODE_SYSTEM.md`** with implementation status

---

## 📊 Success Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| Mock tick rate | 1 tick/second | Log output |
| Bar aggregation | 1min bars forming | Redis ZRANGE |
| API latency | < 100ms | curl timing |
| Dashboard update | Real-time chart | Browser test |
| Mode isolation | 100% separate keys | Redis KEYS scan |
| Code reuse | Same handler for both modes | Code review |

---

## 🚀 Rollout Plan

1. **Phase 1-2**: Implement Mock WebSocket + Tick Handler (Day 1)
2. **Phase 3**: Implement OHLC Aggregator (Day 1-2)
3. **Phase 4**: Runner Integration (Day 2)
4. **Phase 5**: Testing & Verification (Day 3)
5. **Phase 6**: Documentation (Day 3)

**Total Estimated Time**: 3 days

---

## ⚠️ Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tick format mismatch with Real Kite | High | Copy exact format from Kite docs |
| Performance issues at high tick rate | Medium | Use threading, optimize aggregator |
| Mode detection fails at boundary | Medium | Add buffer zone (09:14-09:16) |
| Redis connection loss | High | Retry logic with exponential backoff |
| Memory leak in long-running process | Medium | Periodic garbage collection |

---

## 🔄 Future Enhancements (Next Stage)

**Current Stage**: OHLC + Indicators pipeline for futures/equity
**Next Stage**: Options features

1. **Real Kite WebSocket Integration**
   - Drop-in replacement for Mock
   - Same tick handler, zero code changes

2. **Historical Replay**
   - Read CSV → emit ticks → same pipeline

3. **Multiple Instruments**
   - Scale to 100+ instruments
   - Parallel aggregation

4. **Advanced Mock Strategies**
   - Replay real market data
   - Pattern generation (breakouts, reversals)

5. **Options Features** (Next Stage)
   - Option chain feed
   - Options depth (bid/ask stacks)
   - Greeks calculation (delta, gamma, theta, vega)
   - IV (Implied Volatility) tracking
   - Options-specific indicators (PCR, max pain, etc.)
   - Options order book analysis

---

## ✅ Approval Checklist

Before implementation, confirm:
- [ ] Architecture matches MODE_SYSTEM.md design
- [ ] Swappable data source pattern clear
- [ ] Mode-agnostic downstream code
- [ ] Fail-fast principles maintained
- [ ] No legacy fallbacks
- [ ] Testing plan covers both modes
- [ ] Documentation plan complete

---

**Status**: 🟡 AWAITING APPROVAL

Once approved, implementation will proceed phase by phase with verification at each step.
