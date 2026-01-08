"""Review agent stub to summarize agent outputs."""

from typing import Dict, Any
import logging

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class ReviewAgent(Agent):
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Summarize existing analysis
        summary = {k: bool(v) for k, v in context.items() if k in ("technical", "sentiment", "macro", "fundamental")}
        return AnalysisResult(decision="HOLD", confidence=0.5, details={"summary": summary})
