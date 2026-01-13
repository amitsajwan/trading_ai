"""Enhanced Base Agent with Structured Reports and Advanced Features.

This module provides an enhanced base agent class that all agents can inherit from,
providing common functionality including:
- Structured report generation
- Multi-timeframe analysis integration
- Regime detection integration
- Evidence-based reasoning
- Position-aware analysis
- Exit signal generation
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

from engine_module.contracts import Agent, AnalysisResult
from engine_module.communication import (
    ReportBuilder,
    StructuredReport,
    ReportEvidence,
    ReportAction,
    ReportSection,
    ReportType,
    ReportPriority,
    EvidenceType
)

logger = logging.getLogger(__name__)


class SignalStrength:
    """Signal strength levels based on confidence."""
    VERY_STRONG = "very_strong"  # > 0.9
    STRONG = "strong"  # 0.7 - 0.9
    MODERATE = "moderate"  # 0.5 - 0.7
    WEAK = "weak"  # 0.3 - 0.5
    VERY_WEAK = "very_weak"  # < 0.3
    
    @staticmethod
    def from_confidence(confidence: float) -> str:
        """Get signal strength from confidence level."""
        if confidence >= 0.9:
            return SignalStrength.VERY_STRONG
        elif confidence >= 0.7:
            return SignalStrength.STRONG
        elif confidence >= 0.5:
            return SignalStrength.MODERATE
        elif confidence >= 0.3:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK


class BaseAgent(ABC, Agent):
    """Enhanced base agent with structured reporting and advanced features.
    
    This abstract base class provides common functionality for all agents:
    - Structured report generation
    - Evidence collection and management
    - Confidence calculation
    - Multi-timeframe data access
    - Regime detection integration
    - Position-aware analysis
    - Exit signal generation
    
    Subclasses must implement:
    - `_analyze_internal()`: Core analysis logic
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize enhanced base agent.
        
        Args:
            name: Agent name
            config: Configuration dictionary with:
                - min_confidence: Minimum confidence threshold (default: 0.60)
                - use_structured_reports: Enable structured reports (default: True)
                - use_multi_timeframe: Enable multi-timeframe analysis (default: True)
                - use_regime_detection: Enable regime detection (default: True)
        """
        self.name = name
        self._agent_name = name  # For compatibility
        self.config = config or {}
        
        self.min_confidence = self.config.get('min_confidence', 0.60)
        self.use_structured_reports = self.config.get('use_structured_reports', True)
        self.use_multi_timeframe = self.config.get('use_multi_timeframe', True)
        self.use_regime_detection = self.config.get('use_regime_detection', True)
        
        logger.debug(f"{self.name} initialized with min_confidence={self.min_confidence}")
    
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Main analyze method with structured reporting wrapper.
        
        This method provides the interface for all agents, wrapping the
        internal analysis with structured reporting and evidence collection.
        
        Args:
            context: Analysis context with:
                - market_data: Current market data
                - multi_timeframe: Optional multi-timeframe data
                - regime: Optional current market regime
                - current_positions: Optional list of current positions
                - technical_indicators: Optional pre-calculated indicators
        
        Returns:
            AnalysisResult with structured report in details if enabled
        """
        try:
            # Extract context components
            market_data = context.get('market_data', context)  # Fallback to full context
            multi_timeframe = context.get('multi_timeframe', {})
            regime = context.get('regime')
            current_positions = context.get('current_positions', [])
            technical_indicators = context.get('technical_indicators', {})
            
            # Perform internal analysis
            analysis_result = await self._analyze_internal(
                market_data=market_data,
                multi_timeframe=multi_timeframe,
                regime=regime,
                current_positions=current_positions,
                technical_indicators=technical_indicators,
                context=context
            )
            
            # Generate structured report if enabled
            if self.use_structured_reports:
                structured_report = self._build_structured_report(
                    analysis_result=analysis_result,
                    market_data=market_data,
                    multi_timeframe=multi_timeframe,
                    regime=regime,
                    current_positions=current_positions
                )
                
                # Add structured report to details
                if analysis_result.details is None:
                    analysis_result.details = {}
                
                analysis_result.details['structured_report'] = structured_report.to_dict()
                analysis_result.details['signal_strength'] = SignalStrength.from_confidence(
                    analysis_result.confidence
                )
            
            return analysis_result
        
        except Exception as e:
            logger.exception(f"{self.name} analysis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "error": str(e),
                    "reason": "ANALYSIS_ERROR",
                    "agent": self.name
                },
                agent=self.name
            )
    
    @abstractmethod
    async def _analyze_internal(
        self,
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any],
        regime: Optional[str],
        current_positions: List[Dict[str, Any]],
        technical_indicators: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AnalysisResult:
        """Perform core analysis logic.
        
        This method should be implemented by subclasses to provide
        agent-specific analysis logic.
        
        Args:
            market_data: Current market data
            multi_timeframe: Multi-timeframe data (dict with timeframe keys)
            regime: Current market regime (if available)
            current_positions: List of current positions
            technical_indicators: Pre-calculated technical indicators
            context: Full context dictionary
        
        Returns:
            AnalysisResult with decision, confidence, and details
        """
        pass
    
    def _build_structured_report(
        self,
        analysis_result: AnalysisResult,
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any],
        regime: Optional[str],
        current_positions: List[Dict[str, Any]]
    ) -> StructuredReport:
        """Build structured report from analysis result.
        
        Subclasses can override this to customize report structure.
        
        Args:
            analysis_result: The analysis result
            market_data: Market data used
            multi_timeframe: Multi-timeframe data
            regime: Market regime
            current_positions: Current positions
        
        Returns:
            StructuredReport object
        """
        builder = ReportBuilder(self.name)
        
        # Determine report type based on decision
        if analysis_result.decision in ["BUY", "SELL", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]:
            report_type = ReportType.RECOMMENDATION
            priority = ReportPriority.HIGH if analysis_result.confidence >= 0.7 else ReportPriority.MEDIUM
        elif analysis_result.decision == "HOLD":
            report_type = ReportType.ANALYSIS
            priority = ReportPriority.MEDIUM
        else:
            report_type = ReportType.ANALYSIS
            priority = ReportPriority.LOW
        
        builder.set_type(report_type)
        builder.set_priority(priority)
        builder.set_confidence(analysis_result.confidence)
        
        # Build title and summary
        title = f"{self.name} Analysis: {analysis_result.decision}"
        summary = self._build_summary(analysis_result, regime, current_positions)
        builder.set_title(title)
        builder.set_summary(summary)
        
        # Add sections
        self._add_analysis_sections(
            builder=builder,
            analysis_result=analysis_result,
            market_data=market_data,
            multi_timeframe=multi_timeframe,
            regime=regime
        )
        
        # Add actions
        if analysis_result.decision != "HOLD":
            self._add_action_recommendations(
                builder=builder,
                analysis_result=analysis_result,
                current_positions=current_positions
            )
        
        return builder.build()
    
    def _build_summary(
        self,
        analysis_result: AnalysisResult,
        regime: Optional[str],
        current_positions: List[Dict[str, Any]]
    ) -> str:
        """Build executive summary for report."""
        decision = analysis_result.decision
        confidence = analysis_result.confidence
        strength = SignalStrength.from_confidence(confidence)
        
        summary_parts = [
            f"Decision: {decision}",
            f"Confidence: {confidence:.1%} ({strength})"
        ]
        
        if regime:
            summary_parts.append(f"Market Regime: {regime}")
        
        if current_positions:
            summary_parts.append(f"Current Positions: {len(current_positions)}")
        
        details = analysis_result.details or {}
        if 'reasoning' in details:
            summary_parts.append(f"Reasoning: {details['reasoning']}")
        
        return ". ".join(summary_parts)
    
    def _add_analysis_sections(
        self,
        builder: ReportBuilder,
        analysis_result: AnalysisResult,
        market_data: Dict[str, Any],
        multi_timeframe: Dict[str, Any],
        regime: Optional[str]
    ):
        """Add analysis sections to report.
        
        Subclasses can override this to add agent-specific sections.
        """
        details = analysis_result.details or {}
        
        # Add main analysis section
        content_parts = []
        if 'reasoning' in details:
            content_parts.append(details['reasoning'])
        
        evidence = []
        
        # Add technical indicator evidence
        if 'technical_indicators' in market_data or 'rsi' in details:
            rsi = details.get('rsi') or market_data.get('rsi')
            if rsi is not None:
                evidence.append(ReportEvidence(
                    type=EvidenceType.TECHNICAL_INDICATOR,
                    description=f"RSI at {rsi:.1f}",
                    value=rsi,
                    source="RSI_14",
                    confidence=0.8
                ))
        
        # Add regime evidence
        if regime:
            content_parts.append(f"Market Regime: {regime}")
            evidence.append(ReportEvidence(
                type=EvidenceType.MARKET_DATA,
                description=f"Market regime: {regime}",
                value=regime,
                source="RegimeDetector",
                confidence=0.7
            ))
        
        # Add multi-timeframe evidence
        if multi_timeframe:
            content_parts.append(f"Multi-timeframe analysis available: {list(multi_timeframe.keys())}")
        
        builder.add_section(
            title="Analysis",
            content=". ".join(content_parts) if content_parts else "Analysis completed",
            confidence=analysis_result.confidence,
            evidence=evidence
        )
    
    def _add_action_recommendations(
        self,
        builder: ReportBuilder,
        analysis_result: AnalysisResult,
        current_positions: List[Dict[str, Any]]
    ):
        """Add action recommendations to report.
        
        Subclasses can override this to customize actions.
        """
        decision = analysis_result.decision
        details = analysis_result.details or {}
        
        # Determine target
        target = details.get('target', 'BANKNIFTY')
        reasoning = details.get('reasoning', f"Agent recommends {decision}")
        
        # Risk assessment
        risk_assessment = details.get('risk_assessment', {})
        
        builder.add_action(
            action=decision,
            target=target,
            reasoning=reasoning,
            confidence=analysis_result.confidence,
            risk_assessment=risk_assessment,
            urgency="scheduled" if analysis_result.confidence >= 0.7 else "optional"
        )
    
    def _calculate_confidence(
        self,
        conditions: Dict[str, bool],
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        """Calculate confidence score based on conditions.
        
        Args:
            conditions: Dict with condition name and result (True/False)
            weights: Optional dict with condition weights
        
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not conditions:
            return 0.0
        
        if weights:
            # Weighted calculation
            total_weight = sum(weights.values())
            if total_weight == 0:
                return 0.0
            
            weighted_score = sum(
                weights.get(cond, 1.0) for cond, result in conditions.items() if result
            )
            return weighted_score / total_weight
        else:
            # Simple ratio
            met_conditions = sum(1 for result in conditions.values() if result)
            return met_conditions / len(conditions)
    
    def _assess_risk(
        self,
        market_data: Dict[str, Any],
        action: str,
        current_positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess risk for a trading action.
        
        Args:
            market_data: Current market data
            action: Proposed action
            current_positions: Current positions
        
        Returns:
            Risk assessment dictionary
        """
        risk_score = 0
        
        # Volatility risk
        iv_percentile = market_data.get('iv_percentile', 50)
        if iv_percentile > 80:
            risk_score += 30
        elif iv_percentile > 70:
            risk_score += 20
        
        # Portfolio exposure
        total_exposure = sum(pos.get('exposure', 0) for pos in current_positions)
        if total_exposure > 0.5:  # 50% portfolio exposed
            risk_score += 30
        elif total_exposure > 0.3:  # 30% portfolio exposed
            risk_score += 15
        
        # Determine risk level
        if risk_score >= 60:
            risk_level = "HIGH"
            recommendation = "CAUTION"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
            recommendation = "MODERATE"
        else:
            risk_level = "LOW"
            recommendation = "OK"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "volatility_regime": "high" if iv_percentile > 70 else "normal",
            "portfolio_exposure": total_exposure,
            "recommendation": recommendation
        }
    
    def _check_exit_conditions(
        self,
        market_data: Dict[str, Any],
        current_positions: List[Dict[str, Any]],
        technical_indicators: Dict[str, Any]
    ) -> Optional[AnalysisResult]:
        """Check if exit conditions are met for current positions.
        
        Subclasses can override this to provide agent-specific exit logic.
        
        Args:
            market_data: Current market data
            current_positions: Current positions
            technical_indicators: Technical indicators
        
        Returns:
            AnalysisResult with CLOSE action if exit conditions met, None otherwise
        """
        if not current_positions:
            return None
        
        # Basic exit logic - subclasses should override
        # For now, check if any position has significant adverse movement
        for position in current_positions:
            entry_price = position.get('entry_price', 0)
            current_price = market_data.get('close', 0) or market_data.get('current_price', 0)
            
            if entry_price > 0 and current_price > 0:
                position_type = position.get('type', 'LONG')
                
                if position_type == 'LONG':
                    pnl_pct = (current_price - entry_price) / entry_price
                else:  # SHORT
                    pnl_pct = (entry_price - current_price) / entry_price
                
                # Exit if loss exceeds 2%
                if pnl_pct <= -0.02:
                    return AnalysisResult(
                        decision="CLOSE",
                        confidence=0.80,
                        details={
                            "position_id": position.get('id'),
                            "reason": "Stop loss hit (-2%)",
                            "pnl_pct": pnl_pct,
                            "agent": self.name
                        },
                        agent=self.name
                    )
        
        return None
