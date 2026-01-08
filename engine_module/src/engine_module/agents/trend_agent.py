"""Trend agent implementing engine_module Agent contract.

Specialized agent for trend-following signals using moving averages and ADX.
"""

import logging
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import pandas_ta as ta

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class TrendAgent(Agent):
    """Trend-following trading agent using MA crossovers and ADX."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize trend agent with configuration."""
        self._agent_name = "TrendAgent"
        self.config = config or {
            'ma_fast': 20,
            'ma_slow': 50,
            'adx_period': 14,
            'adx_threshold': 25
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market context and return trend-based signal.

        Expected context keys:
        - 'ohlc': list[dict] with open/high/low/close/volume[, timestamp]
        - optional 'current_price'
        - optional 'symbol'
        - optional 'current_positions': list of current positions
        - optional 'has_long_position': bool
        - optional 'has_short_position': bool
        """
        try:
            ohlc_data = context.get("ohlc", [])
            if not ohlc_data or len(ohlc_data) < 55:  # Need enough data for slow MA + ADX
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "INSUFFICIENT_DATA", "agent": self._agent_name}
                )

            # Convert to DataFrame
            df = pd.DataFrame(ohlc_data)
            required_cols = ['open', 'high', 'low', 'close']
            if not all(col in df.columns for col in required_cols):
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "MISSING_OHLC_DATA", "agent": self._agent_name}
                )

            # Calculate moving averages
            closes = df['close'].values
            ma_fast = ta.sma(pd.Series(closes), length=self.config['ma_fast'])
            ma_slow = ta.sma(pd.Series(closes), length=self.config['ma_slow'])

            if ma_fast.empty or ma_slow.empty or pd.isna(ma_fast.iloc[-1]) or pd.isna(ma_slow.iloc[-1]):
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "MA_CALC_FAILED", "agent": self._agent_name}
                )

            ma_fast_last = float(ma_fast.iloc[-1])
            ma_slow_last = float(ma_slow.iloc[-1])

            # Calculate ADX
            highs = df['high'].values
            lows = df['low'].values

            try:
                adx = ta.adx(pd.Series(highs), pd.Series(lows), pd.Series(closes), length=self.config['adx_period'])
                adx_last = float(adx.iloc[-1]) if not adx.empty and not pd.isna(adx.iloc[-1]) else 25.0
            except Exception:
                adx_last = 25.0  # Neutral ADX

            price_last = closes[-1]

            # Get position information from context
            current_positions = context.get('current_positions', [])
            has_long_position = context.get('has_long_position', False)
            has_short_position = context.get('has_short_position', False)

            # Trend signal logic with position awareness
            decision = "HOLD"
            confidence = 0.5
            reasoning = []

            # STRONG UPTREND
            if (price_last > ma_fast_last > ma_slow_last and adx_last > self.config['adx_threshold']):
                if has_long_position:
                    # Strong uptrend with existing long - add to position
                    decision = "BUY"
                    confidence = 0.75
                    reasoning = [
                        f"Strong uptrend: Price {price_last:.2f} > MA{self.config['ma_fast']} {ma_fast_last:.2f} > MA{self.config['ma_slow']} {ma_slow_last:.2f}",
                        f"ADX {adx_last:.1f} > {self.config['adx_threshold']} (strong trend)",
                        "Adding to existing long position"
                    ]
                else:
                    # No position - open new
                    decision = "BUY"
                    confidence = 0.80
                    reasoning = [
                        f"Strong uptrend: Price {price_last:.2f} > MA{self.config['ma_fast']} {ma_fast_last:.2f} > MA{self.config['ma_slow']} {ma_slow_last:.2f}",
                        f"ADX {adx_last:.1f} > {self.config['adx_threshold']} (strong trend)",
                        f"MA alignment confirms uptrend direction"
                    ]

            # STRONG DOWNTREND
            elif (price_last < ma_fast_last < ma_slow_last and adx_last > self.config['adx_threshold']):
                if has_short_position:
                    # Strong downtrend with existing short - add to position
                    decision = "SELL"
                    confidence = 0.75
                    reasoning = [
                        f"Strong downtrend: Price {price_last:.2f} < MA{self.config['ma_fast']} {ma_fast_last:.2f} < MA{self.config['ma_slow']} {ma_slow_last:.2f}",
                        f"ADX {adx_last:.1f} > {self.config['adx_threshold']} (strong trend)",
                        "Adding to existing short position"
                    ]
                else:
                    # No position - open new
                    decision = "SELL"
                    confidence = 0.80
                    reasoning = [
                        f"Strong downtrend: Price {price_last:.2f} < MA{self.config['ma_fast']} {ma_fast_last:.2f} < MA{self.config['ma_slow']} {ma_slow_last:.2f}",
                        f"ADX {adx_last:.1f} > {self.config['adx_threshold']} (strong trend)",
                        f"MA alignment confirms downtrend direction"
                    ]

            else:
                # Check for weaker trend signals
                if price_last > ma_fast_last and adx_last > 20:
                    decision = "BUY"
                    confidence = 0.65
                    reasoning = ["Moderate uptrend signal"]
                elif price_last < ma_fast_last and adx_last > 20:
                    decision = "SELL"
                    confidence = 0.65
                    reasoning = ["Moderate downtrend signal"]
                else:
                    # Check for trend reversals that might signal exit
                    if has_long_position and price_last < ma_slow_last:
                        # Long position below slow MA - trend may be reversing
                        decision = "SELL"
                        confidence = 0.60
                        reasoning = [
                            f"Price {price_last:.2f} below slow MA {ma_slow_last:.2f}",
                            "Trend reversal - consider exiting long position"
                        ]
                    elif has_short_position and price_last > ma_slow_last:
                        # Short position above slow MA - trend may be reversing
                        decision = "BUY"
                        confidence = 0.60
                        reasoning = [
                            f"Price {price_last:.2f} above slow MA {ma_slow_last:.2f}",
                            "Trend reversal - consider exiting short position"
                        ]
                    else:
                        reasoning = ["No clear trend direction"]
                        confidence = 0.0

            # Calculate position management levels
            trend_strength = abs(price_last - ma_fast_last) / ma_fast_last * 100

            if decision == "BUY":
                stop_loss = ma_slow_last - (ma_slow_last * 0.005)  # 0.5% below slow MA
                take_profit = price_last + (price_last - stop_loss) * 2  # 2:1 reward ratio
            elif decision == "SELL":
                stop_loss = ma_slow_last + (ma_slow_last * 0.005)  # 0.5% above slow MA
                take_profit = price_last - (stop_loss - price_last) * 2  # 2:1 reward ratio
            else:
                stop_loss = price_last * 0.98  # Default 2% stop
                take_profit = price_last * 1.04  # Default 4% target

            details = {
                "agent": self._agent_name,
                "strategy": "trend_following",
                "indicators": {
                    "ma_fast": ma_fast_last,
                    "ma_fast_period": self.config['ma_fast'],
                    "ma_slow": ma_slow_last,
                    "ma_slow_period": self.config['ma_slow'],
                    "adx": adx_last,
                    "adx_period": self.config['adx_period'],
                    "adx_threshold": self.config['adx_threshold'],
                    "trend_strength_pct": trend_strength
                },
                "reasoning": reasoning,
                "entry_price": price_last,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_reward_ratio": 2.0 if decision != "HOLD" else 0.0
            }

            return AnalysisResult(
                decision=decision,
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

