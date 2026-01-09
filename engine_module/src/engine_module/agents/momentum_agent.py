"""Momentum agent implementing engine_module Agent contract.

Specialized agent for momentum-based trading signals using RSI and volume analysis.
"""

import logging
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import pandas_ta as ta

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class MomentumAgent(Agent):
    """Momentum-based trading agent using RSI + Volume analysis."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize momentum agent with configuration."""
        self._agent_name = "MomentumAgent"
        self.config = config or {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'ma_period': 20,
            'volume_spike_threshold': 1.5,
            'min_price_move': 0.5
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market context and return momentum-based signal.

        Expected context keys:
        - 'technical_indicators': dict with pre-calculated indicators
        - 'current_price': current market price
        - optional 'current_positions': list of current positions
        - optional 'has_long_position': bool
        - optional 'has_short_position': bool
        """
        try:
            # Get pre-calculated technical indicators
            tech_indicators = context.get("technical_indicators", {})
            current_price = context.get("current_price", 0)

            # Check if we have required indicators
            if not tech_indicators:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "NO_TECHNICAL_DATA", "agent": self._agent_name}
                )

            # Extract indicators
            rsi = tech_indicators.get('rsi')
            sma_20 = tech_indicators.get('sma_20')
            volume_ratio = tech_indicators.get('volume_ratio')
            price_change_pct = tech_indicators.get('price_change_pct')

            # Validate required indicators
            if rsi is None or sma_20 is None:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "MISSING_INDICATORS", "agent": self._agent_name}
                )

            # Get position information from context
            current_positions = context.get('current_positions', [])
            has_long_position = context.get('has_long_position', False)
            has_short_position = context.get('has_short_position', False)

            # Determine volume spike from ratio
            vol_spike = volume_ratio and volume_ratio > self.config['volume_spike_threshold'] if volume_ratio else False

            # Momentum signal logic with position awareness
            decision = "HOLD"
            confidence = 0.5
            reasoning = []

            # BULLISH MOMENTUM
            if (rsi > self.config['rsi_overbought'] and
                current_price > sma_20 and
                vol_spike and
                price_change_pct and price_change_pct > self.config['min_price_move']):

                # If we already have a long position, consider adding to it or holding
                if has_long_position:
                    # Strong momentum with existing position - could add or hold
                    decision = "BUY"  # Signal to add to position
                    confidence = 0.70  # Slightly lower confidence when adding
                    reasoning = [
                        f"RSI {rsi:.1f} > {self.config['rsi_overbought']} (strong momentum)",
                        f"Price {current_price:.2f} > SMA20 {sma_20:.2f}",
                        f"Volume spike: {volume_ratio:.1f}x average" if volume_ratio else "Volume spike detected",
                        f"Price move: {price_change_pct:.1f}%",
                        "Adding to existing long position"
                    ]
                else:
                    # No existing position - open new
                    decision = "BUY"
                    confidence = 0.75
                    reasoning = [
                        f"RSI {rsi:.1f} > {self.config['rsi_overbought']} (overbought momentum)",
                        f"Price {current_price:.2f} > SMA20 {sma_20:.2f}",
                        f"Volume spike: {volume_ratio:.1f}x average" if volume_ratio else "Volume spike detected",
                        f"Price move: {price_change_pct:.1f}%" if price_change_pct else ""
                    ]

            # BEARISH MOMENTUM
            elif (rsi < self.config['rsi_oversold'] and
                  current_price < sma_20 and
                  vol_spike and
                  price_change_pct and price_change_pct < -self.config['min_price_move']):

                # If we already have a short position, consider adding to it
                if has_short_position:
                    decision = "SELL"  # Signal to add to position
                    confidence = 0.70
                    reasoning = [
                        f"RSI {rsi:.1f} < {self.config['rsi_oversold']} (strong momentum)",
                        f"Price {current_price:.2f} < SMA20 {sma_20:.2f}",
                        f"Volume spike: {volume_ratio:.1f}x average" if volume_ratio else "Volume spike detected",
                        f"Price move: {price_change_pct:.1f}%",
                        "Adding to existing short position"
                    ]
                else:
                    # Check if we should exit existing positions due to momentum reversal
                    if has_long_position and rsi and rsi < 50:
                        # Long position losing momentum - consider exit
                        decision = "SELL"
                        confidence = 0.60
                        reasoning = [
                            f"Momentum weakening: RSI {rsi:.1f}",
                            "Consider exiting long position"
                        ]
                    elif has_short_position and rsi and rsi > 50:
                        # Short position losing momentum - consider exit
                        decision = "BUY"
                        confidence = 0.60
                        reasoning = [
                            f"Momentum weakening: RSI {rsi:.1f}",
                            "Consider exiting short position"
                        ]
                    else:
                        reasoning = ["No strong momentum signal identified"]
                        confidence = 0.0

            # Prepare stop loss and target levels
            sl_distance = abs(current_price * 0.01)  # 1% stop loss
            stop_loss = current_price - sl_distance if decision == "BUY" else current_price + sl_distance
            take_profit = current_price + (sl_distance * 1.5) if decision == "BUY" else current_price - (sl_distance * 1.5)

            details = {
                "agent": self._agent_name,
                "strategy": "momentum",
                "indicators": {
                    "rsi": rsi,
                    "rsi_period": self.config['rsi_period'],
                    "sma_20": sma_20,
                    "volume_spike": vol_spike,
                    "volume_ratio": volume_ratio,
                    "price_change_pct": price_change_pct
                },
                "reasoning": reasoning,
                "entry_price": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_reward_ratio": 1.5
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

