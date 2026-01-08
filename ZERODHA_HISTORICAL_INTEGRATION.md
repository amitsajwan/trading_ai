# Zerodha Historical Data Integration

## ✅ What Changed

The historical simulation system now supports fetching data directly from **Zerodha API** instead of just CSV files.

## 🎯 Usage

### Basic Example

```python
from datetime import date, timedelta
from kiteconnect import KiteConnect
from market_data.adapters.unified_data_flow import UnifiedDataFlow
from market_data.store import InMemoryMarketStore
from market_data.adapters.paper_broker import PaperBroker

# Initialize Kite
kite = KiteConnect(api_key="...")
kite.set_access_token("...")

# Create flow with Zerodha historical data
flow = UnifiedDataFlow(
    store=InMemoryMarketStore(),
    data_source="zerodha",  # Use Zerodha API
    kite=kite,
    instrument_symbol="NIFTY BANK",
    from_date=date.today() - timedelta(days=30),
    to_date=date.today(),
    interval="minute"  # "minute", "5minute", "day", etc.
)

flow.start()
# Data is automatically fetched and replayed
```

## 📊 Supported Data Sources

1. **Zerodha API** (`data_source="zerodha"`)
   - Fetches from `kite.historical_data()`
   - Requires: `kite`, `instrument_symbol`, `from_date`, `to_date`, `interval`
   - ✅ Real market data
   - ✅ No CSV files needed

2. **CSV File** (`data_source="path/to/file.csv"`)
   - Loads from local CSV file
   - ✅ Offline backtesting
   - ✅ Custom data sources

3. **Synthetic** (`data_source="synthetic"`)
   - Generates test data
   - ✅ Development and testing

## 🔧 API Parameters

### HistoricalTickReplayer

```python
HistoricalTickReplayer(
    store=store,
    data_source="zerodha",
    speed=0.0,  # Replay speed
    on_tick_callback=callback,
    kite=kite,  # KiteConnect instance
    instrument_symbol="NIFTY BANK",  # or "BANKNIFTY"
    from_date=date(2024, 1, 1),  # Start date
    to_date=date(2024, 1, 31),  # End date
    interval="minute"  # Data interval
)
```

### Supported Intervals

- `"minute"` - 1 minute candles
- `"3minute"` - 3 minute candles
- `"5minute"` - 5 minute candles
- `"15minute"` - 15 minute candles
- `"30minute"` - 30 minute candles
- `"60minute"` - 1 hour candles
- `"day"` - Daily candles

### Instrument Symbols

- `"NIFTY BANK"` - Index (NSE)
- `"BANKNIFTY"` - Futures (NFO, nearest expiry)
- Any valid Zerodha instrument symbol

## 🔄 Data Flow

```
Zerodha API (kite.historical_data())
    ↓
OHLC Candles (from Zerodha)
    ↓
Convert to Multiple Ticks (simulates intra-candle movement)
    ↓
MarketTick (SAME structure as live)
    ↓
CandleBuilder (SAME code)
    ↓
OHLCBar (SAME structure)
    ↓
Indicators → Strategy → Orders
```

## ✨ Key Features

1. **Automatic Instrument Token Resolution**
   - Automatically finds instrument token from symbol
   - Supports NSE (equity/index) and NFO (futures/options)

2. **OHLC to Ticks Conversion**
   - Converts each candle to multiple ticks
   - Simulates intra-candle price movement
   - Maintains realistic volume distribution

3. **Time Handling**
   - Uses historical timestamps from Zerodha
   - Proper timezone handling (IST)
   - Chronological ordering

4. **Same Interface**
   - Works identically with CSV or Zerodha API
   - Strategy code unchanged
   - Same data structures

## 📝 Example: Complete Backtest

See `data_niftybank/examples/zerodha_historical_backtest_example.py` for a complete working example.

## 🚀 Benefits

- ✅ **No CSV Management**: Fetch data directly from Zerodha
- ✅ **Real Market Data**: Actual historical prices
- ✅ **Multiple Intervals**: Support for various timeframes
- ✅ **Always Up-to-Date**: Latest data available
- ✅ **Same Code Path**: Identical to live trading

## 🔍 Notes

- Requires valid Kite API credentials
- Historical data availability depends on Zerodha API limits
- For futures, automatically selects nearest expiry
- Data is cached in memory during replay


