"""Enhanced Risk Agents with Deliberation Mechanism.

This module provides enhanced risk agents that use a deliberation mechanism
to debate risk assessments before making final recommendations.
"""

import logging
from typing import Dict, Any, List, Optional

from engine_module.agents.base_agent import BaseAgent
from engine_module.contracts import AnalysisResult
from engine_module.communication import (
    DebateProtocol,
    ArgumentType,
    ReportEvidence,
    EvidenceType,
    ReportType,
    ReportPriority
)

logger = logging.getLogger(__name__)


class EnhancedRiskAgent(BaseAgent):
    """Enhanced risk agent with deliberation mechanism.
    
    This agent uses a formal deliberation process between multiple risk perspectives
    before making risk recommendations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize enhanced risk agent.
        
        Args:
            config: Configuration dictionary with:
                - risk_tolerance: Risk tolerance level (default: "moderate")
                - max_portfolio_risk: Maximum portfolio risk % (default: 0.02)
                - max_position_risk: Maximum position risk % (default: 0.01)
        """
        config = config or {}
        super().__init__("EnhancedRiskAgent", config)
        
        self.risk_tolerance = config.get('risk_tolerance', 'moderate')
        self.max_portfolio_risk = config.get('max_portfolio_risk', 0.02)  # 2%
        self.max_position_risk = config.get('max_position_risk', 0.01)  # 1%
        
        # Initialize deliberation protocol
        self.deliberation_protocol = DebateProtocol(
            max_rounds=2,  # Shorter debates for risk assessment
            min_confidence_threshold=0.7
        )
        
        logger.debug(f"EnhancedRiskAgent initialized: tolerance={self.risk_tolerance}, "
                    f"max_portfolio_risk={self.max_portfolio_risk}")
    
    async def _analyze_internal(
        self,
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any],
        regime: Optional[str],
        current_positions: List[Dict[str, Any]],
        technical_indicators: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AnalysisResult:
        """Perform risk analysis with deliberation.
        
        Args:
            market_data: Current market data
            multi_timeframe: Multi-timeframe data
            regime: Market regime
            current_positions: Current positions
            technical_indicators: Technical indicators
            context: Full context
        
        Returns:
            AnalysisResult with risk assessment
        """
        # Conduct deliberation between risk perspectives
        deliberation_result = await self._conduct_risk_deliberation(
            market_data, current_positions, technical_indicators, context
        )
        
        # Determine risk recommendation
        risk_level = self._determine_risk_level(deliberation_result, market_data, current_positions)
        
        # Make decision (typically HOLD/VETO/APPROVE)
        decision = self._make_risk_decision(risk_level, context)
        
        # Calculate confidence based on deliberation consensus
        confidence = deliberation_result.winner_confidence if deliberation_result.winner else 0.5
        
        details = {
            'agent': self.name,
            'risk_level': risk_level,
            'deliberation_result': deliberation_result.to_dict(),
            'portfolio_risk': self._calculate_portfolio_risk(current_positions, market_data),
            'recommendation': decision,
            'risk_assessment': self._assess_risk(market_data, decision, current_positions)
        }
        
        return AnalysisResult(
            decision=decision,
            confidence=confidence,
            details=details,
            agent=self.name
        )
    
    async def _conduct_risk_deliberation(
        self,
        market_data: Dict[str, Any],
        current_positions: List[Dict[str, Any]],
        technical_indicators: Dict[str, Any],
        context: Dict[str, Any]
    ):
        """Conduct formal deliberation between risk perspectives.
        
        This creates multiple risk perspectives (conservative, moderate, aggressive)
        and has them debate the risk assessment.
        """
        # Register risk perspectives
        conservative = self.deliberation_protocol.register_participant(
            "ConservativeRiskPerspective",
            "conservative"
        )
        
        moderate = self.deliberation_protocol.register_participant(
            "ModerateRiskPerspective",
            "moderate"
        )
        
        # Calculate risk metrics
        iv_percentile = market_data.get('iv_percentile', 50)
        portfolio_risk = self._calculate_portfolio_risk(current_positions, market_data)
        volatility = market_data.get('volatility', 0) or technical_indicators.get('volatility', 0)
        
        # Conservative perspective - focus on risk
        conservative_evidence = [
            ReportEvidence(
                type=EvidenceType.MARKET_DATA,
                description=f"IV percentile: {iv_percentile}%",
                value=iv_percentile,
                source="IV_Percentile",
                confidence=0.8
            )
        ]
        
        if portfolio_risk > self.max_portfolio_risk:
            conservative_evidence.append(ReportEvidence(
                type=EvidenceType.STATISTICAL_ANALYSIS,
                description=f"Portfolio risk exceeds limit: {portfolio_risk:.2%} > {self.max_portfolio_risk:.2%}",
                value=portfolio_risk,
                source="PortfolioRisk",
                confidence=0.9
            ))
        
        conservative_confidence = 0.9 if (iv_percentile > 80 or portfolio_risk > self.max_portfolio_risk) else 0.6
        conservative_claim = "RISK TOO HIGH" if conservative_confidence > 0.8 else "RISK MODERATE"
        
        # Moderate perspective - balanced view
        moderate_evidence = [
            ReportEvidence(
                type=EvidenceType.MARKET_DATA,
                description=f"Volatility: {volatility:.2%}" if volatility > 0 else "Volatility: Normal",
                value=volatility if volatility > 0 else 0.2,
                source="Volatility",
                confidence=0.7
            )
        ]
        
        moderate_confidence = 0.7
        moderate_claim = "RISK ACCEPTABLE" if portfolio_risk <= self.max_portfolio_risk else "RISK ELEVATED"
        
        # Prepare arguments
        initial_arguments = {
            "ConservativeRiskPerspective": {
                "claim": conservative_claim,
                "reasoning": f"IV percentile {iv_percentile}%, portfolio risk {portfolio_risk:.2%}",
                "confidence": conservative_confidence,
                "evidence": conservative_evidence
            },
            "ModerateRiskPerspective": {
                "claim": moderate_claim,
                "reasoning": f"Balanced risk assessment: portfolio risk {portfolio_risk:.2%}",
                "confidence": moderate_confidence,
                "evidence": moderate_evidence
            }
        }
        
        # Conduct deliberation
        deliberation_result = self.deliberation_protocol.conduct_debate(
            initial_arguments=initial_arguments
        )
        
        logger.debug(f"Risk deliberation concluded: Winner={deliberation_result.winner}")
        
        return deliberation_result
    
    def _calculate_portfolio_risk(
        self,
        current_positions: List[Dict[str, Any]],
        market_data: Dict[str, Any]
    ) -> float:
        """Calculate current portfolio risk as percentage of account."""
        if not current_positions:
            return 0.0
        
        # Sum risk from all positions
        total_risk = sum(
            pos.get('max_loss', 0) or pos.get('risk_amount', 0)
            for pos in current_positions
        )
        
        # Get account balance (from context or default)
        account_balance = market_data.get('account_balance', 1000000)  # Default 10L
        
        if account_balance <= 0:
            return 0.0
        
        portfolio_risk = total_risk / account_balance
        return portfolio_risk
    
    def _determine_risk_level(
        self,
        deliberation_result,
        market_data: Dict[str, Any],
        current_positions: List[Dict[str, Any]]
    ) -> str:
        """Determine overall risk level from deliberation."""
        winner = deliberation_result.winner
        
        if winner == "ConservativeRiskPerspective":
            return "HIGH"
        
        portfolio_risk = self._calculate_portfolio_risk(current_positions, market_data)
        
        if portfolio_risk > self.max_portfolio_risk:
            return "HIGH"
        elif portfolio_risk > self.max_portfolio_risk * 0.7:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _make_risk_decision(
        self,
        risk_level: str,
        context: Dict[str, Any]
    ) -> str:
        """Make risk decision (HOLD/VETO/APPROVE).
        
        Args:
            risk_level: Risk level (HIGH/MEDIUM/LOW)
            context: Analysis context
        
        Returns:
            Decision string (typically "HOLD" for risk veto, or "APPROVE")
        """
        proposed_action = context.get('proposed_action')
        
        if risk_level == "HIGH":
            return "VETO"  # Block the trade
        elif risk_level == "MEDIUM":
            return "CAUTION"  # Warn but allow
        else:
            return "APPROVE" if proposed_action else "HOLD"
    
    def _add_analysis_sections(
        self,
        builder,
        analysis_result: AnalysisResult,
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any],
        regime: Optional[str]
    ):
        """Add risk-specific sections to report."""
        # Call parent for base sections
        super()._add_analysis_sections(builder, analysis_result, market_data, multi_timeframe, regime)
        
        details = analysis_result.details or {}
        deliberation_result = details.get('deliberation_result', {})
        portfolio_risk = details.get('portfolio_risk', 0.0)
        
        # Add risk deliberation section
        if deliberation_result:
            builder.add_section(
                title="Risk Deliberation",
                content=f"Risk deliberation concluded: {deliberation_result.get('summary', 'N/A')}",
                confidence=analysis_result.confidence
            )
        
        # Add portfolio risk section
        builder.add_section(
            title="Portfolio Risk Assessment",
            content=f"Current portfolio risk: {portfolio_risk:.2%} (Limit: {self.max_portfolio_risk:.2%})",
            confidence=0.9 if portfolio_risk <= self.max_portfolio_risk else 0.5
        )
