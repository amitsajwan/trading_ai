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
            'rsi_overbought': 70,    # Overbought = potential sell signal
            'rsi_oversold': 30,      # Oversold = potential buy signal
            'ma_period': 20,
            'volume_spike_threshold': 1.2,  # Reduced from 1.5 for more signals
            'min_price_move': 0.3    # Reduced from 0.5 for more signals
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market context and return momentum-based signal.

        Expected context keys:
        - 'technical_indicators': dict with pre-calculated indicators
        - 'current_price': current market price
        - optional 'current_positions': list of current positions
        - optional 'has_long_position': bool
        - optional 'has_short_position': bool
        - optional 'research_thesis': dict with research manager's primary thesis
        """
        try:
            # Check for research thesis to align analysis
            research_thesis = context.get("research_thesis")
            if research_thesis:
                logger.debug(f"MomentumAgent aligning with research thesis: {research_thesis.get('decision', 'UNKNOWN')}")
            # Get pre-calculated technical indicators
            tech_indicators = context.get("technical_indicators", {})
            current_price = context.get("current_price", 0)

            # Debug logging
            # logger.info(f"MomentumAgent: Context keys: {list(context.keys())}")
            # logger.info(f"MomentumAgent: tech_indicators keys: {list(tech_indicators.keys()) if tech_indicators else 'None'}")
            # logger.info(f"MomentumAgent: current_price: {current_price}")

            # Check if we have required indicators
            if not tech_indicators:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "NO_TECHNICAL_DATA", "agent": self._agent_name},
                    input_data={"technical_indicators_available": [], "current_price": current_price}
                )

            # Extract indicators
            rsi = tech_indicators.get('rsi_14', tech_indicators.get('rsi'))
            sma_20 = tech_indicators.get('sma_20')
            volume_ratio = tech_indicators.get('volume_ratio')
            price_change_pct = tech_indicators.get('price_change_pct')
            atr_14 = tech_indicators.get('atr_14', tech_indicators.get('atr'))

            # Multi-timeframe confirmation (if available)
            rsi_1h = tech_indicators.get('rsi_1h')
            sma_20_1h = tech_indicators.get('sma_20_1h')

            # Validate required indicators
            if rsi is None or sma_20 is None:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "MISSING_INDICATORS", "agent": self._agent_name},
                    input_data={"technical_indicators_available": list(tech_indicators.keys()), "rsi_available": rsi is not None, "sma_20_available": sma_20 is not None}
                )

            # Get position information from context
            current_positions = context.get('current_positions', [])
            has_long_position = context.get('has_long_position', False)
            has_short_position = context.get('has_short_position', False)

            # Determine volume spike from ratio
            vol_spike = volume_ratio and volume_ratio > self.config['volume_spike_threshold'] if volume_ratio else False

            # Momentum signal logic with position awareness and research thesis alignment
            decision = "HOLD"
            confidence = 0.5
            reasoning = []
            thesis_bias = 0.0  # Neutral bias

            # Align with research thesis if available
            if research_thesis:
                thesis_decision = research_thesis.get('decision', '').upper()
                thesis_confidence = research_thesis.get('confidence', 0.5)
                if 'BUY' in thesis_decision or 'BULL' in thesis_decision:
                    thesis_bias = thesis_confidence * 0.3  # Boost bullish signals
                    reasoning.append(f"Research thesis supports bullish momentum (bias +{thesis_bias:.2f})")
                elif 'SELL' in thesis_decision or 'BEAR' in thesis_decision:
                    thesis_bias = -thesis_confidence * 0.3  # Boost bearish signals
                    reasoning.append(f"Research thesis supports bearish momentum (bias {thesis_bias:.2f})")

            # BULLISH MOMENTUM (Fixed: RSI < oversold = buy signal)
            bullish_signal = (rsi < self.config['rsi_oversold'] and
                            current_price > sma_20 and
                            vol_spike and
                            price_change_pct and price_change_pct > self.config['min_price_move'])

            # Multi-timeframe confirmation (higher weight if 1h timeframe agrees)
            mtf_confirmed = False
            if rsi_1h and sma_20_1h and current_price:
                mtf_confirmed = (rsi_1h < self.config['rsi_oversold'] and current_price > sma_20_1h)
                if mtf_confirmed:
                    logger.debug(f"Multi-timeframe confirmation: 1h RSI {rsi_1h:.1f}, 1h SMA {sma_20_1h:.2f}")

            if bullish_signal:
                base_confidence = 0.75
                reasoning = [
                    f"RSI {rsi:.1f} < {self.config['rsi_oversold']} (oversold - potential bounce)",
                    f"Price {current_price:.2f} > SMA20 {sma_20:.2f}",
                    f"Volume spike: {volume_ratio:.1f}x average" if volume_ratio else "Volume spike detected",
                    f"Price move: {price_change_pct:.1f}%" if price_change_pct else ""
                ]

                # Boost confidence with multi-timeframe confirmation
                if mtf_confirmed:
                    base_confidence += 0.10
                    reasoning.append("[OK] Multi-timeframe (1h) confirmation")

                # Apply thesis bias to confidence
                adjusted_confidence = min(0.95, max(0.1, base_confidence + thesis_bias))

                # If we already have a long position, consider adding to it or holding
                if has_long_position:
                    decision = "BUY"  # Signal to add to position
                    confidence = adjusted_confidence * 0.9  # Slightly lower confidence when adding
                    reasoning.append("Adding to existing long position")
                else:
                    # No existing position - open new
                    decision = "BUY"
                    confidence = adjusted_confidence

            # BEARISH MOMENTUM (Fixed: RSI > overbought = sell signal)
            bearish_signal = (rsi > self.config['rsi_overbought'] and
                            current_price < sma_20 and
                            vol_spike and
                            price_change_pct and price_change_pct < -self.config['min_price_move'])

            # Multi-timeframe confirmation for bearish
            mtf_confirmed_bearish = False
            if rsi_1h and sma_20_1h and current_price:
                mtf_confirmed_bearish = (rsi_1h > self.config['rsi_overbought'] and current_price < sma_20_1h)

            elif bearish_signal:
                base_confidence = 0.75
                reasoning = [
                    f"RSI {rsi:.1f} > {self.config['rsi_overbought']} (overbought - potential rejection)",
                    f"Price {current_price:.2f} < SMA20 {sma_20:.2f}",
                    f"Volume spike: {volume_ratio:.1f}x average" if volume_ratio else "Volume spike detected",
                    f"Price move: {price_change_pct:.1f}%" if price_change_pct else ""
                ]

                # Boost confidence with multi-timeframe confirmation
                if mtf_confirmed_bearish:
                    base_confidence += 0.10
                    reasoning.append("[OK] Multi-timeframe (1h) confirmation")

                # Apply thesis bias to confidence
                adjusted_confidence = min(0.95, max(0.1, base_confidence - thesis_bias))  # Note: subtract for bearish

                # If we already have a short position, consider adding to it
                if has_short_position:
                    decision = "SELL"  # Signal to add to position
                    confidence = adjusted_confidence * 0.9  # Slightly lower confidence when adding
                    reasoning.append("Adding to existing short position")
                else:
                    # No existing short position - open new short
                    decision = "SELL"
                    confidence = adjusted_confidence

            # Prepare ATR-based stop loss and target levels (much better than fixed %)
            if atr_14 and atr_14 > 0:
                # ATR-based stop loss: 1.5 ATR (more volatile = wider stops)
                atr_multiplier = 1.5
                sl_distance = atr_14 * atr_multiplier
                # Ensure minimum stop distance
                min_stop_pct = 0.005  # 0.5% minimum
                min_stop_distance = current_price * min_stop_pct
                sl_distance = max(sl_distance, min_stop_distance)
            else:
                # Fallback to percentage-based if ATR not available
                sl_distance = abs(current_price * 0.015)  # 1.5% stop loss

            # Set stop loss and take profit based on direction
            if decision == "BUY":
                stop_loss = current_price - sl_distance
                take_profit = current_price + (sl_distance * 2.0)  # 2:1 reward:risk
            elif decision == "SELL":
                stop_loss = current_price + sl_distance
                take_profit = current_price - (sl_distance * 2.0)  # 2:1 reward:risk
            else:
                stop_loss = None
                take_profit = None

            # Calculate risk-reward metrics
            risk_amount = abs(current_price - stop_loss) if stop_loss else 0
            reward_amount = abs(take_profit - current_price) if take_profit else 0
            risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

            details = {
                "agent": self._agent_name,
                "strategy": "momentum",
                "indicators": {
                    "rsi": rsi,
                    "rsi_period": self.config['rsi_period'],
                    "rsi_1h": rsi_1h,
                    "sma_20": sma_20,
                    "sma_20_1h": sma_20_1h,
                    "volume_spike": vol_spike,
                    "volume_ratio": volume_ratio,
                    "price_change_pct": price_change_pct,
                    "atr_14": atr_14
                },
                "multi_timeframe": {
                    "confirmed": mtf_confirmed or mtf_confirmed_bearish,
                    "timeframes": ["1m", "1h"] if (rsi_1h and sma_20_1h) else ["1m"]
                },
                "reasoning": reasoning,
                "risk_reward_ratio": risk_reward_ratio,
                "position_size_suggestion": self._calculate_position_size(current_price, stop_loss, risk_reward_ratio)
            }

            # Collect input data used for analysis
            input_data = {
                "technical_indicators_available": list(tech_indicators.keys()),
                "current_price": current_price,
                "rsi_value": rsi,
                "sma_20_value": sma_20,
                "volume_ratio": volume_ratio,
                "price_change_pct": price_change_pct,
                "has_long_position": has_long_position,
                "has_short_position": has_short_position,
                "config": self.config
            }

            return AnalysisResult(
                decision=decision,
                confidence=confidence,
                details=details,
                agent=self._agent_name,
                input_data=input_data
            )

        except Exception as e:
            logger.exception(f"Error in {self._agent_name} analysis")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"reason": f"ANALYSIS_ERROR: {str(e)}", "agent": self._agent_name},
                input_data={"error_occurred": True, "context_keys": list(context.keys())}
            )

    def _calculate_position_size(self, entry_price: float, stop_loss: float, risk_reward_ratio: float) -> Dict[str, Any]:
        """Calculate position size based on risk management principles.

        Uses a simplified position sizing algorithm based on:
        - Risk per trade (default 1% of portfolio)
        - Risk-reward ratio
        - Stop loss distance
        """
        if not entry_price or not stop_loss or risk_reward_ratio <= 0:
            return {"size_multiplier": 1.0, "risk_amount": 0, "reason": "insufficient_data"}

        # Risk per trade (1% of portfolio by default)
        risk_per_trade_pct = 0.01

        # Calculate stop loss distance
        risk_amount_per_unit = abs(entry_price - stop_loss)

        if risk_amount_per_unit <= 0:
            return {"size_multiplier": 1.0, "risk_amount": 0, "reason": "invalid_stop_loss"}

        # Calculate position size: risk_per_trade / risk_per_unit
        # This gives us the number of units to trade to risk exactly risk_per_trade_pct
        position_size_multiplier = risk_per_trade_pct / (risk_amount_per_unit / entry_price)

        # Cap position size at reasonable levels
        position_size_multiplier = min(position_size_multiplier, 2.0)  # Max 2x normal size

        # Reduce size if risk-reward ratio is poor
        if risk_reward_ratio < 1.5:
            position_size_multiplier *= 0.7
        elif risk_reward_ratio > 3.0:
            position_size_multiplier *= 1.2  # Increase for better R:R

        return {
            "size_multiplier": round(position_size_multiplier, 2),
            "risk_amount_pct": risk_per_trade_pct,
            "risk_reward_adjustment": risk_reward_ratio >= 1.5,
            "max_size_cap": 2.0
        }

