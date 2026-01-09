"""Research Manager agent: orchestrates bull/bear debate and synthesizes research."""

from typing import Dict, Any, List
from engine_module.contracts import Agent, AnalysisResult
import logging

logger = logging.getLogger(__name__)


class ResearchManager(Agent):
    """Manages research debate between bull and bear researchers."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client  # For debate synthesis

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Run research debate and synthesize conclusion."""
        try:
            # Get bull and bear analyses
            bull_result = await self._get_bull_analysis(context)
            bear_result = await self._get_bear_analysis(context)

            # Conduct debate
            debate_result = await self._conduct_debate(bull_result, bear_result, context)

            # Synthesize final research plan
            final_decision = self._synthesize_research(debate_result, bull_result, bear_result)

            return AnalysisResult(
                decision=final_decision["decision"],
                confidence=final_decision["confidence"],
                details={
                    "bull_thesis": bull_result.details if bull_result else {},
                    "bear_thesis": bear_result.details if bear_result else {},
                    "debate_summary": debate_result,
                    "research_plan": final_decision["plan"]
                }
            )

        except Exception as e:
            logger.exception("Research manager analysis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.3,
                details={"error": str(e), "reason": "RESEARCH_ERROR"}
            )

    async def _get_bull_analysis(self, context: Dict[str, Any]) -> AnalysisResult:
        """Get analysis from bull researcher."""
        try:
            from engine_module.agents.bull_researcher import BullResearcher
            bull_agent = BullResearcher()
            return await bull_agent.analyze(context)
        except Exception as e:
            logger.warning(f"Bull researcher failed: {e}")
            return None

    async def _get_bear_analysis(self, context: Dict[str, Any]) -> AnalysisResult:
        """Get analysis from bear researcher."""
        try:
            from engine_module.agents.bear_researcher import BearResearcher
            bear_agent = BearResearcher()
            return await bear_agent.analyze(context)
        except Exception as e:
            logger.warning(f"Bear researcher failed: {e}")
            return None

    async def _conduct_debate(self, bull_result: AnalysisResult, bear_result: AnalysisResult,
                            context: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct structured debate between bull and bear perspectives."""
        if not bull_result or not bear_result:
            return {"debate": "Incomplete - missing researcher input"}

        # Simple debate logic - can be enhanced with LLM
        bull_strength = bull_result.confidence
        bear_strength = bear_result.confidence

        debate_points = []

        # Bull arguments
        if bull_result.decision == "BUY":
            debate_points.append(f"Bull: Strong {bull_result.details.get('thesis', 'bullish signal')}")

        # Bear arguments
        if bear_result.decision == "SELL":
            debate_points.append(f"Bear: Strong {bear_result.details.get('thesis', 'bearish signal')}")

        # Determine winner
        if bull_strength > bear_strength:
            winner = "bull"
            summary = "Bullish perspective prevails in debate"
        elif bear_strength > bull_strength:
            winner = "bear"
            summary = "Bearish perspective prevails in debate"
        else:
            winner = "neutral"
            summary = "Balanced debate - no clear winner"

        return {
            "debate_points": debate_points,
            "winner": winner,
            "summary": summary,
            "bull_confidence": bull_strength,
            "bear_confidence": bear_strength
        }

    def _synthesize_research(self, debate_result: Dict[str, Any],
                           bull_result: AnalysisResult, bear_result: AnalysisResult) -> Dict[str, Any]:
        """Synthesize final research decision from debate - now for options strategies."""
        winner = debate_result.get("winner", "neutral")

        if winner == "bull" and bull_result and bull_result.decision != "HOLD":
            return {
                "decision": bull_result.decision,  # e.g., "BULL_CALL_SPREAD"
                "confidence": min(bull_result.confidence + 0.1, 0.9),
                "plan": f"Proceed with bullish options strategy: {bull_result.details.get('thesis', '')}"
            }
        elif winner == "bear" and bear_result and bear_result.decision != "HOLD":
            return {
                "decision": bear_result.decision,  # e.g., "BEAR_PUT_SPREAD"
                "confidence": min(bear_result.confidence + 0.1, 0.9),
                "plan": f"Proceed with bearish options strategy: {bear_result.details.get('thesis', '')}"
            }
        else:
            # Neutral - suggest iron condor for range-bound market
            return {
                "decision": "IRON_CONDOR",
                "confidence": 0.6,
                "plan": "Market range-bound - implement iron condor for premium collection"
            }