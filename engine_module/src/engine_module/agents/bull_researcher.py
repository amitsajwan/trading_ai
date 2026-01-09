"""Bull researcher agent: provides bullish thesis with memory and structured reporting."""

from typing import Dict, Any
from engine_module.contracts import Agent, AnalysisResult
from engine_module.utils.memory import AgentMemory
import logging

logger = logging.getLogger(__name__)


class BullResearcher(Agent):
    """Bull researcher providing bullish market analysis."""

    def __init__(self):
        self.memory = AgentMemory("bull_researcher")

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market for bullish opportunities."""
        try:
            symbol = context.get('symbol', 'UNKNOWN')
            technical = context.get('technical_indicators', {}) or context.get('technical', {})
            current_price = context.get('current_price', 0)

            # Get similar past situations
            situation_desc = f"Technical analysis for {symbol}: trend={technical.get('trend_direction')}, momentum={technical.get('momentum')}"
            past_experiences = self.memory.retrieve_similar(situation_desc, n_results=2)

            # Analyze bullish signals
            bullish_signals = self._identify_bullish_signals(technical)

            # Consider past experiences
            confidence_boost = 0.0
            if past_experiences:
                successful_buys = sum(1 for exp in past_experiences
                                    if exp["metadata"].get("outcome") == "profit"
                                    and exp["metadata"].get("decision") == "BUY")
                confidence_boost = min(successful_buys * 0.1, 0.2)

            # Make decision - now suggest options strategies
            if bullish_signals:
                confidence = min(0.6 + confidence_boost + len(bullish_signals) * 0.1, 0.9)
                decision = "BULL_CALL_SPREAD"  # Options strategy instead of simple BUY
                thesis = f"Bullish signals suggest call spread: {', '.join(bullish_signals)}"
            else:
                confidence = 0.3
                decision = "HOLD"
                thesis = "No strong bullish signals detected"

            # Store experience for future learning
            self.memory.store_experience(
                situation=situation_desc,
                decision=decision,
                outcome="pending",  # Will be updated later
                confidence=confidence,
                metadata={"signals": str(bullish_signals), "symbol": symbol}
            )

            return AnalysisResult(
                decision=decision,
                confidence=confidence,
                details={
                    "thesis": thesis,
                    "signals": bullish_signals,
                    "past_experiences_considered": len(past_experiences),
                    "confidence_boost": confidence_boost,
                    "report_type": "bullish_research"
                }
            )

        except Exception as e:
            logger.exception("Bull researcher analysis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"error": str(e), "report_type": "bullish_research"}
            )

    def _identify_bullish_signals(self, technical: Dict[str, Any]) -> list:
        """Identify bullish technical signals."""
        signals = []

        # Trend signals
        if technical.get('trend_direction') == 'UP':
            signals.append("uptrend confirmed")

        # Momentum signals
        if technical.get('rsi', 50) < 30:  # Oversold
            signals.append("RSI oversold")
        if technical.get('macd_signal') == 'BUY':
            signals.append("MACD bullish crossover")

        # Moving averages
        if technical.get('price_above_sma_50'):
            signals.append("price above 50 SMA")
        if technical.get('golden_cross'):
            signals.append("golden cross pattern")

        # Volume signals
        if technical.get('volume_trend') == 'INCREASING':
            signals.append("increasing volume")

        return signals
