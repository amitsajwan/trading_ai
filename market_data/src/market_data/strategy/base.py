from __future__ import annotations

from typing import Dict, Any, Optional


class Strategy:
    """Base class for trading strategies.

    Implement ``on_new_candle``; override ``on_tick`` if you want tick-level signals.
    This API is intentionally minimal so the same strategy can run in backtest,
    replay, or live modes without knowing the data source.
    
    Technical indicators are automatically calculated and passed to on_new_candle().
    Includes 40+ indicators: RSI, MACD, Bollinger Bands, ADX, ATR, etc.
    """

    def on_new_candle(self, candle: Dict[str, Any], indicators: Optional[Dict[str, Any]] = None) -> None:
        """Called when a new candle closes.

        Args:
            candle: dict with keys:
              - timestamp (datetime)
              - open, high, low, close (float)
              - volume (int)
              - instrument (str)
            indicators: dict with calculated technical indicators:
              - rsi_14, rsi_9: RSI values
              - macd_value, macd_signal, macd_histogram: MACD indicators
              - sma_10, sma_20, sma_50: Simple moving averages
              - ema_10, ema_20, ema_50: Exponential moving averages
              - bollinger_upper, bollinger_lower, bollinger_middle: Bollinger Bands
              - atr_14, atr_20: Average True Range
              - adx_14: Average Directional Index
              - stoch_k, stoch_d: Stochastic oscillator
              - obv: On Balance Volume
              - trend_direction: "UP", "DOWN", "SIDEWAYS"
              - trend_strength: 0-100 scale
              - rsi_status: "OVERSOLD", "OVERBOUGHT", "NEUTRAL"
              - volatility_level: "LOW", "MEDIUM", "HIGH"
              ...and 30+ more (see technical_indicators_service.py for full list)
        """
        raise NotImplementedError

    def on_tick(self, tick: Dict[str, Any]) -> None:
        """Optional tick-level callback (live mode)."""
        return None
