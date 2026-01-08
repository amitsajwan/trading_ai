"""Mean reversion agent implementing engine_module Agent contract.

Specialized agent for mean reversion signals using Bollinger Bands and RSI.
"""

import logging
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import pandas_ta as ta

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class MeanReversionAgent(Agent):
    """Mean reversion trading agent using Bollinger Bands and RSI."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize mean reversion agent with configuration."""
        self._agent_name = "MeanReversionAgent"
        self.config = config or {
            'bb_period': 20,
            'bb_std': 2.0,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market context and return mean reversion signal.

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
            if 'close' not in df.columns:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "MISSING_CLOSE_DATA", "agent": self._agent_name}
                )

            closes = df['close'].values

            # Calculate Bollinger Bands
            try:
                bb = ta.bbands(pd.Series(closes), length=self.config['bb_period'], std=self.config['bb_std'])
                if bb.empty or pd.isna(bb.iloc[-1]).any():
                    raise ValueError("BB calculation failed")

                bb_upper = float(bb.iloc[-1, 0])  # BBLU
                bb_middle = float(bb.iloc[-1, 1])  # BBM
                bb_lower = float(bb.iloc[-1, 2])  # BBL
            except Exception:
                # Fallback calculation
                sma = ta.sma(pd.Series(closes), length=self.config['bb_period'])
                std = pd.Series(closes).tail(self.config['bb_period']).std()
                bb_middle = float(sma.iloc[-1])
                bb_upper = bb_middle + (std * self.config['bb_std'])
                bb_lower = bb_middle - (std * self.config['bb_std'])

            # Calculate RSI
            rsi = ta.rsi(pd.Series(closes), length=self.config['rsi_period'])
            if rsi.empty or pd.isna(rsi.iloc[-1]):
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "RSI_CALC_FAILED", "agent": self._agent_name}
                )
            rsi_last = float(rsi.iloc[-1])

            price_last = closes[-1]

            # Mean reversion signal logic
            decision = "HOLD"
            confidence = 0.5
            reasoning = []

            # OVERSOLD BOUNCE (BUY)
            if (rsi_last < self.config['rsi_oversold'] and
                price_last < bb_lower):

                decision = "BUY"
                confidence = 0.65
                reasoning = [
                    f"RSI {rsi_last:.1f} < {self.config['rsi_oversold']} (oversold)",
                    f"Price {price_last:.2f} < BB lower {bb_lower:.2f}",
                    f"Expected mean reversion bounce toward middle BB {bb_middle:.2f}"
                ]

            # OVERBOUGHT FADE (SELL)
            elif (rsi_last > self.config['rsi_overbought'] and
                  price_last > bb_upper):

                decision = "SELL"
                confidence = 0.65
                reasoning = [
                    f"RSI {rsi_last:.1f} > {self.config['rsi_overbought']} (overbought)",
                    f"Price {price_last:.2f} > BB upper {bb_upper:.2f}",
                    f"Expected mean reversion pullback toward middle BB {bb_middle:.2f}"
                ]

            else:
                reasoning = ["No mean reversion opportunity identified"]
                confidence = 0.0

            # Calculate position levels
            if decision == "BUY":
                # Stop loss below lower BB, target at middle BB
                stop_loss = bb_lower - (bb_middle - bb_lower) * 0.5
                take_profit = bb_middle
            elif decision == "SELL":
                # Stop loss above upper BB, target at middle BB
                stop_loss = bb_upper + (bb_upper - bb_middle) * 0.5
                take_profit = bb_middle
            else:
                # Default levels
                stop_loss = price_last * 0.97
                take_profit = price_last * 1.03

            # Calculate band position
            band_position = (price_last - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

            details = {
                "agent": self._agent_name,
                "strategy": "mean_reversion",
                "indicators": {
                    "rsi": rsi_last,
                    "rsi_period": self.config['rsi_period'],
                    "rsi_oversold": self.config['rsi_oversold'],
                    "rsi_overbought": self.config['rsi_overbought'],
                    "bb_upper": bb_upper,
                    "bb_middle": bb_middle,
                    "bb_lower": bb_lower,
                    "bb_period": self.config['bb_period'],
                    "bb_std": self.config['bb_std'],
                    "band_position": band_position
                },
                "reasoning": reasoning,
                "entry_price": price_last,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_reward_ratio": abs(take_profit - price_last) / abs(price_last - stop_loss) if decision != "HOLD" else 0.0
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

