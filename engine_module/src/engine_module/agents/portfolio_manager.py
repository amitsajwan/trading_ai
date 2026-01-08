"""Portfolio manager agent that computes final signal based on agent inputs."""

from typing import Dict, Any
import logging

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class PortfolioManagerAgent(Agent):
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # context expected to include agent outputs: technical, sentiment, macro, fundamental
        technical = context.get("technical", {})
        sentiment = context.get("sentiment", {})
        macro = context.get("macro", {})

        # Simple voting: BUY if two or more agents bullish, SELL if two or more bearish
        votes = {"BUY": 0, "SELL": 0, "HOLD": 0}

        def vote_from(agent_out):
            bias = agent_out.get("bias") if agent_out else None
            if bias == "BULLISH":
                return "BUY"
            if bias == "BEARISH":
                return "SELL"
            return "HOLD"

        for a in (technical, sentiment, macro):
            v = vote_from(a)
            votes[v] += 1

        # Choose winner
        decision = max(votes, key=lambda k: votes[k])
        confidence = min(0.9, 0.4 + votes[decision] * 0.2)
        details = {"votes": votes}
        return AnalysisResult(decision=decision, confidence=confidence, details=details)

