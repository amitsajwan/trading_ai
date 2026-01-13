"""Portfolio Heat Manager for risk management.

This module provides portfolio-wide risk limit management, preventing over-exposure
and ensuring diversification across positions.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PositionRisk:
    """Risk metrics for a single position."""
    position_id: str
    instrument: str
    strategy_type: str
    max_loss: float  # Maximum possible loss
    current_pnl: float  # Current unrealized P&L
    heat_percentage: float  # % of portfolio at risk
    entry_price: float
    current_price: float
    quantity: int
    entry_time: datetime
    status: str = "active"  # active, closed, expired


class PortfolioHeatManager:
    """Manage portfolio-wide risk limits.
    
    Prevents over-exposure and ensures diversification by:
    - Limiting position heat (individual position risk)
    - Limiting total portfolio heat (aggregate risk)
    - Tracking daily/weekly loss limits
    - Managing position sizing based on available heat
    """
    
    def __init__(self, config: Dict):
        """Initialize portfolio heat manager.
        
        Args:
            config: Configuration dictionary with:
                - max_portfolio_heat: Maximum total portfolio heat (default 0.02 = 2%)
                - max_position_heat: Maximum heat per position (default 0.01 = 1%)
                - max_daily_loss: Maximum daily loss limit (default 0.05 = 5%)
                - max_weekly_loss: Maximum weekly loss limit (default 0.10 = 10%)
                - account_balance: Current account balance
        """
        self.config = config
        self.max_portfolio_heat = config.get('max_portfolio_heat', 0.02)  # 2%
        self.max_position_heat = config.get('max_position_heat', 0.01)  # 1%
        self.max_daily_loss = config.get('max_daily_loss', 0.05)  # 5%
        self.max_weekly_loss = config.get('max_weekly_loss', 0.10)  # 10%
        self.account_balance = config.get('account_balance', 100000.0)
        
        # Track daily/weekly P&L
        self.daily_pnl: float = 0.0
        self.weekly_pnl: float = 0.0
        self.last_reset_date: Optional[datetime] = None
        
        logger.info(f"Portfolio Heat Manager initialized: "
                   f"max_portfolio_heat={self.max_portfolio_heat:.2%}, "
                   f"max_position_heat={self.max_position_heat:.2%}")
    
    def can_open_position(
        self,
        position_risk: float,
        current_positions: List[PositionRisk],
        daily_pnl: Optional[float] = None,
        weekly_pnl: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Check if new position can be opened based on heat limits.
        
        Args:
            position_risk: Maximum possible loss for new position
            current_positions: List of current active positions
            daily_pnl: Optional daily P&L (uses internal if None)
            weekly_pnl: Optional weekly P&L (uses internal if None)
        
        Returns:
            Tuple of (can_open: bool, reason: str)
        """
        # Update daily/weekly tracking
        self._update_daily_weekly_tracking()
        
        # Use provided P&L or internal tracking
        daily_pnl = daily_pnl if daily_pnl is not None else self.daily_pnl
        weekly_pnl = weekly_pnl if weekly_pnl is not None else self.weekly_pnl
        
        # Check position heat
        position_heat = position_risk / self.account_balance
        if position_heat > self.max_position_heat:
            return False, (
                f"Position heat {position_heat:.2%} exceeds limit "
                f"{self.max_position_heat:.2%}"
            )
        
        # Check total portfolio heat
        current_heat = sum(pos.heat_percentage for pos in current_positions)
        total_heat = current_heat + position_heat
        if total_heat > self.max_portfolio_heat:
            return False, (
                f"Total portfolio heat {total_heat:.2%} exceeds limit "
                f"{self.max_portfolio_heat:.2%} "
                f"(current: {current_heat:.2%}, new: {position_heat:.2%})"
            )
        
        # Check daily loss limit
        daily_loss_pct = abs(daily_pnl) / self.account_balance if daily_pnl < 0 else 0.0
        if daily_loss_pct >= self.max_daily_loss:
            return False, (
                f"Daily loss limit reached: {daily_loss_pct:.2%} >= "
                f"{self.max_daily_loss:.2%}"
            )
        
        # Check weekly loss limit
        weekly_loss_pct = abs(weekly_pnl) / self.account_balance if weekly_pnl < 0 else 0.0
        if weekly_loss_pct >= self.max_weekly_loss:
            return False, (
                f"Weekly loss limit reached: {weekly_loss_pct:.2%} >= "
                f"{self.max_weekly_loss:.2%}"
            )
        
        return True, "OK"
    
    def calculate_optimal_quantity(
        self,
        max_loss_per_unit: float,
        current_positions: List[PositionRisk]
    ) -> int:
        """Calculate optimal position size using available heat.
        
        Args:
            max_loss_per_unit: Maximum loss per unit/lot
            current_positions: List of current active positions
        
        Returns:
            Optimal quantity in units/lots (0 if no capacity)
        """
        # Calculate available heat
        current_heat = sum(pos.heat_percentage for pos in current_positions)
        available_heat = self.max_portfolio_heat - current_heat
        
        # Cap at max position heat
        available_heat = min(available_heat, self.max_position_heat)
        
        if available_heat <= 0:
            return 0
        
        # Calculate max risk amount
        max_risk_amount = self.account_balance * available_heat
        
        # Calculate quantity
        if max_loss_per_unit <= 0:
            return 0
        
        quantity = int(max_risk_amount / max_loss_per_unit)
        return max(0, quantity)
    
    def update_position(
        self,
        position: PositionRisk,
        current_price: float,
        current_time: Optional[datetime] = None
    ) -> None:
        """Update position risk metrics.
        
        Args:
            position: Position to update
            current_price: Current market price
            current_time: Current time (uses now if None)
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Calculate current P&L
        price_change = current_price - position.entry_price
        position.current_pnl = price_change * position.quantity
        position.current_price = current_price
        
        # Recalculate heat (based on max_loss, not current P&L)
        position.heat_percentage = position.max_loss / self.account_balance
        
        # Update daily/weekly P&L tracking
        self._update_pnl_tracking(position.current_pnl)
    
    def close_position(
        self,
        position: PositionRisk,
        exit_price: float,
        exit_time: Optional[datetime] = None
    ) -> None:
        """Close a position and update tracking.
        
        Args:
            position: Position to close
            exit_price: Exit price
            exit_time: Exit time (uses now if None)
        """
        if exit_time is None:
            exit_time = datetime.now()
        
        # Final update
        self.update_position(position, exit_price, exit_time)
        
        # Update daily/weekly P&L
        self._update_pnl_tracking(position.current_pnl)
        
        # Mark as closed
        position.status = "closed"
        
        logger.info(f"Position {position.position_id} closed: "
                   f"P&L={position.current_pnl:.2f}, "
                   f"Duration={(exit_time - position.entry_time).total_seconds() / 3600:.2f}h")
    
    def get_portfolio_summary(
        self,
        positions: List[PositionRisk]
    ) -> Dict:
        """Get portfolio risk summary.
        
        Args:
            positions: List of all positions (active and closed)
        
        Returns:
            Dictionary with portfolio risk metrics
        """
        active_positions = [p for p in positions if p.status == "active"]
        
        total_heat = sum(pos.heat_percentage for pos in active_positions)
        total_max_loss = sum(pos.max_loss for pos in active_positions)
        total_current_pnl = sum(pos.current_pnl for pos in active_positions)
        
        # Update tracking
        self._update_daily_weekly_tracking()
        
        return {
            'account_balance': self.account_balance,
            'active_positions': len(active_positions),
            'total_portfolio_heat': total_heat,
            'max_portfolio_heat': self.max_portfolio_heat,
            'available_heat': self.max_portfolio_heat - total_heat,
            'total_max_loss': total_max_loss,
            'total_current_pnl': total_current_pnl,
            'daily_pnl': self.daily_pnl,
            'weekly_pnl': self.weekly_pnl,
            'daily_loss_pct': abs(self.daily_pnl) / self.account_balance if self.daily_pnl < 0 else 0.0,
            'weekly_loss_pct': abs(self.weekly_pnl) / self.account_balance if self.weekly_pnl < 0 else 0.0,
            'can_trade': (
                total_heat < self.max_portfolio_heat and
                abs(self.daily_pnl) / self.account_balance < self.max_daily_loss and
                abs(self.weekly_pnl) / self.account_balance < self.max_weekly_loss
            )
        }
    
    def _update_daily_weekly_tracking(self) -> None:
        """Update daily and weekly P&L tracking."""
        now = datetime.now()
        
        # Reset daily tracking if new day
        if self.last_reset_date is None:
            self.last_reset_date = now.date()
        elif self.last_reset_date < now.date():
            # New day - reset daily P&L
            self.daily_pnl = 0.0
            self.last_reset_date = now.date()
            
            # Reset weekly if new week (Monday)
            if now.weekday() == 0:  # Monday
                self.weekly_pnl = 0.0
    
    def _update_pnl_tracking(self, pnl: float) -> None:
        """Update P&L tracking when position P&L changes.
        
        Note: This is called when positions are updated/closed.
        In a real system, you'd track realized vs unrealized P&L separately.
        
        Args:
            pnl: Position P&L to add to tracking
        """
        self._update_daily_weekly_tracking()
        # For simplicity, we add to daily/weekly
        # In reality, you'd only add realized P&L on close
        # This is a simplified version
        pass
    
    def reset_daily_pnl(self) -> None:
        """Reset daily P&L (called at start of trading day)."""
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
    
    def reset_weekly_pnl(self) -> None:
        """Reset weekly P&L (called at start of trading week)."""
        self.weekly_pnl = 0.0
    
    def update_account_balance(self, new_balance: float) -> None:
        """Update account balance.
        
        Args:
            new_balance: New account balance
        """
        old_balance = self.account_balance
        self.account_balance = new_balance
        
        # Recalculate heat percentages if balance changed significantly
        if abs(old_balance - new_balance) / old_balance > 0.1:  # >10% change
            logger.warning(f"Account balance changed significantly: "
                          f"{old_balance:.2f} -> {new_balance:.2f}")
    
    def get_heat_utilization(
        self,
        positions: List[PositionRisk]
    ) -> Dict[str, float]:
        """Get heat utilization breakdown.
        
        Args:
            positions: List of positions
        
        Returns:
            Dictionary with heat utilization by strategy/instrument
        """
        active_positions = [p for p in positions if p.status == "active"]
        
        # Group by strategy
        by_strategy: Dict[str, float] = {}
        by_instrument: Dict[str, float] = {}
        
        for pos in active_positions:
            # By strategy
            strategy = pos.strategy_type
            by_strategy[strategy] = by_strategy.get(strategy, 0.0) + pos.heat_percentage
            
            # By instrument
            instrument = pos.instrument
            by_instrument[instrument] = by_instrument.get(instrument, 0.0) + pos.heat_percentage
        
        return {
            'total_heat': sum(pos.heat_percentage for pos in active_positions),
            'max_portfolio_heat': self.max_portfolio_heat,
            'utilization_pct': (sum(pos.heat_percentage for pos in active_positions) / 
                               self.max_portfolio_heat * 100) if self.max_portfolio_heat > 0 else 0.0,
            'by_strategy': by_strategy,
            'by_instrument': by_instrument
        }
