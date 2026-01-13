"""Enhanced Research Manager with Formal Debate Protocol.

This module provides an enhanced research manager that uses the formal
debate protocol to conduct structured debates between bull and bear researchers.
"""

import logging
from typing import Dict, Any, List, Optional

from engine_module.contracts import Agent, AnalysisResult
from engine_module.communication import (
    DebateProtocol,
    ArgumentType,
    ReportEvidence,
    EvidenceType
)

logger = logging.getLogger(__name__)


class EnhancedResearchManager(Agent):
    """Enhanced research manager with formal debate protocol.
    
    This manager orchestrates formal debates between bull and bear researchers
    using the DebateProtocol for structured argumentation.
    """
    
    def __init__(self, llm_client=None, config: Optional[Dict[str, Any]] = None):
        """Initialize enhanced research manager.
        
        Args:
            llm_client: Optional LLM client for debate synthesis
            config: Configuration dictionary with:
                - max_rounds: Maximum debate rounds (default: 3)
                - min_confidence_threshold: Minimum confidence for winner (default: 0.6)
        """
        self.llm_client = llm_client
        self.config = config or {}
        self._agent_name = "EnhancedResearchManager"
        
        # Store config for creating protocol instances per debate
        self._max_rounds = self.config.get('max_rounds', 3)
        self._min_confidence = self.config.get('min_confidence_threshold', 0.6)
        
        logger.debug(f"EnhancedResearchManager initialized: max_rounds={self._max_rounds}, "
                    f"min_confidence={self._min_confidence}")
    
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Run formal debate between bull and bear researchers.
        
        Args:
            context: Analysis context with market data, positions, etc.
        
        Returns:
            AnalysisResult with synthesized decision from debate
        """
        try:
            # Get bull and bear analyses
            bull_result = await self._get_bull_analysis(context)
            bear_result = await self._get_bear_analysis(context)
            
            if not bull_result or not bear_result:
                logger.warning("Missing bull or bear analysis, returning HOLD")
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.3,
                    details={
                        "reason": "INCOMPLETE_ANALYSIS",
                        "bull_result": bull_result is not None,
                        "bear_result": bear_result is not None
                    },
                    agent=self._agent_name
                )
            
            # Conduct formal debate
            debate_result = await self._conduct_formal_debate(
                bull_result, bear_result, context
            )
            
            # Synthesize final decision
            final_decision = self._synthesize_from_debate(debate_result, bull_result, bear_result)
            
            return AnalysisResult(
                decision=final_decision["decision"],
                confidence=final_decision["confidence"],
                details={
                    "bull_thesis": bull_result.details if bull_result else {},
                    "bear_thesis": bear_result.details if bear_result else {},
                    "debate_result": debate_result.to_dict(),
                    "winner": debate_result.winner,
                    "consensus": debate_result.consensus,
                    "research_plan": final_decision.get("plan", "")
                },
                agent=self._agent_name
            )
        
        except Exception as e:
            logger.exception("Enhanced research manager analysis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.3,
                details={"error": str(e), "reason": "RESEARCH_ERROR"},
                agent=self._agent_name
            )
    
    async def _get_bull_analysis(self, context: Dict[str, Any]) -> Optional[AnalysisResult]:
        """Get analysis from bull researcher."""
        try:
            from engine_module.agents.bull_researcher import BullResearcher
            bull_agent = BullResearcher()
            return await bull_agent.analyze(context)
        except Exception as e:
            logger.warning(f"Bull researcher failed: {e}")
            return None
    
    async def _get_bear_analysis(self, context: Dict[str, Any]) -> Optional[AnalysisResult]:
        """Get analysis from bear researcher."""
        try:
            from engine_module.agents.bear_researcher import BearResearcher
            bear_agent = BearResearcher()
            return await bear_agent.analyze(context)
        except Exception as e:
            logger.warning(f"Bear researcher failed: {e}")
            return None
    
    async def _conduct_formal_debate(
        self,
        bull_result: AnalysisResult,
        bear_result: AnalysisResult,
        context: Dict[str, Any]
    ):
        """Conduct formal debate using DebateProtocol.
        
        Args:
            bull_result: Bull researcher analysis
            bear_result: Bear researcher analysis
            context: Analysis context
        
        Returns:
            DebateResult object
        """
        # Create a new debate protocol instance for this debate
        debate_protocol = DebateProtocol(
            max_rounds=self._max_rounds,
            min_confidence_threshold=self._min_confidence
        )
        
        # Register participants
        bull_participant = debate_protocol.register_participant(
            "BullResearcher",
            "bull"
        )
        
        bear_participant = debate_protocol.register_participant(
            "BearResearcher",
            "bear"
        )
        
        # Prepare initial arguments
        bull_thesis = bull_result.details.get('thesis', '') if bull_result.details else ''
        bull_reasoning = bull_result.details.get('reasoning', '') if bull_result.details else ''
        if not bull_reasoning and bull_result.details:
            # Try to extract reasoning from details
            bull_reasoning = str(bull_result.details)
        
        bear_thesis = bear_result.details.get('thesis', '') if bear_result.details else ''
        bear_reasoning = bear_result.details.get('reasoning', '') if bear_result.details else ''
        if not bear_reasoning and bear_result.details:
            bear_reasoning = str(bear_result.details)
        
        # Build evidence from analysis results
        bull_evidence = []
        bear_evidence = []
        
        if bull_result.details:
            # Add technical indicators as evidence
            for key in ['rsi', 'macd', 'adx', 'volume_ratio']:
                value = bull_result.details.get(key)
                if value is not None:
                    bull_evidence.append(ReportEvidence(
                        type=EvidenceType.TECHNICAL_INDICATOR,
                        description=f"Bull evidence: {key}",
                        value=value,
                        source=f"BullResearcher_{key}",
                        confidence=bull_result.confidence * 0.9
                    ))
        
        if bear_result.details:
            for key in ['rsi', 'macd', 'adx', 'volume_ratio']:
                value = bear_result.details.get(key)
                if value is not None:
                    bear_evidence.append(ReportEvidence(
                        type=EvidenceType.TECHNICAL_INDICATOR,
                        description=f"Bear evidence: {key}",
                        value=value,
                        source=f"BearResearcher_{key}",
                        confidence=bear_result.confidence * 0.9
                    ))
        
        # Prepare initial arguments for debate
        initial_arguments = {
            "BullResearcher": {
                "claim": bull_result.decision if bull_result.decision != "HOLD" else "Market is bullish",
                "reasoning": bull_thesis or bull_reasoning or f"Bullish confidence: {bull_result.confidence:.2%}",
                "confidence": bull_result.confidence,
                "evidence": bull_evidence if bull_evidence else None
            },
            "BearResearcher": {
                "claim": bear_result.decision if bear_result.decision != "HOLD" else "Market is bearish",
                "reasoning": bear_thesis or bear_reasoning or f"Bearish confidence: {bear_result.confidence:.2%}",
                "confidence": bear_result.confidence,
                "evidence": bear_evidence if bear_evidence else None
            }
        }
        
        # Conduct debate
        debate_result = debate_protocol.conduct_debate(
            initial_arguments=initial_arguments,
            llm_synthesizer=self.llm_client
        )
        
        logger.info(f"Debate concluded: Winner={debate_result.winner}, "
                   f"Confidence={debate_result.winner_confidence:.2%}")
        
        return debate_result
    
    def _synthesize_from_debate(
        self,
        debate_result,
        bull_result: AnalysisResult,
        bear_result: AnalysisResult
    ) -> Dict[str, Any]:
        """Synthesize final decision from debate result.
        
        Args:
            debate_result: DebateResult from formal debate
            bull_result: Bull researcher result
            bear_result: Bear researcher result
        
        Returns:
            Dictionary with decision, confidence, and plan
        """
        winner = debate_result.winner
        
        if winner == "BullResearcher" and bull_result and bull_result.decision != "HOLD":
            return {
                "decision": bull_result.decision,  # e.g., "BULL_CALL_SPREAD"
                "confidence": min(debate_result.winner_confidence + 0.05, 0.95),
                "plan": f"Bull wins debate: {debate_result.consensus or debate_result.recommended_action or bull_result.decision}"
            }
        elif winner == "BearResearcher" and bear_result and bear_result.decision != "HOLD":
            return {
                "decision": bear_result.decision,  # e.g., "BEAR_PUT_SPREAD"
                "confidence": min(debate_result.winner_confidence + 0.05, 0.95),
                "plan": f"Bear wins debate: {debate_result.consensus or debate_result.recommended_action or bear_result.decision}"
            }
        else:
            # No clear winner or neutral - suggest iron condor for range-bound market
            return {
                "decision": "IRON_CONDOR",
                "confidence": 0.6,
                "plan": f"Neutral debate result: {debate_result.consensus or 'Market range-bound - implement iron condor'}"
            }
