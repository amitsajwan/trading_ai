"""Fundamental agent implementing simple fundamental checks."""

from typing import Dict, Any
import logging

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class FundamentalAgent(Agent):
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Inspect context for fundamentals (earnings, revenue growth)
        earnings = context.get("earnings_surprise")
        revenue = context.get("revenue_growth")

        # Simple heuristic
        if earnings is not None and earnings > 0.05:
            decision = "BUY"
            confidence = 0.6
        elif earnings is not None and earnings < -0.05:
            decision = "SELL"
            confidence = 0.6
        else:
            decision = "HOLD"
            confidence = 0.4

        details = {"earnings_surprise": earnings, "revenue_growth": revenue}
        return AnalysisResult(decision=decision, confidence=confidence, details=details)

