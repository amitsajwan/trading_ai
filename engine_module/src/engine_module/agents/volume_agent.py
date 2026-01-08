"""Volume agent implementing engine_module Agent contract.

Specialized agent for volume confirmation signals.
"""

import logging
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import pandas_ta as ta

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class VolumeAgent(Agent):
    """Volume confirmation trading agent."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize volume agent with configuration."""
        self._agent_name = "VolumeAgent"
        self.config = config or {
            'volume_period': 20,
            'volume_spike_multiplier': 2.0,
            'price_move_threshold': 0.5,
            'rsi_period': 14
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market context and return volume-based signal.

        Expected context keys:
        - 'ohlc': list[dict] with open/high/low/close/volume[, timestamp]
        - optional 'current_price'
        - optional 'symbol'
        """
        try:
            ohlc_data = context.get("ohlc", [])
            if not ohlc_data or len(ohlc_data) < 25:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "INSUFFICIENT_DATA", "agent": self._agent_name}
                )

            # Convert to DataFrame
            df = pd.DataFrame(ohlc_data)
            if 'close' not in df.columns or 'volume' not in df.columns:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "MISSING_DATA", "agent": self._agent_name}
                )

            closes = df['close'].values
            volumes = df['volume'].values

            # Check for volume spike
            if len(volumes) < self.config['volume_period'] + 1:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "INSUFFICIENT_VOLUME_DATA", "agent": self._agent_name}
                )

            # Calculate volume average (excluding current period)
            vol_avg = volumes[-self.config['volume_period']-1:-1].mean()
            current_volume = volumes[-1]
            volume_spike = current_volume > (vol_avg * self.config['volume_spike_multiplier'])

            if not volume_spike:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={
                        "reason": "NO_VOLUME_SPIKE",
                        "agent": self._agent_name,
                        "current_volume": current_volume,
                        "avg_volume": vol_avg
                    }
                )

            # Calculate price movement
            price_move_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100

            # Must have significant price movement
            if abs(price_move_pct) < self.config['price_move_threshold']:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={
                        "reason": "INSUFFICIENT_PRICE_MOVE",
                        "agent": self._agent_name,
                        "price_move_pct": price_move_pct,
                        "threshold": self.config['price_move_threshold']
                    }
                )

            # Calculate RSI for confirmation
            rsi = ta.rsi(pd.Series(closes), length=self.config['rsi_period'])
            rsi_last = float(rsi.iloc[-1]) if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50.0

            # Volume confirmation signal
            price_last = closes[-1]
            direction = "BUY" if price_move_pct > 0 else "SELL"

            # Confidence based on volume spike magnitude and price move
            volume_ratio = current_volume / vol_avg
            confidence = min(0.70, 0.50 + (volume_ratio - 2.0) * 0.1 + abs(price_move_pct) * 0.02)

            # Calculate position levels based on recent swing
            lookback_period = min(10, len(closes) - 1)
            recent_highs = closes[-lookback_period:].max()
            recent_lows = closes[-lookback_period:].min()

            if direction == "BUY":
                stop_loss = recent_lows
                take_profit = price_last + (price_last - recent_lows) * 2
            else:
                stop_loss = recent_highs
                take_profit = price_last - (recent_highs - price_last) * 2

            reasoning = [
                f"Volume spike: {current_volume:,.0f} vs avg {vol_avg:,.0f} ({volume_ratio:.1f}x)",
                f"Price move: {price_move_pct:.1f}% {'up' if price_move_pct > 0 else 'down'}",
                f"RSI confirmation: {rsi_last:.1f}",
                f"Direction: {direction} with {confidence:.0%} confidence"
            ]

            details = {
                "agent": self._agent_name,
                "strategy": "volume_confirmation",
                "indicators": {
                    "volume_spike": volume_spike,
                    "current_volume": current_volume,
                    "avg_volume": vol_avg,
                    "volume_ratio": volume_ratio,
                    "price_move_pct": price_move_pct,
                    "rsi": rsi_last,
                    "rsi_period": self.config['rsi_period']
                },
                "reasoning": reasoning,
                "entry_price": price_last,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_reward_ratio": abs(take_profit - price_last) / abs(price_last - stop_loss)
            }

            return AnalysisResult(
                decision=direction,
                confidence=confidence,
                details=details
            )

        except Exception as e:
            logger.exception(f"Error in {self._agent_name} analysis")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"reason": f"ANALYSIS_ERROR: {str(e)}", "agent": self._agent_name}
            )

