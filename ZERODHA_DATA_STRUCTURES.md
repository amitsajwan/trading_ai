# Zerodha Data Structures

This document outlines the data structures fetched from Zerodha Kite API and used in the trading system.

## Overview

The system fetches the following types of data from Zerodha:
1. **Market Tick Data** - Real-time price updates
2. **OHLC Bar Data** - Historical candlestick data
3. **Options Chain Data** - Options prices, OI, and Greeks
4. **Account/Margins Data** - Trading account balances and margins
5. **Instruments Data** - Instrument metadata and tokens

---

## 1. Market Tick Data

### Source APIs
- `kite.ltp(instruments)` - Last Traded Price (REST)
- WebSocket tick stream (real-time)

### Data Structure: `MarketTick`

```python
@dataclass
class MarketTick:
    """Simple tick payload for the latest price."""
    instrument: str          # e.g., "BANKNIFTY", "NIFTY BANK"
    timestamp: datetime       # When the tick occurred
    last_price: float        # Last traded price
    volume: Optional[int]    # Volume traded (if available)
```

### Example from `kite.ltp()`

```python
# API Call
instruments = ["NSE:NIFTY BANK"]
ltp_data = kite.ltp(instruments)

# Response Structure
{
    "NSE:NIFTY BANK": {
        "last_price": 45050.0,
        "volume": 1500000,
        # Additional fields may include:
        # "ohlc": {"open": 45000, "high": 45100, "low": 44950, "close": 45050},
        # "net_change": 50.0,
        # "timestamp": "2024-01-15T09:30:00+05:30"
    }
}
```

### Usage in Code
- Stored in `MarketStore` via `store_tick()`
- Retrieved via `get_latest_tick(instrument)`
- Used for real-time price updates in dashboard

---

## 2. OHLC Bar Data

### Source API
- `kite.historical_data(instrument_token, from_date, to_date, interval)`

### Data Structure: `OHLCBar`

```python
@dataclass
class OHLCBar:
    """Aggregated OHLC bar for a timeframe."""
    instrument: str          # e.g., "BANKNIFTY"
    timeframe: str           # e.g., "1min", "5min", "1day"
    open: float              # Opening price
    high: float              # Highest price
    low: float               # Lowest price
    close: float             # Closing price
    volume: Optional[int]    # Total volume
    start_at: datetime       # Bar start timestamp
```

### Example from `kite.historical_data()`

```python
# API Call
instrument_token = 26009  # BANKNIFTY token
from_date = datetime(2024, 1, 1)
to_date = datetime(2024, 1, 15)
interval = "5minute"  # or "minute", "day", etc.

historical_data = kite.historical_data(
    instrument_token, from_date, to_date, interval
)

# Response Structure (list of candles)
[
    {
        "date": datetime(2024, 1, 1, 9, 15, 0),
        "open": 45000.0,
        "high": 45100.0,
        "low": 44950.0,
        "close": 45050.0,
        "volume": 1500000,
        "oi": 2500000  # Open Interest (for futures/options)
    },
    # ... more candles
]
```

### Timeframe Options
- `"minute"` - 1 minute candles
- `"3minute"` - 3 minute candles
- `"5minute"` - 5 minute candles
- `"15minute"` - 15 minute candles
- `"30minute"` - 30 minute candles
- `"60minute"` - 1 hour candles
- `"day"` - Daily candles

### Usage in Code
- Stored in `MarketStore` via `store_ohlc()`
- Retrieved via `get_ohlc(instrument, timeframe, limit)`
- Used for technical indicator calculations

---

## 3. Options Chain Data

### Source APIs
- `kite.instruments("NFO")` - Get all NFO instruments
- `kite.quote([tokens])` - Get quotes for option tokens

### Data Structure: Options Chain Response

```python
{
    "available": bool,           # Whether data is available
    "futures_price": float,      # Current futures price
    "strikes": {
        strike_price: {
            "ce_ltp": float,     # Call option last traded price
            "pe_ltp": float,     # Put option last traded price
            "ce_oi": int,        # Call option open interest
            "pe_oi": int,        # Put option open interest
            "ce_volume": int,    # Call option volume (if available)
            "pe_volume": int,    # Put option volume (if available)
            # Additional fields from quote() may include:
            # "ce_iv": float,    # Call implied volatility
            # "pe_iv": float,    # Put implied volatility
            # "ce_greeks": {...}, # Call Greeks (delta, gamma, theta, vega)
            # "pe_greeks": {...}  # Put Greeks
        },
        # ... more strikes
    }
}
```

### Example Flow

```python
# Step 1: Get instruments
nfo_instruments = kite.instruments("NFO")

# Instrument structure:
{
    "tradingsymbol": "BANKNIFTY24JAN45000CE",
    "segment": "NFO-OPT",
    "instrument_type": "CE",  # or "PE", "FUT"
    "strike": 45000,
    "expiry": date(2024, 1, 25),
    "instrument_token": 1001,
    "exchange": "NFO",
    "name": "BANKNIFTY",
    "lot_size": 15,
    "tick_size": 0.05
}

# Step 2: Get quotes for option tokens
option_tokens = [1001, 1002]  # CE and PE tokens
quotes = kite.quote(option_tokens)

# Quote structure:
{
    "1001": {  # Call option
        "last_price": 150.0,
        "oi": 10000,
        "volume": 500,
        "bid": 149.5,
        "ask": 150.5,
        "bid_qty": 100,
        "ask_qty": 100,
        "timestamp": datetime(...),
        # Greeks (if available):
        # "greeks": {
        #     "delta": 0.5,
        #     "gamma": 0.01,
        #     "theta": -0.5,
        #     "vega": 0.2
        # },
        # "iv": 0.15  # Implied volatility
    },
    "1002": {  # Put option
        "last_price": 120.0,
        "oi": 8000,
        "volume": 400,
        # ... similar structure
    }
}
```

### Usage in Code
- Fetched via `fetch_options_chain(strikes=None)`
- Used for options trading strategies
- Supports strike filtering: `fetch_options_chain(strikes=[45000, 45100])`

---

## 4. Account/Margins Data

### Source API
- `kite.margins()`

### Data Structure

```python
{
    "equity": {
        "enabled": bool,
        "net": float,              # Net margin available
        "available": {
            "cash": float,         # Cash available
            "opening_balance": float,
            "live_balance": float, # Live balance
            "collateral": float,
            "intraday_payin": float
        },
        "utilised": {
            "debits": float,
            "exposure": float,
            "m2m_unrealised": float,
            "m2m_realised": float,
            "option_premium": float,
            "span": float,
            "adhoc_margin": float,
            "notional_cash": float
        }
    },
    "commodity": { ... },  # Similar structure for commodity segment
    "currency": { ... }    # Similar structure for currency segment
}
```

### Usage in Code
- Used to check available balance for trading
- Accessed via `kite.margins()["equity"]["available"]["live_balance"]`

---

## 5. Instruments Data

### Source API
- `kite.instruments(exchange)`

### Data Structure

```python
[
    {
        "instrument_token": int,      # Unique token for API calls
        "exchange_token": str,        # Exchange-specific token
        "tradingsymbol": str,         # e.g., "NIFTY BANK", "BANKNIFTY24JAN45000CE"
        "name": str,                  # e.g., "NIFTY BANK", "BANKNIFTY"
        "last_price": float,          # Last traded price
        "expiry": date,               # Expiry date (for F&O)
        "strike": float,              # Strike price (for options)
        "tick_size": float,           # Minimum price movement
        "lot_size": int,              # Contract size
        "instrument_type": str,       # "EQ", "CE", "PE", "FUT"
        "segment": str,               # "NSE", "NFO-OPT", "NFO-FUT", etc.
        "exchange": str                # "NSE", "NFO", "BSE", etc.
    },
    # ... more instruments
]
```

### Common Exchanges
- `"NSE"` - National Stock Exchange (equity)
- `"NFO"` - NSE Futures & Options
- `"BSE"` - Bombay Stock Exchange
- `"CDS"` - Currency Derivatives
- `"MCX"` - Multi Commodity Exchange

### Usage in Code
- Used to find instrument tokens for API calls
- Used to filter instruments by type (CE, PE, FUT)
- Used to get expiry dates and strike prices

---

## 6. Additional API Methods Used

### `kite.profile()`
Returns user profile information:
```python
{
    "user_id": str,
    "user_name": str,
    "user_shortname": str,
    "email": str,
    "user_type": str,
    "broker": str,
    "exchanges": list[str],
    "products": list[str],
    "avatar_url": str,
    "meta": dict
}
```

### `kite.positions()`
Returns current positions:
```python
{
    "net": [
        {
            "tradingsymbol": str,
            "exchange": str,
            "instrument_token": int,
            "product": str,          # "MIS", "CNC", "NRML"
            "quantity": int,
            "average_price": float,
            "last_price": float,
            "pnl": float,
            "m2m": float,
            "buy_quantity": int,
            "sell_quantity": int
        }
    ],
    "day": [ ... ]  # Day positions
}
```

### `kite.orders()`
Returns order book:
```python
[
    {
        "order_id": str,
        "exchange_order_id": str,
        "tradingsymbol": str,
        "instrument_token": int,
        "transaction_type": str,     # "BUY", "SELL"
        "product": str,
        "order_type": str,           # "MARKET", "LIMIT", "SL", "SL-M"
        "quantity": int,
        "price": float,
        "trigger_price": float,
        "status": str,               # "COMPLETE", "OPEN", "REJECTED", etc.
        "filled_quantity": int,
        "pending_quantity": int,
        "order_timestamp": datetime,
        "exchange_timestamp": datetime
    }
]
```

---

## Data Flow Summary

```
┌─────────────────┐
│  Zerodha Kite   │
│      API        │
└────────┬────────┘
         │
         ├──► ltp() ──────────────► MarketTick
         ├──► historical_data() ──► OHLCBar
         ├──► quote() ────────────► Options Chain
         ├──► instruments() ──────► Instrument Metadata
         ├──► margins() ──────────► Account Balance
         ├──► positions() ────────► Current Positions
         └──► orders() ────────────► Order Book
```

---

## Notes for Historical Simulation

When simulating historical data, ensure your mock data structures match:

1. **MarketTick**: Must have `instrument`, `timestamp`, `last_price`, `volume`
2. **OHLCBar**: Must have `instrument`, `timeframe`, `open`, `high`, `low`, `close`, `volume`, `start_at`
3. **Options Chain**: Must have `available`, `futures_price`, `strikes` with `ce_ltp`, `pe_ltp`, `ce_oi`, `pe_oi`
4. **Instruments**: Must have `instrument_token`, `tradingsymbol`, `exchange`, `instrument_type`, `strike`, `expiry`
5. **Margins**: Must have `equity.available.live_balance` for balance checks

All timestamps should be timezone-aware (preferably IST: `+05:30`).


