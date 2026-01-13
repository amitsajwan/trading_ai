"""Risk Management API endpoints for Portfolio Heat, Kelly Sizing, and Fund Manager Approval."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import risk management components
try:
    from risk_module.portfolio_heat import PortfolioHeatManager, PositionRisk
    from risk_module.position_sizer import KellyPositionSizer
    from engine_module.approval.fund_manager import (
        FundManagerApprovalLayer,
        ApprovalDecision,
        ApprovalResult
    )
except ImportError as e:
    # Handle import errors gracefully
    PortfolioHeatManager = None
    KellyPositionSizer = None
    FundManagerApprovalLayer = None
    print(f"Warning: Could not import risk modules: {e}")

router = APIRouter(prefix="/api/risk", tags=["risk"])


# Pydantic models for API
class PortfolioHeatRequest(BaseModel):
    """Request model for portfolio heat check."""
    position_risk: float
    current_positions: List[Dict[str, Any]]
    daily_pnl: Optional[float] = None
    weekly_pnl: Optional[float] = None


class KellySizingRequest(BaseModel):
    """Request model for Kelly position sizing."""
    account_balance: float
    max_loss_per_unit: float
    win_probability: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    trade_history: Optional[List[Dict[str, Any]]] = None
    strategy_type: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request model for fund manager approval."""
    trading_decision: Dict[str, Any]  # AnalysisResult as dict
    current_positions: List[Dict[str, Any]]
    proposed_quantity: Optional[int] = None
    max_loss_per_unit: Optional[float] = None
    trade_history: Optional[List[Dict[str, Any]]] = None


# Global instances (in production, these would be managed by dependency injection)
_portfolio_heat_manager: Optional[PortfolioHeatManager] = None
_kelly_sizer: Optional[KellyPositionSizer] = None
_fund_manager: Optional[FundManagerApprovalLayer] = None


def get_portfolio_heat_manager() -> Optional[PortfolioHeatManager]:
    """Get or create Portfolio Heat Manager."""
    global _portfolio_heat_manager
    if _portfolio_heat_manager is None:
        config = {
            'account_balance': 100000.0,  # Default, should come from config
            'max_portfolio_heat': 0.02,
            'max_position_heat': 0.01,
            'max_daily_loss': 0.05,
            'max_weekly_loss': 0.10
        }
        if PortfolioHeatManager:
            _portfolio_heat_manager = PortfolioHeatManager(config)
        else:
            return None  # Return None instead of raising exception
    return _portfolio_heat_manager


def get_kelly_sizer() -> Optional[KellyPositionSizer]:
    """Get or create Kelly Position Sizer."""
    global _kelly_sizer
    if _kelly_sizer is None:
        config = {
            'kelly_fraction': 0.25,
            'max_kelly': 0.30,
            'min_kelly': 0.01
        }
        if KellyPositionSizer:
            _kelly_sizer = KellyPositionSizer(config)
        else:
            return None
    return _kelly_sizer


def get_fund_manager() -> Optional[FundManagerApprovalLayer]:
    """Get or create Fund Manager Approval Layer."""
    global _fund_manager
    if _fund_manager is None:
        config = {
            'account_balance': 100000.0,
            'min_approval_confidence': 0.6,
            'require_risk_approval': True,
            'portfolio_heat_config': {
                'max_portfolio_heat': 0.02,
                'max_position_heat': 0.01,
                'max_daily_loss': 0.05,
                'max_weekly_loss': 0.10
            },
            'kelly_config': {
                'kelly_fraction': 0.25,
                'max_kelly': 0.30,
                'min_kelly': 0.01
            }
        }
        if FundManagerApprovalLayer:
            _fund_manager = FundManagerApprovalLayer(config)
        else:
            return None
    return _fund_manager


@router.get("/portfolio/summary")
async def get_portfolio_summary(
    heat_manager: Optional[PortfolioHeatManager] = Depends(get_portfolio_heat_manager)
) -> Dict[str, Any]:
    """Get portfolio risk summary."""
    if heat_manager is None:
        return {
            "status": "unavailable",
            "error": "Portfolio Heat Manager not available",
            "account_balance": 100000.0,
            "total_heat": 0.0,
            "positions": []
        }
    # Try to get positions from portfolio API
    positions = []
    try:
        # Try to fetch from portfolio API endpoint via HTTP request
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8888/api/portfolio", timeout=2.0)
            if response.status_code == 200:
                portfolio_data = response.json()
                if portfolio_data and 'positions' in portfolio_data:
                    positions = portfolio_data['positions']
    except Exception as e:
        # Fallback to empty positions if API unavailable
        logger.warning(f"Could not fetch positions for heat summary: {e}")
        positions = []
    
    # Get account balance from portfolio data or use default
    account_balance = 100000.0  # Default
    try:
        if portfolio_data:
            if 'summary' in portfolio_data:
                summary_data = portfolio_data['summary']
                account_balance = summary_data.get('total_equity', summary_data.get('total_value', 100000.0))
            elif 'account_balance' in portfolio_data:
                account_balance = portfolio_data['account_balance']
    except Exception:
        pass  # Use default
    
    # Update heat manager account balance
    heat_manager.update_account_balance(account_balance)
    
    # Convert to PositionRisk objects
    position_risks = []
    for pos in positions:
        if pos.get('status') == 'active' or not pos.get('status'):
            max_loss = pos.get('max_loss', pos.get('risk_amount', 0.0))
            # Calculate heat_percentage if not provided
            heat_percentage = pos.get('heat_percentage', 0.0)
            if heat_percentage == 0.0 and max_loss > 0 and account_balance > 0:
                heat_percentage = max_loss / account_balance
            
            risk = PositionRisk(
                position_id=str(pos.get('position_id', pos.get('id', ''))),
                instrument=pos.get('instrument', pos.get('symbol', '')),
                strategy_type=pos.get('strategy_type', pos.get('strategy', 'unknown')),
                max_loss=max_loss,
                current_pnl=pos.get('current_pnl', pos.get('pnl', pos.get('unrealized_pnl', 0.0))),
                heat_percentage=heat_percentage,
                entry_price=pos.get('entry_price', pos.get('avg_price', 0.0)),
                current_price=pos.get('current_price', pos.get('entry_price', 0.0)),
                quantity=pos.get('quantity', 0),
                entry_time=datetime.fromisoformat(pos['entry_time']) if isinstance(pos.get('entry_time'), str) else pos.get('entry_time', datetime.now()),
                status=pos.get('status', 'active')
            )
            position_risks.append(risk)
    
    summary = heat_manager.get_portfolio_summary(position_risks)
    return summary


@router.get("/portfolio/heat-utilization")
async def get_heat_utilization(
    heat_manager: Optional[PortfolioHeatManager] = Depends(get_portfolio_heat_manager)
) -> Dict[str, Any]:
    """Get heat utilization breakdown by strategy and instrument."""
    if heat_manager is None:
        return {"status": "unavailable", "error": "Portfolio Heat Manager not available"}
    
    # Get positions (same as portfolio/summary)
    positions = []
    portfolio_data = None
    try:
        # Try to fetch from portfolio API endpoint via HTTP request
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8888/api/portfolio", timeout=2.0)
            if response.status_code == 200:
                portfolio_data = response.json()
                if portfolio_data and 'positions' in portfolio_data:
                    positions = portfolio_data['positions']
    except Exception as e:
        # Fallback to empty positions if API unavailable
        logger.warning(f"Could not fetch positions for heat utilization: {e}")
        positions = []
    
    # Get account balance
    account_balance = 100000.0  # Default
    try:
        if portfolio_data:
            if 'summary' in portfolio_data:
                summary_data = portfolio_data['summary']
                account_balance = summary_data.get('total_equity', summary_data.get('total_value', 100000.0))
            elif 'account_balance' in portfolio_data:
                account_balance = portfolio_data['account_balance']
    except Exception:
        pass  # Use default
    
    # Update heat manager account balance
    heat_manager.update_account_balance(account_balance)
    
    # Convert to PositionRisk objects
    position_risks = []
    for pos in positions:
        if pos.get('status') == 'active' or not pos.get('status'):
            max_loss = pos.get('max_loss', pos.get('risk_amount', 0.0))
            # Calculate heat_percentage if not provided
            heat_percentage = pos.get('heat_percentage', 0.0)
            if heat_percentage == 0.0 and max_loss > 0 and account_balance > 0:
                heat_percentage = max_loss / account_balance
            
            risk = PositionRisk(
                position_id=str(pos.get('position_id', pos.get('id', ''))),
                instrument=pos.get('instrument', pos.get('symbol', '')),
                strategy_type=pos.get('strategy_type', pos.get('strategy', 'unknown')),
                max_loss=max_loss,
                current_pnl=pos.get('current_pnl', pos.get('pnl', pos.get('unrealized_pnl', 0.0))),
                heat_percentage=heat_percentage,
                entry_price=pos.get('entry_price', pos.get('avg_price', 0.0)),
                current_price=pos.get('current_price', pos.get('entry_price', 0.0)),
                quantity=pos.get('quantity', 0),
                entry_time=datetime.fromisoformat(pos['entry_time']) if isinstance(pos.get('entry_time'), str) else pos.get('entry_time', datetime.now()),
                status=pos.get('status', 'active')
            )
            position_risks.append(risk)
    
    summary = heat_manager.get_portfolio_summary(position_risks)
    
    # Build utilization breakdown by strategy and instrument
    by_strategy: Dict[str, float] = {}
    by_instrument: Dict[str, float] = {}
    
    for pos_risk in position_risks:
        strategy = pos_risk.strategy_type
        instrument = pos_risk.instrument
        
        by_strategy[strategy] = by_strategy.get(strategy, 0.0) + pos_risk.heat_percentage
        by_instrument[instrument] = by_instrument.get(instrument, 0.0) + pos_risk.heat_percentage
    
    utilization = {
        'total_heat': summary.get('total_portfolio_heat', 0.0),
        'max_heat': summary.get('max_portfolio_heat', 0.02),
        'available_heat': summary.get('available_heat', 0.02),
        'utilization_pct': (summary.get('total_portfolio_heat', 0.0) / summary.get('max_portfolio_heat', 0.02) * 100) if summary.get('max_portfolio_heat', 0.02) > 0 else 0.0,
        'by_strategy': by_strategy,
        'by_instrument': by_instrument
    }
    return utilization


@router.post("/portfolio/can-open-position")
async def can_open_position(
    request: PortfolioHeatRequest,
    heat_manager: Optional[PortfolioHeatManager] = Depends(get_portfolio_heat_manager)
) -> Dict[str, Any]:
    """Check if a new position can be opened based on heat limits."""
    if heat_manager is None:
        return {"can_open": False, "reason": "Portfolio Heat Manager not available"}
    
    # Convert positions to PositionRisk objects
    position_risks = []
    for pos in request.current_positions:
        if pos.get('status') == 'active':
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
    
    can_open, reason = heat_manager.can_open_position(
        position_risk=request.position_risk,
        current_positions=position_risks,
        daily_pnl=request.daily_pnl,
        weekly_pnl=request.weekly_pnl
    )
    
    return {
        'can_open': can_open,
        'reason': reason,
        'portfolio_summary': heat_manager.get_portfolio_summary(position_risks)
    }


@router.post("/portfolio/optimal-quantity")
async def calculate_optimal_quantity(
    max_loss_per_unit: float,
    current_positions: List[Dict[str, Any]] = [],
    heat_manager: PortfolioHeatManager = Depends(get_portfolio_heat_manager)
) -> Dict[str, Any]:
    """Calculate optimal position quantity based on available heat."""
    # Convert positions
    position_risks = []
    for pos in current_positions:
        if pos.get('status') == 'active':
            risk = PositionRisk(
                position_id=str(pos.get('position_id', '')),
                instrument=pos.get('instrument', ''),
                strategy_type=pos.get('strategy_type', 'unknown'),
                max_loss=pos.get('max_loss', 0.0),
                current_pnl=pos.get('current_pnl', 0.0),
                heat_percentage=pos.get('heat_percentage', 0.0),
                entry_price=pos.get('entry_price', 0.0),
                current_price=pos.get('current_price', pos.get('entry_price', 0.0)),
                quantity=pos.get('quantity', 0),
                entry_time=datetime.now(),
                status=pos.get('status', 'active')
            )
            position_risks.append(risk)
    
    quantity = heat_manager.calculate_optimal_quantity(
        max_loss_per_unit=max_loss_per_unit,
        current_positions=position_risks
    )
    
    portfolio_summary = heat_manager.get_portfolio_summary(position_risks)
    
    return {
        'optimal_quantity': quantity,
        'max_loss_per_unit': max_loss_per_unit,
        'total_risk': quantity * max_loss_per_unit,
        'portfolio_summary': portfolio_summary
    }


@router.post("/kelly/calculate")
async def calculate_kelly(
    request: KellySizingRequest,
    kelly_sizer: Optional[KellyPositionSizer] = Depends(get_kelly_sizer)
) -> Dict[str, Any]:
    """Calculate Kelly percentage and position size."""
    if kelly_sizer is None:
        return {
            'error': 'Kelly sizing module not available',
            'quantity': 0,
            'kelly_pct': 0.0,
            'win_probability': 0.55,
            'risk_reward_ratio': 2.0,
            'risk_amount': 0.0,
            'historical_stats': {}
        }
    if request.trade_history and len(request.trade_history) > 0:
        # Use historical stats
        try:
            result = kelly_sizer.calculate_position_size_from_history(
                account_balance=request.account_balance,
                max_loss_per_unit=request.max_loss_per_unit,
                trade_history=request.trade_history,
                strategy_type=request.strategy_type
            )
            return result
        except Exception as e:
            # Fallback to manual calculation
            stats = kelly_sizer.get_historical_stats(request.trade_history)
            win_prob = stats.get('win_rate', 0.55)
            rr_ratio = stats.get('risk_reward', 2.0)
    else:
        # Use provided win probability and R:R
        stats = {}
        win_prob = request.win_probability or 0.55
        rr_ratio = request.risk_reward_ratio or 2.0
    
    kelly_pct = kelly_sizer.calculate_kelly(win_prob, rr_ratio, 1.0)
    quantity = kelly_sizer.calculate_position_size(
        account_balance=request.account_balance,
        max_loss_per_unit=request.max_loss_per_unit,
        win_probability=win_prob,
        risk_reward_ratio=rr_ratio
    )
    
    if not stats:
        stats = kelly_sizer.get_historical_stats(request.trade_history or [])
    
    return {
        'quantity': quantity,
        'kelly_pct': kelly_pct,
        'win_probability': win_prob,
        'risk_reward_ratio': rr_ratio,
        'risk_amount': request.account_balance * kelly_pct,
        'historical_stats': stats
    }


@router.get("/kelly/historical-stats")
async def get_historical_stats(
    trade_history: List[Dict[str, Any]],
    strategy_type: Optional[str] = None,
    kelly_sizer: Optional[KellyPositionSizer] = Depends(get_kelly_sizer)
) -> Dict[str, Any]:
    """Get historical statistics for Kelly calculation."""
    if kelly_sizer is None:
        return {
            'error': 'Kelly sizing module not available',
            'win_rate': 0.55,
            'risk_reward': 2.0,
            'total_trades': 0,
            'avg_win': 0.0,
            'avg_loss': 0.0
        }
    stats = kelly_sizer.get_historical_stats(trade_history)
    return stats


@router.post("/approval/review")
async def review_and_approve(
    request: ApprovalRequest,
    fund_manager: Optional[FundManagerApprovalLayer] = Depends(get_fund_manager)
) -> Dict[str, Any]:
    """Review and approve/reject a trading decision."""
    if fund_manager is None:
        return {
            'error': 'Fund manager approval module not available',
            'decision': 'REJECTED',
            'reason': 'MODULE_UNAVAILABLE',
            'approved_quantity': 0,
            'original_quantity': request.proposed_quantity,
            'kelly_percentage': 0.0,
            'risk_amount': 0.0,
            'portfolio_heat_used': 0.0,
            'portfolio_heat_available': 0.0,
            'details': {'error': 'Approval module not available'},
            'timestamp': datetime.now().isoformat()
        }
    from engine_module.contracts import AnalysisResult
    
    # Convert trading_decision dict to AnalysisResult
    decision_dict = request.trading_decision
    trading_decision = AnalysisResult(
        decision=decision_dict.get('decision', 'HOLD'),
        confidence=decision_dict.get('confidence', 0.0),
        details=decision_dict.get('details', {}),
        agent=decision_dict.get('agent'),
        options_strategy=decision_dict.get('options_strategy')
    )
    
    # Get approval result
    result = await fund_manager.review_and_approve(
        trading_decision=trading_decision,
        current_positions=request.current_positions,
        trade_history=request.trade_history,
        proposed_quantity=request.proposed_quantity,
        max_loss_per_unit=request.max_loss_per_unit
    )
    
    # Convert ApprovalResult to dict
    return {
        'decision': result.decision.value,
        'reason': result.reason.value,
        'approved_quantity': result.approved_quantity,
        'original_quantity': result.original_quantity,
        'kelly_percentage': result.kelly_percentage,
        'risk_amount': result.risk_amount,
        'portfolio_heat_used': result.portfolio_heat_used,
        'portfolio_heat_available': result.portfolio_heat_available,
        'details': result.details,
        'timestamp': result.timestamp.isoformat()
    }


@router.get("/approval/history")
async def get_approval_history(
    limit: int = 100,
    fund_manager: Optional[FundManagerApprovalLayer] = Depends(get_fund_manager)
) -> Dict[str, Any]:
    """Get recent approval history."""
    if fund_manager is None:
        return {
            'error': 'Fund manager approval module not available',
            'history': [],
            'count': 0
        }
    history = fund_manager.get_approval_history(limit=limit)
    
    return {
        'history': [
            {
                'decision': r.decision.value,
                'reason': r.reason.value,
                'approved_quantity': r.approved_quantity,
                'kelly_percentage': r.kelly_percentage,
                'risk_amount': r.risk_amount,
                'timestamp': r.timestamp.isoformat()
            }
            for r in history
        ],
        'count': len(history)
    }


@router.get("/approval/stats")
async def get_approval_stats(
    fund_manager: Optional[FundManagerApprovalLayer] = Depends(get_fund_manager)
) -> Dict[str, Any]:
    """Get approval statistics."""
    if fund_manager is None:
        return {
            'error': 'Fund manager approval module not available',
            'total_approvals': 0,
            'total_rejections': 0,
            'approval_rate': 0.0,
            'avg_kelly_percentage': 0.0,
            'avg_risk_amount': 0.0
        }
    stats = fund_manager.get_approval_stats()
    return stats
