"""Bull researcher agent: provides bullish thesis."""

from typing import Dict, Any
from engine_module.contracts import Agent, AnalysisResult


class BullResearcher(Agent):
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        technical = context.get("technical", {})
        trend = technical.get("trend_direction") if technical else None
        if trend == "UP":
            return AnalysisResult(decision="BUY", confidence=0.6, details={"thesis": "Uptrend"})
        return AnalysisResult(decision="HOLD", confidence=0.3, details={"thesis": "No strong bullish signal"})