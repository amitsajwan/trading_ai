"""Risk Manager agent: orchestrates risk debate between different risk perspectives."""

from typing import Dict, Any, List
from engine_module.contracts import Agent, AnalysisResult
import logging

logger = logging.getLogger(__name__)


class RiskManager(Agent):
    """Manages risk debate between different risk perspectives."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client  # For debate synthesis

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Run risk debate and synthesize risk assessment."""
        try:
            # Get analyses from different risk perspectives
            conservative_result = await self._get_conservative_analysis(context)
            aggressive_result = await self._get_aggressive_analysis(context)
            neutral_result = await self._get_neutral_analysis(context)

            # Conduct risk debate
            debate_result = await self._conduct_risk_debate(
                conservative_result, aggressive_result, neutral_result, context
            )

            # Synthesize final risk assessment
            final_risk = self._synthesize_risk_assessment(
                debate_result, conservative_result, aggressive_result, neutral_result
            )

            return AnalysisResult(
                decision=final_risk["decision"],
                confidence=final_risk["confidence"],
                details={
                    "conservative_view": conservative_result.details if conservative_result else {},
                    "aggressive_view": aggressive_result.details if aggressive_result else {},
                    "neutral_view": neutral_result.details if neutral_result else {},
                    "debate_summary": debate_result,
                    "risk_assessment": final_risk["assessment"]
                }
            )

        except Exception as e:
            logger.exception("Risk manager analysis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.7,  # Default to caution
                details={"error": str(e), "reason": "RISK_ERROR"}
            )

    async def _get_conservative_analysis(self, context: Dict[str, Any]) -> AnalysisResult:
        """Get conservative risk analysis."""
        try:
            from engine_module.agents.risk_agents import ConservativeRiskAgent
            agent = ConservativeRiskAgent()
            return await agent.analyze(context)
        except Exception as e:
            logger.warning(f"Conservative risk analysis failed: {e}")
            return None

    async def _get_aggressive_analysis(self, context: Dict[str, Any]) -> AnalysisResult:
        """Get aggressive risk analysis."""
        try:
            from engine_module.agents.risk_agents import AggressiveRiskAgent
            agent = AggressiveRiskAgent()
            return await agent.analyze(context)
        except Exception as e:
            logger.warning(f"Aggressive risk analysis failed: {e}")
            return None

    async def _get_neutral_analysis(self, context: Dict[str, Any]) -> AnalysisResult:
        """Get neutral risk analysis."""
        try:
            from engine_module.agents.risk_agents import NeutralRiskAgent
            agent = NeutralRiskAgent()
            return await agent.analyze(context)
        except Exception as e:
            logger.warning(f"Neutral risk analysis failed: {e}")
            return None

    async def _conduct_risk_debate(self, conservative: AnalysisResult, aggressive: AnalysisResult,
                                 neutral: AnalysisResult, context: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct structured debate between risk perspectives."""
        debate_points = []

        # Conservative arguments
        if conservative and conservative.confidence > 0.5:
            debate_points.append(f"Conservative: {conservative.details.get('risk', 'High caution needed')}")

        # Aggressive arguments
        if aggressive and aggressive.confidence > 0.5:
            debate_points.append(f"Aggressive: {aggressive.details.get('risk', 'Accept higher risk for returns')}")

        # Neutral arguments
        if neutral and neutral.confidence > 0.5:
            debate_points.append(f"Neutral: {neutral.details.get('risk', 'Balanced risk approach')}")

        # Determine consensus
        confidences = []
        if conservative:
            confidences.append(("conservative", conservative.confidence))
        if aggressive:
            confidences.append(("aggressive", aggressive.confidence))
        if neutral:
            confidences.append(("neutral", neutral.confidence))

        if confidences:
            # Sort by confidence
            confidences.sort(key=lambda x: x[1], reverse=True)
            winner = confidences[0][0]
            summary = f"{winner.capitalize()} perspective leads the risk debate"
        else:
            winner = "neutral"
            summary = "No clear risk consensus"

        return {
            "debate_points": debate_points,
            "winner": winner,
            "summary": summary,
            "confidences": dict(confidences)
        }

    def _synthesize_risk_assessment(self, debate_result: Dict[str, Any],
                                  conservative: AnalysisResult, aggressive: AnalysisResult,
                                  neutral: AnalysisResult) -> Dict[str, Any]:
        """Synthesize final risk assessment from debate."""
        winner = debate_result.get("winner", "neutral")

        if winner == "conservative":
            return {
                "decision": "HOLD",  # Conservative bias towards caution
                "confidence": 0.8,
                "assessment": "High risk - proceed with caution or avoid"
            }
        elif winner == "aggressive":
            return {
                "decision": "APPROVE",  # Allow trade but with monitoring
                "confidence": 0.6,
                "assessment": "Acceptable risk - proceed with position sizing"
            }
        else:  # neutral
            return {
                "decision": "MONITOR",
                "confidence": 0.7,
                "assessment": "Moderate risk - monitor closely"
            }