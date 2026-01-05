"""Technical agent implementing engine_module Agent contract.

This is a migration of the legacy technical_agent into the new module and
exposes an async `analyze(context)` method returning `AnalysisResult`.
"""

import logging
from typing import Dict, Any, List
from dataclasses import asdict
import pandas as pd
import pandas_ta as ta

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class TechnicalAgent(Agent):
    """Simple technical agent that computes indicators and returns an AnalysisResult."""

    def __init__(self):
        """Initialize technical agent."""
        self._agent_name = "TechnicalAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze context and return AnalysisResult.

        Expected context keys:
        - 'ohlc': list[dict] where each dict has open/high/low/close[, timestamp]
        - optional 'current_price'
        """
        ohlc = context.get("ohlc", [])
        if not ohlc:
            return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": "INSUFFICIENT_DATA"})

        df = pd.DataFrame(ohlc)
        # Ensure required columns
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": f"MISSING_COLUMN_{col}"})

        # Clean and coerce types
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

        if df.empty:
            return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": "EMPTY_AFTER_CLEAN"})

        indicators = self._calculate_indicators(df)

        # Simple decision: combine trend + rsi
        trend = indicators.get("trend_direction", "SIDEWAYS")
        rsi_status = indicators.get("rsi_status", "NEUTRAL")

        decision = "HOLD"
        confidence = 0.5

        if trend == "UP" and rsi_status != "OVERBOUGHT":
            decision = "BUY"
            confidence = min(0.9, 0.5 + indicators.get("trend_strength", 0) / 200)
        elif trend == "DOWN" and rsi_status != "OVERSOLD":
            decision = "SELL"
            confidence = min(0.9, 0.5 + indicators.get("trend_strength", 0) / 200)

        details = indicators
        details["decision_basis"] = f"trend={trend}, rsi_status={rsi_status}"

        return AnalysisResult(decision=decision, confidence=confidence, details=details)

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate a small set of technical indicators."""
        indicators: Dict[str, Any] = {}
        data_length = len(df)

        try:
            # RSI (default 14 or shorter if insufficient data)
            rsi_period = min(14, max(2, data_length - 1))
            if data_length >= 2:
                rsi = ta.rsi(df["close"], length=rsi_period)
                indicators["rsi"] = float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else None
                if indicators["rsi"] is not None:
                    indicators["rsi_status"] = (
                        "OVERSOLD" if indicators["rsi"] < 30 else
                        "OVERBOUGHT" if indicators["rsi"] > 70 else
                        "NEUTRAL"
                    )
                else:
                    indicators["rsi_status"] = "NEUTRAL"
            else:
                indicators["rsi"] = None
                indicators["rsi_status"] = "NEUTRAL"
        except Exception as e:
            logger.warning(f"RSI calc failed: {e}")
            indicators["rsi"] = None
            indicators["rsi_status"] = "NEUTRAL"

        try:
            # ATR
            atr_period = min(14, max(2, data_length - 1))
            if data_length >= 2:
                atr = ta.atr(df["high"], df["low"], df["close"], length=atr_period)
                indicators["atr"] = float(atr.iloc[-1]) if not atr.empty and pd.notna(atr.iloc[-1]) else None
            else:
                indicators["atr"] = None
        except Exception as e:
            logger.warning(f"ATR calc failed: {e}")
            indicators["atr"] = None

        try:
            current_price = df["close"].iloc[-1]
            lookback = min(20, max(2, data_length))
            recent_lows = df["low"].tail(lookback).min()
            recent_highs = df["high"].tail(lookback).max()
            indicators["support_level"] = float(recent_lows)
            indicators["resistance_level"] = float(recent_highs)

            if data_length >= 5:
                sma_period = min(20, max(5, data_length // 2))
                sma = df["close"].tail(sma_period).mean()
                if current_price > sma * 1.01:
                    indicators["trend_direction"] = "UP"
                    indicators["trend_strength"] = min(100, ((current_price - sma) / sma * 100) * 2)
                elif current_price < sma * 0.99:
                    indicators["trend_direction"] = "DOWN"
                    indicators["trend_strength"] = min(100, ((sma - current_price) / current_price * 100) * 2)
                else:
                    indicators["trend_direction"] = "SIDEWAYS"
                    indicators["trend_strength"] = 30.0
            else:
                if data_length >= 2:
                    price_change = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]
                    if price_change > 0.01:
                        indicators["trend_direction"] = "UP"
                        indicators["trend_strength"] = min(100, abs(price_change) * 1000)
                    elif price_change < -0.01:
                        indicators["trend_direction"] = "DOWN"
                        indicators["trend_strength"] = min(100, abs(price_change) * 1000)
                    else:
                        indicators["trend_direction"] = "SIDEWAYS"
                        indicators["trend_strength"] = 30.0
                else:
                    indicators["trend_direction"] = "SIDEWAYS"
                    indicators["trend_strength"] = 30.0
        except Exception as e:
            logger.warning(f"Support/res calc failed: {e}")
            indicators["trend_direction"] = "SIDEWAYS"
            indicators["trend_strength"] = 30.0

        return indicators
