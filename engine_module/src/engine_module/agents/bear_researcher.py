"""Bear researcher agent: provides bearish thesis."""

from typing import Dict, Any
from engine_module.contracts import Agent, AnalysisResult


class BearResearcher(Agent):
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Provide a simple bearish thesis if market trending down
        technical = context.get("technical", {})
        trend = technical.get("trend_direction") if technical else None
        if trend == "DOWN":
            return AnalysisResult(decision="SELL", confidence=0.6, details={"thesis": "Downtrend"})
        return AnalysisResult(decision="HOLD", confidence=0.3, details={"thesis": "No strong bearish signal"})