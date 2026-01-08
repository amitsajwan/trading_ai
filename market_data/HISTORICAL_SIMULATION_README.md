# Historical Simulation System

## 🧠 Core Principle

**Strategy should NOT know the difference between live and historical data.**

The same code path processes both:
- **Live**: Zerodha WebSocket → MarketTick → Candle Builder → Indicators → Strategy → Orders
- **Historical**: CSV/Generator → MarketTick → Candle Builder → Indicators → Strategy → Paper Orders

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCE LAYER                         │
├─────────────────────────────────────────────────────────────┤
│  Live: Zerodha WebSocket → MarketTick                       │
│  Historical: CSV/Generator → MarketTick                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    CANDLE BUILDER                            │
│  (SAME CODE for live and historical)                        │
│  Aggregates ticks → OHLCBar                                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    INDICATOR ENGINE                         │
│  (SAME CODE for live and historical)                         │
│  Calculates RSI, MACD, EMA, VWAP, etc.                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    STRATEGY ENGINE                           │
│  (SAME CODE for live and historical)                         │
│  Evaluates signals, places orders                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    ORDER EXECUTION                           │
│  Live: kite.place_order()                                   │
│  Historical: paper_broker.place_order()                      │
│  (SAME INTERFACE)                                            │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Components

### 1. HistoricalTickReplayer

Replays historical ticks in chronological order, mimicking live WebSocket flow.

**Features:**
- Loads from Zerodha API (`kite.historical_data()`)
- Loads from CSV (BankNifty 1-minute format)
- Generates synthetic data for testing
- Converts OHLC candles to multiple ticks (simulates intra-candle movement)
- Replays at configurable speed (0 = instant, 1 = real-time, 2 = 2x speed)

**Usage with Zerodha API:**
```python
from market_data.adapters.historical_tick_replayer import HistoricalTickReplayer
from market_data.store import InMemoryMarketStore
from kiteconnect import KiteConnect
from datetime import date, timedelta

# Initialize Kite
kite = KiteConnect(api_key="...")
kite.set_access_token("...")

store = InMemoryMarketStore()
replayer = HistoricalTickReplayer(
    store=store,
    data_source="zerodha",  # Use Zerodha API
    speed=0.0,  # Instant replay
    kite=kite,
    instrument_symbol="NIFTY BANK",
    from_date=date.today() - timedelta(days=30),
    to_date=date.today(),
    interval="minute"  # or "5minute", "day", etc.
)

replayer.start()
# Ticks are automatically stored and callbacks called
```

**Usage with CSV:**
```python
replayer = HistoricalTickReplayer(
    store=store,
    data_source="data/banknifty_1min.csv",  # CSV file path
    speed=0.0
)
```

### 2. CandleBuilder

Aggregates ticks into OHLC bars. **Same code** used for live and historical.

**Features:**
- Supports multiple timeframes (1min, 5min, 15min, etc.)
- Emits OHLCBar when candle closes
- Callback support for real-time processing

**Usage:**
```python
from market_data.adapters.candle_builder import CandleBuilder
from market_data.contracts import MarketTick

def on_candle_close(candle):
    print(f"New candle: O={candle.open} H={candle.high} L={candle.low} C={candle.close}")

builder = CandleBuilder(
    timeframe="1min",
    on_candle_close=on_candle_close
)

# Process each tick
tick = MarketTick(instrument="BANKNIFTY", timestamp=..., last_price=45000, volume=1000)
closed_candle = builder.process_tick(tick)  # Returns OHLCBar if candle closed
```

### 3. PaperBroker

Mimics Zerodha Kite API for backtesting. **Same interface** as `kite.place_order()`.

**Features:**
- Identical API to Kite (`place_order()`, `orders()`, `positions()`, `margins()`)
- Tracks P&L, margins, positions
- Supports MARKET, LIMIT, SL orders
- Portfolio summary and reporting

**Usage:**
```python
from market_data.adapters.paper_broker import PaperBroker

broker = PaperBroker(initial_capital=1000000.0)

# Place order (same as kite.place_order())
result = broker.place_order(
    exchange="NFO",
    tradingsymbol="BANKNIFTY",
    transaction_type="BUY",
    quantity=15,
    product="MIS",
    order_type="MARKET"
)

# Get positions (same as kite.positions())
positions = broker.positions()

# Get orders (same as kite.orders())
orders = broker.orders()

# Get portfolio summary
summary = broker.get_portfolio_summary()
```

### 4. UnifiedDataFlow

Orchestrates the entire flow, making historical and live data indistinguishable.

**Usage:**
```python
from market_data.adapters.unified_data_flow import UnifiedDataFlow
from market_data.store import InMemoryMarketStore
from market_data.contracts import OHLCBar

def on_candle_close(candle: OHLCBar):
    # Your strategy logic here
    # This works identically for live and historical
    pass

store = InMemoryMarketStore()
flow = UnifiedDataFlow(
    store=store,
    data_source="data/banknifty_1min.csv",  # or "synthetic" or "live"
    on_candle_close=on_candle_close
)

flow.start()
# Data flows automatically
flow.stop()

# Get broker (paper or live)
broker = flow.get_broker()
```

## 📊 Data Sources

### Option 1: Zerodha API (Recommended)

Fetch historical data directly from Zerodha using `kite.historical_data()`:

```python
flow = UnifiedDataFlow(
    store=store,
    data_source="zerodha",
    kite=kite,
    instrument_symbol="NIFTY BANK",
    from_date=date(2024, 1, 1),
    to_date=date(2024, 1, 31),
    interval="minute"  # "minute", "5minute", "day", etc.
)
```

**Benefits:**
- ✅ Real market data
- ✅ No need to download/manage CSV files
- ✅ Always up-to-date
- ✅ Multiple intervals supported

### Option 2: CSV File

For historical data from CSV, use BankNifty 1-minute format:

```csv
Date,Time,Open,High,Low,Close,Volume
2024-01-15,09:15,45000,45100,44950,45050,1500000
2024-01-15,09:16,45050,45150,45000,45100,1600000
...
```

```python
flow = UnifiedDataFlow(
    store=store,
    data_source="data/banknifty_1min.csv"
)
```

### Option 3: CSV File (Recommended for Testing)

For testing and development, use CSV files with real historical data:

```python
flow = UnifiedDataFlow(
    store=store,
    data_source="path/to/historical_data.csv"
)
```

**Note**: Synthetic data generation has been removed. Use CSV files or Zerodha API for historical data.

The replayer automatically:
1. Fetches/parses data from source
2. Converts OHLC candles to multiple ticks (simulates intra-candle movement)
3. Replays ticks in chronological order

## 🔄 Data Flow Example

### Historical Backtesting with Zerodha API

```python
import asyncio
from datetime import date, timedelta
from kiteconnect import KiteConnect
from market_data.store import InMemoryMarketStore
from market_data.adapters.unified_data_flow import UnifiedDataFlow
from market_data.adapters.paper_broker import PaperBroker
from market_data.contracts import OHLCBar

# Initialize Kite
kite = KiteConnect(api_key="...")
kite.set_access_token("...")

# Create components
store = InMemoryMarketStore()
broker = PaperBroker(initial_capital=1000000.0)

def strategy_on_candle(candle: OHLCBar):
    """Your strategy - works for both live and historical."""
    if candle.close > candle.open:
        # Buy signal
        broker.place_order(
            exchange="NFO",
            tradingsymbol="BANKNIFTY",
            transaction_type="BUY",
            quantity=15,
            product="MIS",
            order_type="MARKET"
        )

# Create unified flow with Zerodha historical data
flow = UnifiedDataFlow(
    store=store,
    data_source="zerodha",  # Use Zerodha API
    on_candle_close=strategy_on_candle,
    paper_broker=broker,
    kite=kite,
    instrument_symbol="NIFTY BANK",
    from_date=date.today() - timedelta(days=30),
    to_date=date.today(),
    interval="minute"
)

# Run backtest
flow.start()
await asyncio.sleep(60)  # Let it run
flow.stop()

# Get results
print(broker.get_portfolio_summary())
```

### Historical Backtesting with CSV

```python
# Same code, just change data_source
flow = UnifiedDataFlow(
    store=store,
    data_source="data/banknifty_1min.csv",  # CSV file
    on_candle_close=strategy_on_candle,
    paper_broker=broker
)
```

### Live Trading (Same Code!)

```python
# Only change: data_source="live"
flow = UnifiedDataFlow(
    store=store,
    data_source="live",  # Uses Zerodha WebSocket
    on_candle_close=strategy_on_candle,  # SAME callback!
    # broker would be live Kite client
)
```

## ✅ Validation Checklist

Before trusting backtest results:

- [ ] Strategy works on live feed
- [ ] Same result in historical replay
- [ ] No lookahead bias (indicators use only past candles)
- [ ] Trades align with candle close timestamps
- [ ] Paper broker matches Kite API structure
- [ ] Time handling uses historical time, not `datetime.now()`

## 🎯 Key Benefits

1. **Code Reuse**: Same strategy code for live and historical
2. **Accurate Simulation**: Ticks → Candles → Indicators (same as live)
3. **Realistic Backtesting**: Intra-candle movement, proper timing
4. **Easy Validation**: Test strategies before going live
5. **No Lookahead Bias**: Uses only past data

## 📝 Notes

- **Time Handling**: Always use `tick.timestamp`, never `datetime.now()`
- **Candle Building**: Only calculate indicators on closed candles
- **Order Execution**: Paper broker uses current market price (from ticks)
- **VWAP**: Resets daily (handled automatically by candle builder)

## 🚀 Next Steps

1. Download BankNifty 1-minute CSV data
2. Run `historical_backtest_example.py`
3. Adapt your strategy to use `on_candle_close` callback
4. Validate results
5. Deploy same code to live trading!


