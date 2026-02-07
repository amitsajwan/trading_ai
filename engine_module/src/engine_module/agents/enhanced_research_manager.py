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
    """Market Maker: Synthesizes trader inputs into final strategy parameters.

    This manager acts as a market maker who combines aggressive bull trader and
    conservative bear trader inputs to create balanced, executable strategies.
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
        """Act as market maker synthesizing trader inputs into balanced strategy.

        Args:
            context: Analysis context with market data, positions, etc.

        Returns:
            AnalysisResult with synthesized trading parameters
        """
        try:
            # Get bull and bear trader analyses
            bull_result = await self._get_bull_analysis(context)
            bear_result = await self._get_bear_analysis(context)

            if not bull_result or not bear_result:
                logger.warning("Missing bull or bear trader analysis, returning HOLD")
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.3,
                    details={
                        "reasoning": "Unable to perform balanced market analysis due to missing Bull and Bear researcher agents (chromadb not available). Returning HOLD to avoid biased trading decisions.",
                        "bull_result": bull_result is not None,
                        "bear_result": bear_result is not None
                    },
                    agent=self._agent_name
                )

            # Market maker synthesis: Balance aggressive and conservative approaches
            final_strategy = self._synthesize_trader_strategies(bull_result, bear_result, context)

            # Generate market maker reasoning
            reasoning = self._generate_market_maker_reasoning(
                bull_result, bear_result, final_strategy, context
            )

            return AnalysisResult(
                decision=final_strategy["strategy_type"],
                confidence=final_strategy["confidence"],
                details={
                    "reasoning": reasoning,
                    "market_maker_synthesis": final_strategy,
                    "bull_trader_input": bull_result.details,
                    "bear_trader_input": bear_result.details,
                    "synthesized_parameters": final_strategy["parameters"],
                    "risk_balance": final_strategy["risk_balance"],
                    "market_view": "balanced_market_making"
                },
                agent=self._agent_name
            )

        except Exception as e:
            logger.exception("Market maker synthesis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.3,
                details={"error": str(e), "reason": "SYNTHESIS_ERROR"},
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
    
    def _synthesize_trader_strategies(self, bull_result: AnalysisResult,
                                     bear_result: AnalysisResult, context: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize trading strategies from bull and bear trader inputs.

        Args:
            bull_result: Aggressive bull trader analysis
            bear_result: Conservative bear trader analysis
            context: Market context

        Returns:
            Dict with synthesized strategy parameters
        """
        # Extract trader preferences
        bull_confidence = bull_result.confidence
        bear_confidence = bear_result.confidence
        bull_strategy = bull_result.decision
        bear_strategy = bear_result.decision

        # Market regime analysis
        technical = context.get('technical_indicators', {})
        adx_val = technical.get('adx_14', 20)
        trend_direction = technical.get('trend_direction', 'SIDEWAYS')

        # MARKET MAKER SYNTHESIS LOGIC
        # Balance aggressive bull vs conservative bear approaches

        if adx_val > 25:  # Strong trend
            # In strong trends, lean toward the directional trader
            if trend_direction == "UP" and bull_confidence > bear_confidence:
                base_strategy = bull_strategy  # Bull trader leads
                confidence = bull_confidence * 0.9  # Slightly conservative
            elif trend_direction == "DOWN" and bear_confidence > bull_confidence:
                base_strategy = bear_strategy  # Bear trader leads
                confidence = bear_confidence * 0.9
            else:
                base_strategy = "IRON_CONDOR"  # Balanced approach
                confidence = 0.65
        else:  # Range-bound market
            # In range markets, prefer balanced strategies
            base_strategy = "IRON_CONDOR"  # Most balanced
            confidence = min(bull_confidence, bear_confidence) + 0.1  # Balanced confidence

        # Synthesize strike selection - balance aggressive vs conservative
        bull_params = bull_result.details.get('trading_parameters', {})
        bear_params = bear_result.details.get('trading_parameters', {})

        synthesized_params = self._balance_strike_parameters(bull_params, bear_params, base_strategy)

        return {
            "strategy_type": base_strategy,
            "confidence": min(confidence, 0.85),  # Market maker conservatism
            "parameters": synthesized_params,
            "risk_balance": {
                "bull_input_weight": bull_confidence / (bull_confidence + bear_confidence),
                "bear_input_weight": bear_confidence / (bull_confidence + bear_confidence),
                "synthesis_approach": "weighted_average_with_conservative_bias"
            },
            "market_regime": {
                "trend_strength": "strong" if adx_val > 25 else "weak",
                "direction": trend_direction,
                "volatility": technical.get('volatility_level', 'MEDIUM')
            }
        }

    def _balance_strike_parameters(self, bull_params: Dict, bear_params: Dict, strategy: str) -> Dict:
        """Balance strike parameters between aggressive and conservative approaches."""

        if strategy == "IRON_CONDOR":
            # Balance bull (wider strikes) and bear (tighter strikes) approaches
            bull_strikes = bull_params.get('strike_selection', {})
            bear_strikes = bear_params.get('strike_selection', {})

            return {
                "strike_selection": {
                    "put_sell_range": self._weighted_average_range(
                        bull_strikes.get('put_sell_range', '3-5% OTM'),
                        bear_strikes.get('put_sell_range', '2-3% OTM'),
                        0.6, 0.4  # 60% bull, 40% bear weighting
                    ),
                    "put_buy_range": self._weighted_average_range(
                        bull_strikes.get('put_buy_range', '8-12% OTM'),
                        bear_strikes.get('put_buy_range', '5-7% OTM'),
                        0.6, 0.4
                    ),
                    "call_sell_range": self._weighted_average_range(
                        bull_strikes.get('call_sell_range', '3-5% OTM'),
                        bear_strikes.get('call_sell_range', '2-3% OTM'),
                        0.6, 0.4
                    ),
                    "call_buy_range": self._weighted_average_range(
                        bull_strikes.get('call_buy_range', '8-12% OTM'),
                        bear_strikes.get('call_buy_range', '5-7% OTM'),
                        0.6, 0.4
                    )
                },
                "position_sizing": {
                    "allocation": "55% puts, 45% calls",  # Slight bull bias
                    "max_loss_limit": "₹7,000",  # Between bull ₹10k and bear ₹5k
                    "target_profit": "₹2,500"  # Between bull ₹3k and bear ₹1.5k
                },
                "risk_management": {
                    "stop_loss": "35% of max loss",  # Between bull 50% and bear 25%
                    "trailing_stop": False,  # Conservative approach
                    "time_decay_management": "Close if theta decay > ₹300/day"
                }
            }
        elif strategy in ["BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]:
            # For directional strategies, use more conservative parameters
            return bear_params.get('strike_selection', {}) if bear_params else bull_params.get('strike_selection', {})
        else:
            return {}

    def _weighted_average_range(self, range1: str, range2: str, weight1: float, weight2: float) -> str:
        """Calculate weighted average of two percentage ranges."""
        try:
            # Parse ranges like "3-5% OTM" -> extract numbers
            def parse_range(r):
                nums = [int(x.strip('% OTM-')) for x in r.split('-') if x.strip('% OTM-').isdigit()]
                return nums[0] if nums else 3

            val1 = parse_range(range1)
            val2 = parse_range(range2)
            avg_low = int(val1 * weight1 + val2 * weight2)
            avg_high = int((val1 + 2) * weight1 + (val2 + 2) * weight2)  # Assume +2 for high end

            return f"{avg_low}-{avg_high}% OTM"
        except:
            return range1  # Fallback to first range

    def _generate_market_maker_reasoning(self, bull_result: AnalysisResult,
                                       bear_result: AnalysisResult, final_strategy: Dict,
                                       context: Dict) -> str:
        """Generate market maker reasoning for the synthesized strategy."""

        bull_confidence = bull_result.confidence
        bear_confidence = bear_result.confidence
        strategy = final_strategy['strategy_type']

        reasoning_parts = [
            f"As market maker, I've synthesized inputs from aggressive bull trader ({bull_confidence:.1f} confidence) and conservative bear trader ({bear_confidence:.1f} confidence).",
            f"Final strategy: {strategy} with {final_strategy['confidence']:.1f} confidence.",
            f"Strike positioning: Balanced between aggressive and conservative approaches.",
            f"Risk management: Conservative bias with {final_strategy['parameters'].get('risk_management', {}).get('stop_loss', 'appropriate')} stops.",
            f"Market regime: {final_strategy['market_regime']['trend_strength']} {final_strategy['market_regime']['direction']} trend, {final_strategy['market_regime']['volatility']} volatility.",
            "Position provides balanced risk/reward while capitalizing on market opportunities."
        ]

        return " ".join(reasoning_parts)
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
