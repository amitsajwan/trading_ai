"""Unit tests for Fund Manager Approval Layer."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from engine_module.approval.fund_manager import (
    FundManagerApprovalLayer,
    ApprovalDecision,
    ApprovalReason,
    ApprovalResult
)
from engine_module.contracts import AnalysisResult


class TestFundManagerApprovalLayer:
    """Tests for FundManagerApprovalLayer."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        config = {
            'account_balance': 100000.0
        }
        layer = FundManagerApprovalLayer(config)
        
        assert layer.min_approval_confidence == 0.6
        assert layer.require_risk_approval is True
        assert layer.portfolio_heat_manager is not None
        assert layer.kelly_sizer is not None
        assert len(layer.approval_log) == 0
    
    def test_initialization_custom_config(self):
        """Test initialization with custom config."""
        config = {
            'account_balance': 200000.0,
            'min_approval_confidence': 0.7,
            'require_risk_approval': False,
            'portfolio_heat_config': {
                'max_portfolio_heat': 0.03
            },
            'kelly_config': {
                'kelly_fraction': 0.5
            }
        }
        layer = FundManagerApprovalLayer(config)
        
        assert layer.min_approval_confidence == 0.7
        assert layer.require_risk_approval is False
        assert layer.portfolio_heat_manager.max_portfolio_heat == 0.03
        assert layer.kelly_sizer.kelly_fraction == 0.5
    
    @pytest.mark.asyncio
    async def test_review_and_approve_low_confidence(self):
        """Test approval rejects low confidence decisions."""
        config = {'account_balance': 100000.0, 'min_approval_confidence': 0.7}
        layer = FundManagerApprovalLayer(config)
        
        decision = AnalysisResult(
            decision="BUY",
            confidence=0.5,  # Below 0.7 threshold
            details={},
            agent=None
        )
        
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=[],
            proposed_quantity=10,
            max_loss_per_unit=100.0
        )
        
        assert result.decision == ApprovalDecision.REJECTED
        assert result.approved_quantity == 0
        assert "Confidence" in result.details['reason']
    
    @pytest.mark.asyncio
    async def test_review_and_approve_risk_veto(self):
        """Test approval rejects when risk agent vetoes."""
        config = {
            'account_balance': 100000.0,
            'require_risk_approval': True
        }
        layer = FundManagerApprovalLayer(config)
        
        decision = AnalysisResult(
            decision="BUY",
            confidence=0.75,
            details={
                'reason': 'RISK_VETO',
                'agent_results': {
                    'risk': {'decision': 'VETO', 'confidence': 0.9}
                }
            },
            agent=None
        )
        
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=[],
            proposed_quantity=10,
            max_loss_per_unit=100.0
        )
        
        assert result.decision == ApprovalDecision.REJECTED
        assert result.reason == ApprovalReason.CONFLICTING_RISK_ASSESSMENT
        assert result.approved_quantity == 0
    
    @pytest.mark.asyncio
    async def test_review_and_approve_success(self):
        """Test successful approval."""
        config = {'account_balance': 100000.0}
        layer = FundManagerApprovalLayer(config)
        
        decision = AnalysisResult(
            decision="BUY",
            confidence=0.75,
            details={
                'agent_results': {
                    'risk': {'decision': 'APPROVE', 'confidence': 0.8}
                }
            },
            agent=None
        )
        
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=[],
            proposed_quantity=10,
            max_loss_per_unit=100.0
        )
        
        assert result.decision == ApprovalDecision.APPROVED
        assert result.reason == ApprovalReason.OK
        assert result.approved_quantity > 0
        assert result.approved_quantity <= 10  # May be reduced by Kelly/heat
    
    @pytest.mark.asyncio
    async def test_review_and_approve_portfolio_heat_exceeded(self):
        """Test approval rejects when portfolio heat exceeded."""
        config = {
            'account_balance': 100000.0,
            'portfolio_heat_config': {
                'max_portfolio_heat': 0.02  # 2%
            }
        }
        layer = FundManagerApprovalLayer(config)
        
        # Create position at max heat
        positions = [
            {
                'position_id': '1',
                'instrument': 'BANKNIFTY',
                'strategy_type': 'iron_condor',
                'max_loss': 2000.0,  # 2% of 100000
                'current_pnl': 0.0,
                'heat_percentage': 0.02,
                'entry_price': 45000.0,
                'current_price': 45000.0,
                'quantity': 25,
                'entry_time': datetime.now().isoformat(),
                'status': 'active'
            }
        ]
        
        decision = AnalysisResult(
            decision="BUY",
            confidence=0.75,
            details={'agent_results': {'risk': {'decision': 'APPROVE'}}},
            agent=None
        )
        
        # Proposed quantity would require 1000 risk (10 * 100)
        # But portfolio is already at max (2% = 2000)
        # So even 1 unit would exceed the limit
        # Portfolio already at max (2%), so even 1 unit would exceed
        # But Kelly might calculate a quantity that gets reduced to 0
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=positions,
            proposed_quantity=1,  # Even 1 unit exceeds
            max_loss_per_unit=100.0
        )
        
        # Should be rejected due to no available heat
        assert result.decision == ApprovalDecision.REJECTED
        assert result.reason in [ApprovalReason.PORTFOLIO_HEAT_EXCEEDED, ApprovalReason.POSITION_HEAT_EXCEEDED]
        assert result.approved_quantity == 0
    
    @pytest.mark.asyncio
    async def test_review_and_approve_daily_loss_limit(self):
        """Test approval rejects when daily loss limit reached."""
        config = {
            'account_balance': 100000.0,
            'portfolio_heat_config': {
                'max_daily_loss': 0.05  # 5%
            }
        }
        layer = FundManagerApprovalLayer(config)
        
        # Set daily P&L to exceed limit
        layer.portfolio_heat_manager.daily_pnl = -6000.0  # -6% loss
        
        decision = AnalysisResult(
            decision="BUY",
            confidence=0.75,
            details={'agent_results': {'risk': {'decision': 'APPROVE'}}},
            agent=None
        )
        
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=[],
            proposed_quantity=10,
            max_loss_per_unit=100.0
        )
        
        assert result.decision == ApprovalDecision.REJECTED
        assert result.reason == ApprovalReason.DAILY_LOSS_LIMIT
    
    @pytest.mark.asyncio
    async def test_review_and_approve_with_kelly_calculation(self):
        """Test approval uses Kelly calculation for position sizing."""
        config = {'account_balance': 100000.0}
        layer = FundManagerApprovalLayer(config)
        
        trade_history = [
            {'pnl': 500.0, 'strategy_type': 'iron_condor'},
            {'pnl': 300.0, 'strategy_type': 'iron_condor'},
            {'pnl': -200.0, 'strategy_type': 'iron_condor'}
        ]
        
        decision = AnalysisResult(
            decision="IRON_CONDOR",
            confidence=0.75,
            details={
                'agent_results': {'risk': {'decision': 'APPROVE'}},
                'strategy': {'strategy_name': 'iron_condor'}
            },
            agent=None
        )
        
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=[],
            trade_history=trade_history,
            proposed_quantity=10,  # Provide proposed quantity
            max_loss_per_unit=100.0
        )
        
        # Should approve (may be with adjusted quantity from Kelly)
        assert result.decision in [ApprovalDecision.APPROVED, ApprovalDecision.REDUCED]
        assert result.kelly_percentage > 0.0 or result.approved_quantity > 0
        # Kelly calculation may be in details if Kelly was used
        if 'kelly_calculation' in result.details:
            assert result.details['kelly_calculation'] is not None
    
    @pytest.mark.asyncio
    async def test_review_and_approve_quantity_reduced(self):
        """Test approval reduces quantity when necessary."""
        config = {
            'account_balance': 100000.0,
            'portfolio_heat_config': {
                'max_portfolio_heat': 0.02  # 2%
            }
        }
        layer = FundManagerApprovalLayer(config)
        
        # Existing position with 1% heat
        positions = [
            {
                'position_id': '1',
                'instrument': 'BANKNIFTY',
                'strategy_type': 'iron_condor',
                'max_loss': 1000.0,  # 1%
                'current_pnl': 0.0,
                'heat_percentage': 0.01,
                'entry_price': 45000.0,
                'current_price': 45000.0,
                'quantity': 25,
                'entry_time': datetime.now().isoformat(),
                'status': 'active'
            }
        ]
        
        decision = AnalysisResult(
            decision="BUY",
            confidence=0.75,
            details={'agent_results': {'risk': {'decision': 'APPROVE'}}},
            agent=None
        )
        
        # Propose large quantity
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=positions,
            proposed_quantity=50,  # Large quantity
            max_loss_per_unit=100.0
        )
        
        # Should be approved but possibly reduced
        assert result.decision in [ApprovalDecision.APPROVED, ApprovalDecision.REDUCED]
        if result.approved_quantity < 50:
            assert result.decision == ApprovalDecision.REDUCED
            assert result.original_quantity == 50
    
    def test_convert_positions_to_risks(self):
        """Test position conversion to PositionRisk."""
        config = {'account_balance': 100000.0}
        layer = FundManagerApprovalLayer(config)
        
        positions = [
            {
                'position_id': '1',
                'instrument': 'BANKNIFTY',
                'strategy_type': 'iron_condor',
                'max_loss': 1000.0,
                'current_pnl': 500.0,
                'heat_percentage': 0.01,
                'entry_price': 45000.0,
                'current_price': 45200.0,
                'quantity': 25,
                'entry_time': datetime.now().isoformat(),
                'status': 'active'
            },
            {
                'position_id': '2',
                'instrument': 'NIFTY',
                'strategy_type': 'bull_call_spread',
                'max_loss': 500.0,
                'current_pnl': -200.0,
                'heat_percentage': 0.005,
                'entry_price': 20000.0,
                'current_price': 19920.0,
                'quantity': 50,
                'entry_time': datetime.now().isoformat(),
                'status': 'closed'  # Should be skipped
            }
        ]
        
        risks = layer._convert_positions_to_risks(positions)
        
        assert len(risks) == 1  # Only active positions
        assert risks[0].position_id == '1'
        assert risks[0].instrument == 'BANKNIFTY'
        assert risks[0].max_loss == 1000.0
    
    def test_get_approval_history(self):
        """Test approval history retrieval."""
        config = {'account_balance': 100000.0}
        layer = FundManagerApprovalLayer(config)
        
        # Create some approval results
        result1 = ApprovalResult(
            decision=ApprovalDecision.APPROVED,
            reason=ApprovalReason.OK,
            approved_quantity=10,
            original_quantity=10,
            kelly_percentage=0.1,
            risk_amount=1000.0,
            portfolio_heat_used=0.01,
            portfolio_heat_available=0.01,
            details={},
            timestamp=datetime.now()
        )
        layer.approval_log.append(result1)
        
        history = layer.get_approval_history(limit=10)
        
        assert len(history) == 1
        assert history[0].decision == ApprovalDecision.APPROVED
    
    def test_get_approval_stats(self):
        """Test approval statistics."""
        config = {'account_balance': 100000.0}
        layer = FundManagerApprovalLayer(config)
        
        # Add various results
        layer.approval_log.append(ApprovalResult(
            decision=ApprovalDecision.APPROVED,
            reason=ApprovalReason.OK,
            approved_quantity=10,
            original_quantity=10,
            kelly_percentage=0.1,
            risk_amount=1000.0,
            portfolio_heat_used=0.01,
            portfolio_heat_available=0.01,
            details={},
            timestamp=datetime.now()
        ))
        layer.approval_log.append(ApprovalResult(
            decision=ApprovalDecision.REJECTED,
            reason=ApprovalReason.PORTFOLIO_HEAT_EXCEEDED,
            approved_quantity=0,
            original_quantity=10,
            kelly_percentage=0.1,
            risk_amount=1000.0,
            portfolio_heat_used=0.02,
            portfolio_heat_available=0.0,
            details={},
            timestamp=datetime.now()
        ))
        layer.approval_log.append(ApprovalResult(
            decision=ApprovalDecision.REDUCED,
            reason=ApprovalReason.OK,
            approved_quantity=5,
            original_quantity=10,
            kelly_percentage=0.1,
            risk_amount=500.0,
            portfolio_heat_used=0.01,
            portfolio_heat_available=0.01,
            details={},
            timestamp=datetime.now()
        ))
        
        stats = layer.get_approval_stats()
        
        assert stats['total_reviews'] == 3
        assert stats['approved'] == 1
        assert stats['rejected'] == 1
        assert stats['reduced'] == 1
        assert stats['approval_rate'] == pytest.approx(1.0 / 3.0, abs=0.01)
    
    @pytest.mark.asyncio
    async def test_review_and_approve_no_portfolio_heat_manager(self):
        """Test approval works without portfolio heat manager."""
        # Mock scenario where imports fail
        import sys
        original_heat = sys.modules.get('risk_module.portfolio_heat')
        
        config = {'account_balance': 100000.0}
        layer = FundManagerApprovalLayer(config)
        
        # Manually set to None to simulate import failure
        layer.portfolio_heat_manager = None
        
        decision = AnalysisResult(
            decision="BUY",
            confidence=0.75,
            details={'agent_results': {'risk': {'decision': 'APPROVE'}}},
            agent=None
        )
        
        result = await layer.review_and_approve(
            trading_decision=decision,
            current_positions=[],
            proposed_quantity=10,
            max_loss_per_unit=100.0
        )
        
        # Should still approve based on Kelly only
        assert result.decision == ApprovalDecision.APPROVED
        assert result.portfolio_heat_used == 0.0
