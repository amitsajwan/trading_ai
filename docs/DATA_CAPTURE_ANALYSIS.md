# Data Capture Analysis

## Currently Captured Signals

### ✅ Price Data
- **Last Price**: `last_price` from ticks ✅
- **OHLC**: Calculated from ticks (Open, High, Low, Close) ✅
- **Current Price**: Stored in Redis for quick access ✅

### ✅ Volume Data
- **Tick Volume**: `volume` from each tick ✅
- **Candle Volume**: Aggregated volume in OHLC candles ✅

### ✅ Time Series Data
- **1-minute candles**: Last 60 candles ✅
- **5-minute candles**: Last 100 candles ✅
- **15-minute candles**: Last 100 candles ✅
- **Hourly candles**: Last 60 candles ✅
- **Daily candles**: Last 60 candles ✅

### ✅ Technical Indicators (Calculated)
- **RSI**: Relative Strength Index ✅
- **MACD**: Moving Average Convergence Divergence ✅
- **ATR**: Average True Range ✅
- **Support/Resistance**: Calculated from price levels ✅
- **Trend**: Direction and strength ✅

## Missing Signals (Available from Zerodha WebSocket)

### ❌ Order Flow Data
- **Bid Price**: Best bid price
- **Ask Price**: Best ask price
- **Bid Quantity**: Quantity at best bid
- **Ask Quantity**: Quantity at best ask
- **Bid-Ask Spread**: Spread calculation
- **Buy Quantity**: Total buy quantity
- **Sell Quantity**: Total sell quantity
- **Buy-Sell Imbalance**: Ratio/indicator

### ❌ Market Depth
- **Depth Data**: Full order book depth (5 levels)
- **Market Depth Analysis**: Support/resistance from depth

### ❌ Price Change Signals
- **Change**: Price change from previous close
- **Net Change**: Net change percentage
- **Average Price**: Volume-weighted average price

### ❌ Volume Analysis
- **Volume Profile**: Volume at different price levels
- **Volume Trends**: Volume momentum
- **Volume Confirmation**: Volume confirming price moves

### ❌ Advanced Signals
- **Tick-by-Tick Data**: Full tick history for analysis
- **Price Velocity**: Rate of price change
- **Volatility**: Real-time volatility from ticks

## Impact of Missing Data

### Current Limitations

1. **No Order Flow Analysis**
   - Cannot detect buying/selling pressure
   - Missing bid-ask spread analysis
   - Cannot identify market maker activity

2. **No Volume Profile**
   - Cannot identify high-volume price levels
   - Missing volume-based support/resistance
   - Cannot confirm breakouts with volume

3. **Limited Volume Analysis**
   - Only aggregate volume, not volume trends
   - Missing volume momentum indicators
   - Cannot detect volume divergences

4. **No Market Depth Insights**
   - Cannot see order book imbalance
   - Missing depth-based support/resistance
   - Cannot detect large orders

## Recommendations

### High Priority Enhancements

1. **Capture Bid/Ask Data**
   - Add bid/ask prices and quantities
   - Calculate bid-ask spread
   - Track buy-sell imbalance

2. **Volume Analysis**
   - Calculate volume profile
   - Track volume trends
   - Volume confirmation signals

3. **Order Flow Indicators**
   - Buy-sell quantity ratio
   - Order flow imbalance
   - Market depth analysis

### Medium Priority Enhancements

4. **Price Change Tracking**
   - Track change and net change
   - Calculate price velocity
   - Volatility from ticks

5. **Advanced Volume Metrics**
   - Volume-weighted average price (VWAP)
   - On-balance volume (OBV)
   - Volume rate of change

### Low Priority Enhancements

6. **Market Depth Storage**
   - Store full order book depth
   - Depth-based support/resistance
   - Large order detection

## Implementation Plan

See `DATA_CAPTURE_ENHANCEMENT.md` for implementation details.

