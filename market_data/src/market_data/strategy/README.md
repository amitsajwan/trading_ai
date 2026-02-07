# Strategy API

Event-driven trading strategy framework with **automatic technical indicators** that works seamlessly across:
- ✅ **Backtesting** (historical data)
- ✅ **Replay mode** (market closed simulation)
- ✅ **Live trading** (real-time WebSocket)

## Core Concept

Your strategy receives candle events + **40+ technical indicators** via callbacks. It never knows whether data is historical, simulated, or live.

```python
Strategy.on_new_candle(candle, indicators) ← Data source + indicators are transparent
```

## Quick Start

### 1. Create a Strategy

```python
from market_data.strategy import Strategy

class MyStrategy(Strategy):
    def on_new_candle(self, candle, indicators=None):
        """Called when a new candle closes with pre-calculated indicators."""
        
        if not indicators:
            print("Waiting for indicators...")
            return
        
        # Use pre-calculated indicators (no manual calculation needed!)
        rsi = indicators.get('rsi_14')
        ema_20 = indicators.get('ema_20')
        macd = indicators.get('macd_value')
        trend = indicators.get('trend_direction')
        
        if rsi and ema_20:
            if candle['close'] > ema_20 and rsi < 70:
                print(f"BUY @ {candle['close']} (RSI={rsi:.1f}, trend={trend})")
            elif candle['close'] < ema_20 and rsi > 30:
                print(f"SELL @ {candle['close']} (RSI={rsi:.1f}, trend={trend})")
```

### 2. Run Backtest/Replay

```python
from datetime import date
from market_data.strategy import StrategyRunner

runner = StrategyRunner(redis_host="localhost", redis_port=6380)
strategy = MyStrategy()

runner.run_backtest_sync(
    strategy=strategy,
    instrument="BANKNIFTY26FEBFUT",
    backtest_date=date(2026, 1, 28),
    interval="minute",
    speed=0.0  # 0 = instant, 1.0 = real-time
)
```

## Available Technical Indicators

Automatically calculated using `pandas_ta` library and passed to every `on_new_candle()` call:

**Trend Indicators:**
- `sma_10`, `sma_20`, `sma_50` - Simple Moving Averages
- `ema_10`, `ema_20`, `ema_50` - Exponential Moving Averages
- `wma_20` - Weighted Moving Average

**Momentum Indicators:**
- `rsi_14`, `rsi_9` - RSI (14 and 9 periods)
- `stoch_k`, `stoch_d` - Stochastic Oscillator
- `williams_r` - Williams %R
- `macd_value`, `macd_signal`, `macd_histogram` - MACD

**Volatility Indicators:**
- `bollinger_upper`, `bollinger_middle`, `bollinger_lower` - Bollinger Bands
- `bollinger_width`, `bollinger_percent_b` - BB width and %B
- `atr_14`, `atr_20` - Average True Range

**Trend Strength:**
- `adx_14` - Average Directional Index
- `di_plus`, `di_minus` - Directional Indicators
- `ichimoku_tenkan`, `ichimoku_kijun` - Ichimoku Cloud

**Volume Indicators:**
- `obv` - On Balance Volume
- `volume_sma_20` - Volume moving average
- `volume_rsi_14` - Volume RSI
- `cmf_20` - Chaikin Money Flow

**Oscillators:**
- `cci_20` - Commodity Channel Index
- `mfi_14` - Money Flow Index
- `roc_12` - Rate of Change
- `momentum_10` - Momentum

**Support/Resistance:**
- `pivot_point`, `pivot_r1`, `pivot_r2`, `pivot_s1`, `pivot_s2`
- `high_20`, `low_20`, `range_20` - 20-period price levels

**Derived Signals:**
- `trend_direction` - "UP", "DOWN", "SIDEWAYS"
- `trend_strength` - 0-100 scale
- `rsi_status` - "OVERSOLD", "OVERBOUGHT", "NEUTRAL"
- `volatility_level` - "LOW", "MEDIUM", "HIGH"
- `signal_strength` - Composite signal 0-100

## Candle Schema

```python
{
    "timestamp": datetime,      # Candle start time
    "open": float,             # Opening price
    "high": float,             # Highest price
    "low": float,              # Lowest price  
    "close": float,            # Closing price
    "volume": int,             # Volume traded
    "instrument": str          # Instrument symbol
}
```

## Indicators Schema

All indicators are optional. Available indicators:

```python
{
    # Trend
    "sma_10": float, "sma_20": float, "sma_50": float,
    "ema_10": float, "ema_20": float, "ema_50": float,
    
    # Momentum
    "rsi_14": float, "rsi_9": float,
    "macd_value": float, "macd_signal": float, "macd_histogram": float,
    "stoch_k": float, "stoch_d": float,
    
    # Volatility
    "bollinger_upper": float, "bollinger_lower": float, "bollinger_middle": float,
    "atr_14": float, "atr_20": float,
    
    # Trend Strength
    "adx_14": float, "di_plus": float, "di_minus": float,
    
    # Volume
    "obv": float, "volume_sma_20": float,
    
    # Signals
    "trend_direction": str,  # "UP", "DOWN", "SIDEWAYS"
    "trend_strength": float,  # 0-100
    "rsi_status": str,  # "OVERSOLD", "OVERBOUGHT", "NEUTRAL"
    "volatility_level": str,  # "LOW", "MEDIUM", "HIGH"
    
    # ... and 20+ more (see technical_indicators_service.py)
}
```

## Integration with Infrastructure

The strategy API leverages existing production infrastructure:

- **TechnicalIndicatorsService**: Calculates 40+ indicators using pandas_ta
- **HistoricalTickReplayer**: Provides candle callbacks for backtests
- **Redis Store**: Caches indicators and OHLC data
- **Market Data API**: Backend for live candle streams (future)

### How It Works

1. **Historical/Live data** flows through existing collectors
2. **TechnicalIndicatorsService** calculates indicators on every candle
3. **Indicators stored** in Redis (`indicators:{INSTRUMENT}:{name}`)
4. **Strategy callbacks** fetch latest indicators before calling `on_new_candle()`
5. **Your strategy** receives clean candle + indicators dict

```
Data Source → Candle Builder → TechnicalIndicatorsService
                                        ↓
                                   Redis Cache
                                        ↓
                        Strategy.on_new_candle(candle, indicators)
```

## Testing Your Strategy

```python
from datetime import date
from market_data.strategy import StrategyRunner
from market_data.strategy.examples import SimpleEMAStrategy

# Start historical mode first (in another terminal)
# python start_unified.py --historical --date 2026-01-28

# Run your strategy
runner = StrategyRunner(redis_port=6380)  # Historical mode port
strategy = SimpleEMAStrategy(window=20)

runner.run_backtest_sync(
    strategy=strategy,
    instrument="BANKNIFTY26FEBFUT",
    backtest_date=date(2026, 1, 28)
)
```

## Live Mode (Coming Soon)

```python
# Future: WebSocket integration with same strategy
runner = StrategyRunner(redis_port=6379)  # Live mode port
await runner.run_live(strategy=MyStrategy(), instrument="BANKNIFTY")
```
