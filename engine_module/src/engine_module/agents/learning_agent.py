"""Learning agent stub for model-based adjustments."""

from typing import Dict, Any
from engine_module.contracts import Agent, AnalysisResult


class LearningAgent(Agent):
    def __init__(self):
        self._agent_name = "LearningAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Not implemented: return neutral
        return AnalysisResult(decision="HOLD", confidence=0.5, details={"note": "learning agent stub"})
