# System Features

Comprehensive guide to key features of the Trading AI System.

## Table of Contents

1. [Real-time Signal-to-Trade](#real-time-signal-to-trade)
2. [Technical Indicators Integration](#technical-indicators-integration)
3. [Historical Mode & Replay](#historical-mode--replay)
4. [Multi-Agent System](#multi-agent-system)
5. [Virtual Time Synchronization](#virtual-time-synchronization)

---

## Real-time Signal-to-Trade

### Overview

The SignalMonitor system converts agent analysis into conditional trades that execute in real-time when technical conditions are met.

### How It Works

```
1. Agent Analysis (15-min cycle)
   ├─> Analyzes market conditions
   ├─> Creates CONDITIONAL signal: "BUY when RSI > 32"
   └─> Registers signal with SignalMonitor

2. Real-time Monitoring (EVERY tick, ~100-200ms)
   ├─> Market tick arrives
   ├─> TechnicalIndicatorsService updates RSI
   ├─> SignalMonitor checks: "Is RSI > 32 now?"
   │   ├─> NO  → Wait for next tick
   │   └─> YES → TRIGGER TRADE IMMEDIATELY!
   └─> Trade execution callback fires

3. Trade Executed
   ├─> Order placed via broker API
   ├─> Signal marked as triggered
   └─> Signal auto-removed from monitor
```

### Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `GREATER_THAN` | Value > threshold | RSI > 70 |
| `LESS_THAN` | Value < threshold | RSI < 30 |
| `EQUALS` | Value == threshold | MACD == 0 |
| `CROSSES_ABOVE` | Value crosses from below to above | RSI crosses above 50 |
| `CROSSES_BELOW` | Value crosses from above to below | Price crosses below SMA |

### Multi-Condition Signals

Supports AND logic for complex conditions:

```python
condition = TradingCondition(
    condition_id="complex_buy",
    instrument="BANKNIFTY",
    indicator="rsi_14",
    operator=ConditionOperator.GREATER_THAN,
    threshold=50.0,
    action="BUY",
    additional_conditions=[
        {"indicator": "current_price", "operator": ">", "threshold": 45100},
        {"indicator": "volume_ratio", "operator": ">", "threshold": 1.5}
    ]
)
```

Trade only triggers when ALL conditions are met simultaneously.

### Example Usage

```python
from engine_module.src.engine_module.signal_monitor import SignalMonitor, TradingCondition, ConditionOperator

# Create monitor
monitor = SignalMonitor()

# Add signal
signal = TradingCondition(
    condition_id="momentum_buy",
    instrument="BANKNIFTY",
    indicator="rsi_14",
    operator=ConditionOperator.GREATER_THAN,
    threshold=32.0,
    action="BUY"
)
monitor.add_signal(signal)

# On every tick
events = await monitor.check_signals("BANKNIFTY")
if events:
    for event in events:
        print(f"TRIGGER! {event.action} {event.instrument}")
        execute_trade(event)
```

---

## Technical Indicators Integration

### Architecture

```
Market Tick
    ↓
TechnicalIndicatorsService.update_tick()
    ↓
Calculate ALL indicators ONCE:
  • RSI, MACD (momentum)
  • SMA, EMA, ADX (trend)
  • Bollinger Bands, ATR (volatility)
  • Volume ratios
  • Support/Resistance
    ↓
Store in memory
    ↓
Agent.analyze() → get_indicators()
    ↓
4 Perspective Analysis:
  • Momentum
  • Trend  
  • Mean Reversion
  • Volume
    ↓
Multi-agent Consensus → Trading Decision
```

### Available Indicators

**Momentum**:
- RSI (14, 21 periods)
- MACD (12, 26, 9)
- Stochastic
- CCI

**Trend**:
- SMA (20, 50, 200)
- EMA (9, 21)
- ADX
- Trend direction

**Volatility**:
- Bollinger Bands
- ATR
- Standard Deviation

**Volume**:
- Volume Ratio
- VWAP
- OBV

**Price Action**:
- Current Price
- Support/Resistance
- Price change %

### Usage

```python
from market_data.src.market_data.technical_indicators_service import get_technical_service

service = get_technical_service()

# Update on every tick
indicators = service.update_tick("BANKNIFTY", {
    "last_price": 45123.50,
    "volume": 1800,
    "timestamp": "2026-01-06T10:00:00"
})

# Access indicators
print(f"RSI: {indicators.rsi_14}")
print(f"Trend: {indicators.trend_direction}")
print(f"Bollinger Upper: {indicators.bb_upper}")

# Get as dict
indicators_dict = service.get_indicators_dict("BANKNIFTY")
```

### Warm-Up Period

Requires 50+ candles for accurate calculations:

```python
# Warm up
for i in range(50):
    service.update_candle("BANKNIFTY", {
        "timestamp": f"2026-01-06T09:{15+i}:00",
        "open": 45000,
        "high": 45020,
        "low": 44980,
        "close": 45010,
        "volume": 1500
    })
```

---

## Historical Mode & Replay

### Mode Overview

| Mode | Data Source | Trading | Use Case |
|------|-------------|---------|----------|
| `live` | Live Zerodha | Real money | Production trading |
| `paper_live` | Live Zerodha | Paper | Test strategies with live data |
| `paper_mock` | Historical or Synthetic | Paper | Backtesting, replay |

### Historical Replay

Switch to paper_mock with a specific date to replay historical data:

```bash
POST /api/control/mode/switch
{
    "mode": "paper_mock",
    "historical_start_date": "2024-01-15",
    "historical_end_date": "2024-01-31",
    "historical_interval": "minute"
}
```

### Virtual Time System

When in historical replay:
- All components use synchronized virtual time
- Market data matches the replay date
- Agents analyze data from that date
- Trades execute in simulated time
- Market hours respected for replay date

```python
# Set virtual time
from core_kernel.src.core_kernel.time_service import set_virtual_time

set_virtual_time(datetime(2024, 1, 15, 10, 0, 0))

# All system components now use this time
# - Dashboard shows 2024-01-15
# - Orchestrator runs with 2024-01-15 time
# - Market data from 2024-01-15
# - Agents analyze 2024-01-15 data
```

### Historical Data Sources

1. **Zerodha Historical Data**
   - Fetch via Kite API: `kite.historical_data()`
   - Supports minute, day, 3min, 5min, 15min, 30min, 60min intervals
   - Up to 60 days of intraday data
   - Years of daily data

2. **MongoDB Storage**
   - Cache historical data locally
   - Fast retrieval for repeated backtests
   - Schema: `historical_data` collection

3. **Synthetic Data**
   - Fallback when Zerodha data unavailable
   - Realistic price movements
   - Configurable volatility

---

## Multi-Agent System

### Agent Architecture

4 specialized agents analyze from different perspectives:

#### 1. Momentum Agent
**Strategy**: Capture breakouts with volume confirmation

**Entry Conditions**:
- RSI > 70 (overbought momentum)
- Volume 50%+ above average
- MACD positive crossover

**Exit Conditions**:
- RSI < 50
- 2% trailing stop loss
- Volume dries up

#### 2. Trend Agent
**Strategy**: Follow established trends

**Entry Conditions**:
- Price breaks above/below 20 SMA
- ADX > 25 (strong trend)
- Higher highs + higher lows (uptrend)

**Exit Conditions**:
- Price closes opposite side of SMA
- ADX < 20 (weakening trend)
- Trend reversal pattern

#### 3. Mean Reversion Agent
**Strategy**: Profit from extremes

**Entry Conditions**:
- Price touches Bollinger Bands
- RSI < 30 (oversold) or > 70 (overbought)
- Stochastic extreme

**Exit Conditions**:
- Price reaches band middle
- 50% position exit at midpoint
- RSI normalizes (40-60)

#### 4. Volume Agent
**Strategy**: Volume-based confirmation

**Entry Conditions**:
- Volume spike (>2x average)
- Price movement in same direction
- OBV confirming

**Exit Conditions**:
- Volume normalizes
- Price/volume divergence
- OBV reverses

### Consensus Mechanism

Agents vote with weighted confidence:

```python
# Each agent provides
{
    "decision": "BUY|SELL|HOLD",
    "confidence": 0.75,  # 0-1 scale
    "reasoning": "Strong momentum with volume confirmation"
}

# Weighted scores
buy_score = sum(confidence for agent in agents if decision == "BUY")
sell_score = sum(confidence for agent in agents if decision == "SELL")
hold_score = sum(confidence for agent in agents if decision == "HOLD")

# Final decision
if buy_score > 2.0:  # Strong consensus
    execute_buy()
elif sell_score > 2.0:
    execute_sell()
else:
    hold()
```

### Position Awareness

Agents receive current position context:

```python
context = {
    "instrument": "BANKNIFTY",
    "current_position": {
        "side": "LONG",
        "quantity": 50,
        "entry_price": 45000,
        "current_pnl": 2500
    }
}

# Agents adjust recommendations based on position
# - Hold profitable positions longer
# - Suggest partial exits
# - Add to winning positions
# - Cut losers quickly
```

---

## Virtual Time Synchronization

### Architecture

```
Redis (Source of Truth)
  ├─ system:virtual_time:enabled = 1
  └─ system:virtual_time:current = 2026-01-06T10:00:00+05:30
       │
       ├──────────────┬──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼              ▼
  Dashboard    Orchestrator   HistReplay    MarketData    TestSuite
  app.py       run_orch.py    replayer      live_data     test_*.py
       │              │              │              │              │
  TimeService    TimeService    Sets Time     Uses Time      Uses Time
  .now()         .now()         in Redis      from Redis     from Redis
```

### Benefits

1. **Historical Simulation**: Entire system operates on past dates
2. **Reproducibility**: Fixed time = consistent results
3. **Market Hours Testing**: Test open/close boundaries
4. **Time Travel**: Test future/past scenarios
5. **Cross-Container Sync**: All Docker containers synchronized

### API

```python
from core_kernel.src.core_kernel.time_service import (
    now as get_system_time,
    set_virtual_time,
    clear_virtual_time,
    is_virtual_time
)

# Get current time (virtual or real)
current = get_system_time()

# Enable virtual time
set_virtual_time(datetime(2026, 1, 6, 10, 0, 0))

# Check if virtual
if is_virtual_time():
    print("Running in virtual time mode")

# Disable virtual time
clear_virtual_time()
```

### HTTP API

```bash
# Get system time
GET /api/system-time

# Set virtual time
POST /api/system-time/set
{
    "datetime": "2026-01-06T10:00:00"
}

# Clear virtual time
POST /api/system-time/clear
```

### Automatic Virtual Time

When switching to `paper_mock` mode, virtual time is automatically set:

```python
# Dashboard app.py
if mode == "paper_mock" and historical_start_date:
    # Automatically set virtual time to start date
    set_virtual_time(historical_start_date)
```

### Market Hours Integration

Market hours check uses virtual time when enabled:

```python
from core_kernel.src.core_kernel.market_hours import is_market_open

# Automatically uses virtual time if set
if is_market_open():
    run_trading_cycle()
else:
    print("Market closed, pausing orchestrator")
```

**Orchestrator Blocking**:
```python
# run_orchestrator.py
while True:
    current_time = get_system_time()
    
    if not is_market_open(current_time):
        logger.info("Market closed, waiting...")
        await asyncio.sleep(60)
        continue
    
    # Run trading cycle
    await run_agents()
```

### Timezone Handling

- **Internal**: UTC for calculations
- **Storage**: IST (UTC+5:30) in MongoDB/Redis
- **Display**: IST in dashboard

```python
import pytz

IST = pytz.timezone('Asia/Kolkata')

# Store in IST
ist_time = utc_time.astimezone(IST)
mongodb.insert({"timestamp": ist_time.isoformat()})

# Display in IST
display_time = ist_time.strftime('%Y-%m-%d %H:%M:%S %Z')
```

### Market Hours

- **Open**: Monday-Friday 9:15 AM IST (inclusive, >=)
- **Close**: Monday-Friday 3:30 PM IST (exclusive, <)

**Boundary Fix**: Uses `<` not `<=` so 3:30 PM exactly is considered closed.

```python
# Correct
market_open <= current_time < market_close  # 3:30 is closed

# Wrong
market_open <= current_time <= market_close  # 3:30 shows as open
```

