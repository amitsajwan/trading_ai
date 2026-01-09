"""Bear researcher agent: provides bearish thesis with memory and structured reporting."""

from typing import Dict, Any
from engine_module.contracts import Agent, AnalysisResult
from engine_module.utils.memory import AgentMemory
import logging

logger = logging.getLogger(__name__)


class BearResearcher(Agent):
    """Bear researcher providing bearish market analysis."""

    def __init__(self):
        self.memory = AgentMemory("bear_researcher")

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market for bearish risks."""
        try:
            symbol = context.get('symbol', 'UNKNOWN')
            technical = context.get('technical_indicators', {}) or context.get('technical', {})
            current_price = context.get('current_price', 0)

            # Get similar past situations
            situation_desc = f"Technical analysis for {symbol}: trend={technical.get('trend_direction')}, momentum={technical.get('momentum')}"
            past_experiences = self.memory.retrieve_similar(situation_desc, n_results=2)

            # Analyze bearish signals
            bearish_signals = self._identify_bearish_signals(technical)

            # Consider past experiences
            confidence_boost = 0.0
            if past_experiences:
                successful_sells = sum(1 for exp in past_experiences
                                     if exp["metadata"].get("outcome") == "profit"
                                     and exp["metadata"].get("decision") == "SELL")
                confidence_boost = min(successful_sells * 0.1, 0.2)

            # Make decision - now suggest options strategies
            if bearish_signals:
                confidence = min(0.6 + confidence_boost + len(bearish_signals) * 0.1, 0.9)
                decision = "BEAR_PUT_SPREAD"  # Options strategy instead of simple SELL
                thesis = f"Bearish signals suggest put spread: {', '.join(bearish_signals)}"
            else:
                confidence = 0.3
                decision = "HOLD"
                thesis = "No strong bearish signals detected"

            # Store experience for future learning
            self.memory.store_experience(
                situation=situation_desc,
                decision=decision,
                outcome="pending",  # Will be updated later
                confidence=confidence,
                metadata={"signals": str(bearish_signals), "symbol": symbol}
            )

            return AnalysisResult(
                decision=decision,
                confidence=confidence,
                details={
                    "thesis": thesis,
                    "signals": bearish_signals,
                    "past_experiences_considered": len(past_experiences),
                    "confidence_boost": confidence_boost,
                    "report_type": "bearish_research"
                }
            )

        except Exception as e:
            logger.exception("Bear researcher analysis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"error": str(e), "report_type": "bearish_research"}
            )

    def _identify_bearish_signals(self, technical: Dict[str, Any]) -> list:
        """Identify bearish technical signals."""
        signals = []

        # Trend signals
        if technical.get('trend_direction') == 'DOWN':
            signals.append("downtrend confirmed")

        # Momentum signals
        if technical.get('rsi', 50) > 70:  # Overbought
            signals.append("RSI overbought")
        if technical.get('macd_signal') == 'SELL':
            signals.append("MACD bearish crossover")

        # Moving averages
        if technical.get('price_below_sma_50'):
            signals.append("price below 50 SMA")
        if technical.get('death_cross'):
            signals.append("death cross pattern")

        # Volume signals
        if technical.get('volume_trend') == 'DECREASING':
            signals.append("decreasing volume")

        return signals
