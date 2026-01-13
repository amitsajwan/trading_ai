"""Agent Template

Copy this template when adding new agents. Keep agents side-effect free: return an AnalysisResult only.

Expected:
- Implement analyze(context: Dict[str, Any]) -> AnalysisResult
- Use `self._agent_name` to identify the agent
- Keep `details` as a dict; orchestrator will standardize result to include `agent` field

Context keys to document at top of agent file.
"""
from typing import Dict, Any
import logging

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class ExampleAgent(Agent):
    def __init__(self, config: Dict[str, Any] = None):
        self._agent_name = "ExampleAgent"
        self.config = config or {}

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Minimal analyze implementation.

        Expected context keys: 'ohlc', 'technical_indicators', 'current_price'
        Returns: AnalysisResult(decision, confidence, details=dict)
        """
        try:
            # Example: require technical indicators
            tech = context.get('technical_indicators', {})
            if not tech:
                return AnalysisResult(decision="HOLD", confidence=0.0, details={"reason": "NO_TECHNICAL_DATA"})

            # Implement agent logic here
            decision = "HOLD"
            confidence = 0.5
            details = {"summary": "Template agent - no action"}

            return AnalysisResult(decision=decision, confidence=confidence, details=details)

        except Exception as e:
            logger.exception("ExampleAgent failed")
            return AnalysisResult(decision="HOLD", confidence=0.0, details={"error": str(e)})