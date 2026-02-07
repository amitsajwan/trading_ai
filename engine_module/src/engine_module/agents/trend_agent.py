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
            'adx_threshold': 18  # Reduced from 25 for more trend signals
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
        - optional 'research_thesis': dict with research manager's primary thesis
        """
        try:
            # Check for research thesis to align analysis
            research_thesis = context.get("research_thesis")
            if research_thesis:
                logger.debug(f"TrendAgent aligning with research thesis: {research_thesis.get('decision', 'UNKNOWN')}")
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

            # Calculate ATR for risk management
            try:
                atr_series = ta.atr(pd.Series(highs), pd.Series(lows), pd.Series(closes), length=14)
                atr_last = float(atr_series.iloc[-1]) if not atr_series.empty and not pd.isna(atr_series.iloc[-1]) else None
            except Exception:
                atr_last = None

            price_last = closes[-1]

            # Get position information from context
            current_positions = context.get('current_positions', [])
            has_long_position = context.get('has_long_position', False)
            has_short_position = context.get('has_short_position', False)

            # Trend signal logic with position awareness and research thesis alignment
            decision = "HOLD"
            confidence = 0.5
            reasoning = []
            thesis_bias = 0.0  # Neutral bias

            # Align with research thesis if available
            if research_thesis:
                thesis_decision = research_thesis.get('decision', '').upper()
                thesis_confidence = research_thesis.get('confidence', 0.5)
                if 'BUY' in thesis_decision or 'BULL' in thesis_decision:
                    thesis_bias = thesis_confidence * 0.2  # Boost bullish signals
                    reasoning.append(f"Research thesis supports bullish trend (bias +{thesis_bias:.2f})")
                elif 'SELL' in thesis_decision or 'BEAR' in thesis_decision:
                    thesis_bias = -thesis_confidence * 0.2  # Boost bearish signals
                    reasoning.append(f"Research thesis supports bearish trend (bias {thesis_bias:.2f})")

            # STRONG UPTREND
            if (price_last > ma_fast_last > ma_slow_last and adx_last > self.config['adx_threshold']):
                if has_long_position:
                    # Strong uptrend with existing long - add to position
                    decision = "BUY"
                    confidence = min(0.95, 0.75 + thesis_bias)
                    reasoning = [
                        f"Strong uptrend: Price {price_last:.2f} > MA{self.config['ma_fast']} {ma_fast_last:.2f} > MA{self.config['ma_slow']} {ma_slow_last:.2f}",
                        f"ADX {adx_last:.1f} > {self.config['adx_threshold']} (strong trend)",
                        "Adding to existing long position"
                    ]
                else:
                    # No position - open new
                    decision = "BUY"
                    confidence = min(0.95, 0.80 + thesis_bias)
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
                    confidence = min(0.95, 0.75 - thesis_bias)
                    reasoning = [
                        f"Strong downtrend: Price {price_last:.2f} < MA{self.config['ma_fast']} {ma_fast_last:.2f} < MA{self.config['ma_slow']} {ma_slow_last:.2f}",
                        f"ADX {adx_last:.1f} > {self.config['adx_threshold']} (strong trend)",
                        "Adding to existing short position"
                    ]
                else:
                    # No position - open new
                    decision = "SELL"
                    confidence = min(0.95, 0.80 - thesis_bias)
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

            # Calculate trend strength for reference
            trend_strength = abs(price_last - ma_fast_last) / ma_fast_last * 100 if ma_fast_last != 0 else 0

            # Analysis complete - trade parameters will be calculated by SignalCreationAgent

            # Analysis details (no trade parameters - those are for SignalCreationAgent)
            details = {
                "agent": self._agent_name,
                "strategy": "trend_following",
                "analysis": {
                    "trend_direction": "UP" if decision == "BUY" else "DOWN" if decision == "SELL" else "SIDEWAYS",
                    "trend_strength": trend_strength,
                    "adx_signal": adx_last > self.config['adx_threshold'],
                    "ma_alignment": "bullish" if price_last > ma_fast_last > ma_slow_last else "bearish" if price_last < ma_fast_last < ma_slow_last else "neutral"
                },
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
                "reasoning": " ".join(reasoning) if isinstance(reasoning, list) else reasoning
            }

            return AnalysisResult(
                decision=decision,
                confidence=confidence,
                details=details,
                agent=self._agent_name
            )

        except Exception as e:
            logger.exception(f"Error in {self._agent_name} analysis")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"reason": f"ANALYSIS_ERROR: {str(e)}", "agent": self._agent_name}
            )

    def _calculate_position_size(self, entry_price: float, stop_loss: float, risk_reward_ratio: float, adx_value: float) -> Dict[str, Any]:
        """Calculate position size based on risk management for trend following.

        Trend following uses different sizing logic than momentum:
        - Higher conviction in strong trends (ADX > 25)
        - Lower sizing in weak trends
        - Account for trend-following higher holding periods
        """
        if not entry_price or not stop_loss or risk_reward_ratio <= 0:
            return {"size_multiplier": 1.0, "risk_amount": 0, "reason": "insufficient_data"}

        # Risk per trade (trend following can afford slightly higher risk due to longer holding periods)
        risk_per_trade_pct = 0.015  # 1.5% vs 1% for momentum

        # Calculate stop loss distance
        risk_amount_per_unit = abs(entry_price - stop_loss)

        if risk_amount_per_unit <= 0:
            return {"size_multiplier": 1.0, "risk_amount": 0, "reason": "invalid_stop_loss"}

        # Calculate position size: risk_per_trade / risk_per_unit
        position_size_multiplier = risk_per_trade_pct / (risk_amount_per_unit / entry_price)

        # Adjust based on trend strength (ADX)
        if adx_value > 30:
            # Very strong trend - can afford larger position
            position_size_multiplier *= 1.3
        elif adx_value > 25:
            # Strong trend - slight increase
            position_size_multiplier *= 1.1
        elif adx_value < 20:
            # Weak trend - reduce position size
            position_size_multiplier *= 0.8

        # Cap position size at reasonable levels for trend following
        position_size_multiplier = min(position_size_multiplier, 2.5)  # Higher cap than momentum

        # Reduce size if risk-reward ratio is poor
        if risk_reward_ratio < 2.0:
            position_size_multiplier *= 0.8
        elif risk_reward_ratio > 4.0:
            position_size_multiplier *= 1.1  # Increase for excellent R:R

        return {
            "size_multiplier": round(position_size_multiplier, 2),
            "risk_amount_pct": risk_per_trade_pct,
            "trend_strength_adjustment": adx_value > 25,
            "max_size_cap": 2.5,
            "holding_period_expectation": "medium_to_long"  # Trend following holds longer
        }

