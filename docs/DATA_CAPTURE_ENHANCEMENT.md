# Data Capture Enhancement Plan

## Overview

Enhance data capture to include all available signals from Zerodha WebSocket, enabling more sophisticated analysis.

## Zerodha WebSocket MODE_FULL Tick Structure

According to Zerodha Kite Connect documentation, MODE_FULL provides:

```python
{
    "instrument_token": int,
    "last_price": float,
    "ohlc": {
        "open": float,
        "high": float,
        "low": float,
        "close": float
    },
    "volume": int,
    "average_price": float,
    "buy_quantity": int,
    "sell_quantity": int,
    "last_traded_price": float,
    "last_traded_quantity": int,
    "change": float,
    "net_change": float,
    "depth": {
        "buy": [
            {"price": float, "orders": int, "quantity": int},
            ...
        ],
        "sell": [
            {"price": float, "orders": int, "quantity": int},
            ...
        ]
    }
}
```

## Enhancement Implementation

### Phase 1: Enhanced Tick Capture

**File**: `data/ingestion_service.py`

**Changes**:
1. Capture all tick fields from MODE_FULL
2. Store bid/ask data
3. Calculate buy-sell imbalance
4. Track price changes

### Phase 2: Volume Analysis

**New File**: `data/volume_analyzer.py`

**Features**:
1. Volume profile calculation
2. Volume trend analysis
3. Volume confirmation signals
4. VWAP calculation

### Phase 3: Order Flow Analysis

**New File**: `data/order_flow_analyzer.py`

**Features**:
1. Buy-sell imbalance tracking
2. Bid-ask spread analysis
3. Market depth analysis
4. Order flow indicators

### Phase 4: Enhanced Agent State

**File**: `agents/state.py`

**Add Fields**:
- `bid_price`, `ask_price`
- `buy_quantity`, `sell_quantity`
- `bid_ask_spread`
- `buy_sell_imbalance`
- `volume_profile`
- `order_flow_signals`

## Benefits

1. **Better Order Flow Analysis**: Detect buying/selling pressure
2. **Volume Confirmation**: Confirm price moves with volume
3. **Market Depth Insights**: Understand order book dynamics
4. **More Accurate Signals**: Better entry/exit timing

## Priority

- **High**: Bid/Ask, Buy-Sell Imbalance
- **Medium**: Volume Profile, Order Flow
- **Low**: Full Market Depth Storage

