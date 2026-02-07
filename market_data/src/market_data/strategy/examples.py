from __future__ import annotations

from typing import Dict, Any, Optional

from market_data.strategy.base import Strategy


class SimpleEMAStrategy(Strategy):
    """Example using pre-calculated EMA from TechnicalIndicatorsService."""

    def __init__(self, window: int = 20):
        self.window = window
        self.ema_key = f"ema_{window}"

    def on_new_candle(self, candle: Dict[str, Any], indicators: Optional[Dict[str, Any]] = None) -> None:
        close = candle.get("close")
        instrument = candle.get("instrument", "UNKNOWN")
        
        if not indicators or self.ema_key not in indicators:
            print(f"[{candle.get('timestamp')}] Waiting for {self.ema_key} indicator...")
            return
        
        ema = indicators[self.ema_key]
        if ema is None:
            return
        
        # Additional indicators available
        rsi = indicators.get('rsi_14')
        trend = indicators.get('trend_direction', 'UNKNOWN')
        
        if close > ema:
            signal = f"BUY {instrument} @ {close:.2f} (ema={ema:.2f})"
            if rsi:
                signal += f", RSI={rsi:.1f}"
            signal += f", trend={trend}"
            print(signal)
        else:
            signal = f"SELL {instrument} @ {close:.2f} (ema={ema:.2f})"
            if rsi:
                signal += f", RSI={rsi:.1f}"
            signal += f", trend={trend}"
            print(signal)


__all__ = ["SimpleEMAStrategy"]
