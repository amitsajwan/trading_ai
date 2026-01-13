"""Fund Manager Approval Layer for final trade approval.

This module provides the final approval layer before trade execution,
integrating portfolio heat management and Kelly position sizing.
"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from engine_module.contracts import AnalysisResult

# Import risk management components
try:
    from risk_module.portfolio_heat import PortfolioHeatManager, PositionRisk
    from risk_module.position_sizer import KellyPositionSizer
except ImportError:
    # Handle import error if risk_module not available
    PortfolioHeatManager = None
    KellyPositionSizer = None
    PositionRisk = None

logger = logging.getLogger(__name__)


class ApprovalDecision(Enum):
    """Approval decision types."""
    APPROVED = "approved"
    REJECTED = "rejected"
    REDUCED = "reduced"  # Approved but with reduced size
    DEFERRED = "deferred"  # Need more information


class ApprovalReason(Enum):
    """Approval reason codes."""
    OK = "ok"
    PORTFOLIO_HEAT_EXCEEDED = "portfolio_heat_exceeded"
    POSITION_HEAT_EXCEEDED = "position_heat_exceeded"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    WEEKLY_LOSS_LIMIT = "weekly_loss_limit"
    KELLY_TOO_LOW = "kelly_too_low"
    INSUFFICIENT_HISTORY = "insufficient_history"
    CONFLICTING_RISK_ASSESSMENT = "conflicting_risk_assessment"


@dataclass
class ApprovalResult:
    """Result of fund manager approval."""
    decision: ApprovalDecision
    reason: ApprovalReason
    approved_quantity: int
    original_quantity: Optional[int]
    kelly_percentage: float
    risk_amount: float
    portfolio_heat_used: float
    portfolio_heat_available: float
    details: Dict[str, Any]
    timestamp: datetime


class FundManagerApprovalLayer:
    """Fund Manager Approval Layer for final trade approval.
    
    This layer acts as the final gatekeeper before trade execution:
    1. Validates portfolio heat limits
    2. Calculates optimal position size using Kelly Criterion
    3. Reviews risk assessment from agents
    4. Makes final approval decision
    5. Logs all decisions for audit trail
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Fund Manager Approval Layer.
        
        Args:
            config: Configuration dictionary with:
                - portfolio_heat_config: Config for PortfolioHeatManager
                - kelly_config: Config for KellyPositionSizer
                - min_approval_confidence: Minimum confidence to approve (default 0.6)
                - require_risk_approval: Require risk agent approval (default True)
        """
        self.config = config
        
        # Initialize portfolio heat manager
        if PortfolioHeatManager is not None:
            portfolio_config = config.get('portfolio_heat_config', {})
            portfolio_config.setdefault('account_balance', config.get('account_balance', 100000.0))
            self.portfolio_heat_manager = PortfolioHeatManager(portfolio_config)
        else:
            self.portfolio_heat_manager = None
            logger.warning("PortfolioHeatManager not available")
        
        # Initialize Kelly position sizer
        if KellyPositionSizer is not None:
            kelly_config = config.get('kelly_config', {})
            self.kelly_sizer = KellyPositionSizer(kelly_config)
        else:
            self.kelly_sizer = None
            logger.warning("KellyPositionSizer not available")
        
        self.min_approval_confidence = config.get('min_approval_confidence', 0.6)
        self.require_risk_approval = config.get('require_risk_approval', True)
        
        # Audit log
        self.approval_log: List[ApprovalResult] = []
        
        logger.info(f"Fund Manager Approval Layer initialized: "
                   f"min_confidence={self.min_approval_confidence}, "
                   f"require_risk_approval={self.require_risk_approval}")
    
    async def review_and_approve(
        self,
        trading_decision: AnalysisResult,
        current_positions: List[Dict[str, Any]],
        trade_history: Optional[List[Dict[str, Any]]] = None,
        proposed_quantity: Optional[int] = None,
        max_loss_per_unit: Optional[float] = None
    ) -> ApprovalResult:
        """Review and approve/reject trading decision.
        
        Args:
            trading_decision: Trading decision from orchestrator
            current_positions: List of current active positions
            trade_history: Optional trade history for Kelly calculation
            proposed_quantity: Optional proposed position size
            max_loss_per_unit: Optional max loss per unit/lot
        
        Returns:
            ApprovalResult with decision and details
        """
        timestamp = datetime.now()
        original_quantity = proposed_quantity or 0
        approved_quantity = 0
        
        # Convert positions to PositionRisk format
        position_risks = self._convert_positions_to_risks(current_positions)
        
        # Step 1: Check confidence threshold
        if trading_decision.confidence < self.min_approval_confidence:
            return ApprovalResult(
                decision=ApprovalDecision.REJECTED,
                reason=ApprovalReason.KELLY_TOO_LOW,  # Reuse reason code
                approved_quantity=0,
                original_quantity=original_quantity,
                kelly_percentage=0.0,
                risk_amount=0.0,
                portfolio_heat_used=0.0,
                portfolio_heat_available=0.0,
                details={
                    'reason': f"Confidence {trading_decision.confidence:.2%} below minimum {self.min_approval_confidence:.2%}",
                    'confidence': trading_decision.confidence
                },
                timestamp=timestamp
            )
        
        # Step 2: Check risk agent approval (if required)
        if self.require_risk_approval:
            risk_decision = self._check_risk_approval(trading_decision)
            if risk_decision == "VETO":
                return ApprovalResult(
                    decision=ApprovalDecision.REJECTED,
                    reason=ApprovalReason.CONFLICTING_RISK_ASSESSMENT,
                    approved_quantity=0,
                    original_quantity=original_quantity,
                    kelly_percentage=0.0,
                    risk_amount=0.0,
                    portfolio_heat_used=0.0,
                    portfolio_heat_available=0.0,
                    details={
                        'reason': 'Risk agent vetoed the trade',
                        'risk_details': trading_decision.details.get('risk_details')
                    },
                    timestamp=timestamp
                )
        
        # Step 3: Calculate optimal position size using Kelly (if sizer available)
        kelly_pct = 0.0
        optimal_quantity = original_quantity
        
        if self.kelly_sizer is not None and max_loss_per_unit and max_loss_per_unit > 0:
            account_balance = self.portfolio_heat_manager.account_balance if self.portfolio_heat_manager else 100000.0
            
            if trade_history:
                # Use historical stats
                kelly_result = self.kelly_sizer.calculate_position_size_from_history(
                    account_balance=account_balance,
                    max_loss_per_unit=max_loss_per_unit,
                    trade_history=trade_history,
                    strategy_type=trading_decision.details.get('strategy', {}).get('strategy_name')
                )
                optimal_quantity = kelly_result['quantity']
                kelly_pct = kelly_result['kelly_pct']
            else:
                # Use default win rate and R:R
                win_probability = 0.55  # Default 55%
                risk_reward_ratio = 2.0  # Default 2:1
                
                optimal_quantity = self.kelly_sizer.calculate_position_size(
                    account_balance=account_balance,
                    max_loss_per_unit=max_loss_per_unit,
                    win_probability=win_probability,
                    risk_reward_ratio=risk_reward_ratio
                )
                kelly_pct = self.kelly_sizer.calculate_kelly(
                    win_probability,
                    risk_reward_ratio,
                    1.0
                )
            
            # If proposed quantity exists, use minimum of Kelly and proposed
            if proposed_quantity and proposed_quantity > 0:
                optimal_quantity = min(optimal_quantity, proposed_quantity)
        
        # Step 4: Check portfolio heat limits (if manager available)
        if self.portfolio_heat_manager is not None:
            # Adjust quantity for portfolio heat
            portfolio_summary = self.portfolio_heat_manager.get_portfolio_summary(position_risks)
            available_heat = portfolio_summary['available_heat']
            
            if self.kelly_sizer is not None and max_loss_per_unit and max_loss_per_unit > 0:
                # Adjust for heat
                optimal_quantity = self.kelly_sizer.adjust_position_size_for_portfolio_heat(
                    base_quantity=optimal_quantity,
                    available_heat=available_heat,
                    account_balance=self.portfolio_heat_manager.account_balance,
                    max_loss_per_unit=max_loss_per_unit
                )
            
            # Calculate position risk
            position_risk = optimal_quantity * max_loss_per_unit if max_loss_per_unit else 0.0
            
            # Check if position can be opened
            can_open, reason = self.portfolio_heat_manager.can_open_position(
                position_risk=position_risk,
                current_positions=position_risks,
                daily_pnl=portfolio_summary['daily_pnl'],
                weekly_pnl=portfolio_summary['weekly_pnl']
            )
            
            if not can_open:
                # Determine rejection reason
                approval_reason = ApprovalReason.OK
                if "portfolio heat" in reason.lower():
                    approval_reason = ApprovalReason.PORTFOLIO_HEAT_EXCEEDED
                elif "position heat" in reason.lower():
                    approval_reason = ApprovalReason.POSITION_HEAT_EXCEEDED
                elif "daily loss" in reason.lower():
                    approval_reason = ApprovalReason.DAILY_LOSS_LIMIT
                elif "weekly loss" in reason.lower():
                    approval_reason = ApprovalReason.WEEKLY_LOSS_LIMIT
                
                return ApprovalResult(
                    decision=ApprovalDecision.REJECTED,
                    reason=approval_reason,
                    approved_quantity=0,
                    original_quantity=original_quantity,
                    kelly_percentage=kelly_pct,
                    risk_amount=position_risk,
                    portfolio_heat_used=portfolio_summary['total_portfolio_heat'],
                    portfolio_heat_available=available_heat,
                    details={
                        'reason': reason,
                        'portfolio_summary': portfolio_summary
                    },
                    timestamp=timestamp
                )
            else:
                # No quantity to trade
                can_open = False
                reason = "No available capacity"
            
            # Check if optimal quantity is 0 after heat adjustment
            if optimal_quantity == 0 and (proposed_quantity or 0) > 0:
                return ApprovalResult(
                    decision=ApprovalDecision.REJECTED,
                    reason=ApprovalReason.PORTFOLIO_HEAT_EXCEEDED,
                    approved_quantity=0,
                    original_quantity=original_quantity,
                    kelly_percentage=kelly_pct,
                    risk_amount=0.0,
                    portfolio_heat_used=portfolio_summary['total_portfolio_heat'],
                    portfolio_heat_available=available_heat,
                    details={
                        'reason': f'No available heat. Current heat: {portfolio_summary["total_portfolio_heat"]:.2%}, Max: {portfolio_summary["max_portfolio_heat"]:.2%}',
                        'portfolio_summary': portfolio_summary
                    },
                    timestamp=timestamp
                )
            
            # Calculate position risk for check
            position_risk = optimal_quantity * max_loss_per_unit if max_loss_per_unit else 0.0
            
            # Check if position can be opened
            if optimal_quantity > 0:
                can_open, reason = self.portfolio_heat_manager.can_open_position(
                    position_risk=position_risk,
                    current_positions=position_risks,
                    daily_pnl=portfolio_summary['daily_pnl'],
                    weekly_pnl=portfolio_summary['weekly_pnl']
                )
                
                if not can_open:
                    # Determine rejection reason
                    approval_reason = ApprovalReason.OK
                    if "portfolio heat" in reason.lower():
                        approval_reason = ApprovalReason.PORTFOLIO_HEAT_EXCEEDED
                    elif "position heat" in reason.lower():
                        approval_reason = ApprovalReason.POSITION_HEAT_EXCEEDED
                    elif "daily loss" in reason.lower():
                        approval_reason = ApprovalReason.DAILY_LOSS_LIMIT
                    elif "weekly loss" in reason.lower():
                        approval_reason = ApprovalReason.WEEKLY_LOSS_LIMIT
                    
                    return ApprovalResult(
                        decision=ApprovalDecision.REJECTED,
                        reason=approval_reason,
                        approved_quantity=0,
                        original_quantity=original_quantity,
                        kelly_percentage=kelly_pct,
                        risk_amount=position_risk,
                        portfolio_heat_used=portfolio_summary['total_portfolio_heat'],
                        portfolio_heat_available=available_heat,
                        details={
                            'reason': reason,
                            'portfolio_summary': portfolio_summary
                        },
                        timestamp=timestamp
                    )
            
            # Approved
            approved_quantity = optimal_quantity
            risk_amount = approved_quantity * max_loss_per_unit if max_loss_per_unit else 0.0
            portfolio_heat_used = portfolio_summary['total_portfolio_heat']
            portfolio_heat_available = available_heat
            
            # Check if quantity was reduced
            decision = ApprovalDecision.APPROVED
            if original_quantity > 0 and approved_quantity < original_quantity:
                decision = ApprovalDecision.REDUCED
            
            result = ApprovalResult(
                decision=decision,
                reason=ApprovalReason.OK,
                approved_quantity=approved_quantity,
                original_quantity=original_quantity,
                kelly_percentage=kelly_pct,
                risk_amount=risk_amount,
                portfolio_heat_used=portfolio_heat_used,
                portfolio_heat_available=portfolio_heat_available,
                details={
                    'reason': 'Approved' if decision == ApprovalDecision.APPROVED else 'Approved with reduced size',
                    'portfolio_summary': portfolio_summary,
                    'kelly_calculation': {
                        'optimal_quantity': optimal_quantity,
                        'kelly_pct': kelly_pct
                    } if self.kelly_sizer else None
                },
                timestamp=timestamp
            )
        else:
            # No portfolio heat manager - approve based on Kelly only
            approved_quantity = optimal_quantity
            risk_amount = approved_quantity * max_loss_per_unit if max_loss_per_unit else 0.0
            
            decision = ApprovalDecision.APPROVED
            if original_quantity > 0 and approved_quantity < original_quantity:
                decision = ApprovalDecision.REDUCED
            
            result = ApprovalResult(
                decision=decision,
                reason=ApprovalReason.OK,
                approved_quantity=approved_quantity,
                original_quantity=original_quantity,
                kelly_percentage=kelly_pct,
                risk_amount=risk_amount,
                portfolio_heat_used=0.0,
                portfolio_heat_available=1.0,
                details={
                    'reason': 'Approved without portfolio heat checks',
                    'kelly_calculation': {
                        'optimal_quantity': optimal_quantity,
                        'kelly_pct': kelly_pct
                    } if self.kelly_sizer else None
                },
                timestamp=timestamp
            )
        
        # Add to audit log
        self.approval_log.append(result)
        
        logger.info(f"Trade {trading_decision.decision} {'approved' if result.decision == ApprovalDecision.APPROVED else 'rejected'}: "
                   f"quantity={approved_quantity}, reason={result.reason.value}")
        
        return result
    
    def _check_risk_approval(self, trading_decision: AnalysisResult) -> str:
        """Check risk agent approval status.
        
        Args:
            trading_decision: Trading decision
        
        Returns:
            "APPROVE", "VETO", or "CAUTION"
        """
        # Check agent results for risk agent decision
        agent_results = trading_decision.details.get('agent_results', {})
        
        for agent_name, agent_result in agent_results.items():
            if 'risk' in agent_name.lower():
                decision = agent_result.get('decision', 'HOLD')
                if decision == "VETO":
                    return "VETO"
                elif decision == "APPROVE":
                    return "APPROVE"
        
        # Check for explicit risk veto in details
        if trading_decision.details.get('reason') == "RISK_VETO":
            return "VETO"
        
        return "CAUTION"  # Default to caution
    
    def _convert_positions_to_risks(
        self,
        positions: List[Dict[str, Any]]
    ) -> List[PositionRisk]:
        """Convert position dictionaries to PositionRisk objects.
        
        Args:
            positions: List of position dictionaries
        
        Returns:
            List of PositionRisk objects
        """
        if PositionRisk is None:
            return []
        
        position_risks = []
        for pos in positions:
            if pos.get('status') != 'active':
                continue
            
            risk = PositionRisk(
                position_id=str(pos.get('position_id', pos.get('id', ''))),
                instrument=pos.get('instrument', pos.get('symbol', '')),
                strategy_type=pos.get('strategy_type', pos.get('strategy', 'unknown')),
                max_loss=pos.get('max_loss', pos.get('risk_amount', 0.0)),
                current_pnl=pos.get('current_pnl', pos.get('pnl', 0.0)),
                heat_percentage=pos.get('heat_percentage', 0.0),
                entry_price=pos.get('entry_price', 0.0),
                current_price=pos.get('current_price', pos.get('entry_price', 0.0)),
                quantity=pos.get('quantity', 0),
                entry_time=datetime.fromisoformat(pos['entry_time']) if isinstance(pos.get('entry_time'), str) else pos.get('entry_time', datetime.now()),
                status=pos.get('status', 'active')
            )
            position_risks.append(risk)
        
        return position_risks
    
    def get_approval_history(
        self,
        limit: int = 100
    ) -> List[ApprovalResult]:
        """Get recent approval history.
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            List of recent ApprovalResult objects
        """
        return self.approval_log[-limit:]
    
    def get_approval_stats(self) -> Dict[str, Any]:
        """Get approval statistics.
        
        Returns:
            Dictionary with approval stats
        """
        if not self.approval_log:
            return {
                'total_reviews': 0,
                'approved': 0,
                'rejected': 0,
                'reduced': 0,
                'approval_rate': 0.0
            }
        
        total = len(self.approval_log)
        approved = len([r for r in self.approval_log if r.decision == ApprovalDecision.APPROVED])
        rejected = len([r for r in self.approval_log if r.decision == ApprovalDecision.REJECTED])
        reduced = len([r for r in self.approval_log if r.decision == ApprovalDecision.REDUCED])
        
        return {
            'total_reviews': total,
            'approved': approved,
            'rejected': rejected,
            'reduced': reduced,
            'approval_rate': approved / total if total > 0 else 0.0,
            'rejection_rate': rejected / total if total > 0 else 0.0,
            'reduction_rate': reduced / total if total > 0 else 0.0
        }
