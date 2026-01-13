"""Kelly Criterion Position Sizer for optimal position sizing.

This module implements Kelly Criterion for calculating optimal position sizes
based on historical win rate, risk/reward ratio, and account balance.
"""

import logging
import math
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class KellyPositionSizer:
    """Calculate position sizes using Kelly Criterion.
    
    The Kelly Criterion determines the optimal fraction of capital to risk
    on each trade based on win probability and risk/reward ratio.
    
    Formula: K = (p*b - q) / b
    where:
        p = win probability
        q = loss probability (1-p)
        b = win/loss ratio (reward/risk)
    
    For safety, we use fractional Kelly (default 1/4 Kelly).
    """
    
    def __init__(self, config: Dict):
        """Initialize Kelly Position Sizer.
        
        Args:
            config: Configuration dictionary with:
                - kelly_fraction: Fraction of Kelly to use (default 0.25 = 1/4 Kelly)
                - max_kelly: Maximum Kelly percentage to allow (default 0.30 = 30%)
                - min_kelly: Minimum Kelly percentage to trade (default 0.01 = 1%)
        """
        self.config = config
        self.kelly_fraction = config.get('kelly_fraction', 0.25)  # 1/4 Kelly
        self.max_kelly = config.get('max_kelly', 0.30)  # Never exceed 30%
        self.min_kelly = config.get('min_kelly', 0.01)  # Minimum 1% to trade
        
        logger.info(f"Kelly Position Sizer initialized: "
                   f"kelly_fraction={self.kelly_fraction}, "
                   f"max_kelly={self.max_kelly:.2%}, "
                   f"min_kelly={self.min_kelly:.2%}")
    
    def calculate_kelly(
        self,
        win_probability: float,
        win_amount: float,
        loss_amount: float
    ) -> float:
        """Calculate Kelly percentage.
        
        Args:
            win_probability: Probability of winning (0.0 to 1.0)
            win_amount: Average win amount
            loss_amount: Average loss amount (positive value)
        
        Returns:
            Kelly percentage (0.0 to max_kelly)
        """
        if win_probability <= 0.0 or win_probability >= 1.0:
            return 0.0
        
        if loss_amount <= 0.0:
            return 0.0
        
        # Calculate win/loss ratio
        b = win_amount / loss_amount if loss_amount > 0 else 0.0
        
        if b <= 0.0:
            return 0.0
        
        # Kelly formula: K = (p*b - q) / b
        q = 1 - win_probability
        kelly = (win_probability * b - q) / b
        
        # Apply Kelly fraction for safety
        adjusted_kelly = kelly * self.kelly_fraction
        
        # Cap at maximum
        adjusted_kelly = min(adjusted_kelly, self.max_kelly)
        
        # Never go negative
        adjusted_kelly = max(0.0, adjusted_kelly)
        
        return adjusted_kelly
    
    def calculate_position_size(
        self,
        account_balance: float,
        max_loss_per_unit: float,
        win_probability: float,
        risk_reward_ratio: float
    ) -> int:
        """Calculate position size in units/lots.
        
        Args:
            account_balance: Current account balance
            max_loss_per_unit: Maximum loss per unit/lot
            win_probability: Probability of winning (0.0 to 1.0)
            risk_reward_ratio: Risk/reward ratio (reward/risk)
        
        Returns:
            Optimal quantity in units/lots (0 if Kelly too low)
        """
        # Calculate Kelly percentage
        kelly_pct = self.calculate_kelly(
            win_probability,
            risk_reward_ratio,  # win_amount (relative to risk)
            1.0  # loss_amount (baseline)
        )
        
        if kelly_pct < self.min_kelly:
            return 0
        
        # Calculate risk amount
        risk_amount = account_balance * kelly_pct
        
        # Calculate quantity
        if max_loss_per_unit <= 0:
            return 0
        
        quantity = int(risk_amount / max_loss_per_unit)
        return max(0, quantity)
    
    def get_historical_stats(
        self,
        trade_history: List[Dict]
    ) -> Dict[str, float]:
        """Calculate historical win rate and avg R:R from trade history.
        
        Args:
            trade_history: List of trade dictionaries with 'pnl' key
        
        Returns:
            Dictionary with:
                - win_rate: Historical win rate (0.0 to 1.0)
                - avg_win: Average win amount
                - avg_loss: Average loss amount (positive)
                - risk_reward: Risk/reward ratio (avg_win/avg_loss)
        """
        if not trade_history:
            return {
                'win_rate': 0.50,  # Default to 50% if no history
                'avg_win': 1.0,
                'avg_loss': 1.0,
                'risk_reward': 1.0
            }
        
        wins = [t for t in trade_history if t.get('pnl', 0) > 0]
        losses = [t for t in trade_history if t.get('pnl', 0) < 0]
        
        total_trades = len(trade_history)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.5
        
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 1.0
        avg_loss = abs(sum(t['pnl'] for t in losses) / len(losses)) if losses else 1.0
        
        risk_reward = avg_win / avg_loss if avg_loss > 0 else 1.0
        
        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'risk_reward': risk_reward
        }
    
    def calculate_position_size_from_history(
        self,
        account_balance: float,
        max_loss_per_unit: float,
        trade_history: List[Dict],
        strategy_type: Optional[str] = None
    ) -> Dict[str, any]:
        """Calculate position size using historical statistics.
        
        Args:
            account_balance: Current account balance
            max_loss_per_unit: Maximum loss per unit/lot
            trade_history: List of trade dictionaries with 'pnl' key
            strategy_type: Optional strategy type to filter history
        
        Returns:
            Dictionary with:
                - quantity: Optimal position size
                - kelly_pct: Kelly percentage used
                - win_rate: Historical win rate
                - risk_reward: Historical risk/reward ratio
                - risk_amount: Total risk amount
        """
        # Filter by strategy if specified
        if strategy_type:
            filtered_history = [
                t for t in trade_history
                if t.get('strategy_type') == strategy_type
            ]
        else:
            filtered_history = trade_history
        
        # Get historical stats
        stats = self.get_historical_stats(filtered_history)
        
        # Calculate position size
        quantity = self.calculate_position_size(
            account_balance,
            max_loss_per_unit,
            stats['win_rate'],
            stats['risk_reward']
        )
        
        # Calculate Kelly percentage used
        kelly_pct = self.calculate_kelly(
            stats['win_rate'],
            stats['risk_reward'],
            1.0
        )
        
        risk_amount = account_balance * kelly_pct if kelly_pct > 0 else 0.0
        
        return {
            'quantity': quantity,
            'kelly_pct': kelly_pct,
            'win_rate': stats['win_rate'],
            'risk_reward': stats['risk_reward'],
            'risk_amount': risk_amount,
            'avg_win': stats['avg_win'],
            'avg_loss': stats['avg_loss']
        }
    
    def validate_position_size(
        self,
        quantity: int,
        max_loss_per_unit: float,
        account_balance: float,
        min_quantity: int = 1
    ) -> tuple[bool, str]:
        """Validate position size meets requirements.
        
        Args:
            quantity: Proposed position size
            max_loss_per_unit: Maximum loss per unit
            account_balance: Account balance
            min_quantity: Minimum quantity to trade
        
        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        if quantity < min_quantity:
            return False, f"Quantity {quantity} below minimum {min_quantity}"
        
        if max_loss_per_unit <= 0:
            return False, "Max loss per unit must be positive"
        
        total_risk = quantity * max_loss_per_unit
        risk_pct = total_risk / account_balance if account_balance > 0 else 0.0
        
        # Check if exceeds max Kelly
        if risk_pct > self.max_kelly:
            return False, (
                f"Position risk {risk_pct:.2%} exceeds max Kelly "
                f"{self.max_kelly:.2%}"
            )
        
        return True, "OK"
    
    def adjust_position_size_for_portfolio_heat(
        self,
        base_quantity: int,
        available_heat: float,
        account_balance: float,
        max_loss_per_unit: float
    ) -> int:
        """Adjust position size to respect portfolio heat limits.
        
        Args:
            base_quantity: Base quantity from Kelly calculation
            available_heat: Available portfolio heat (0.0 to 1.0)
            account_balance: Account balance
            max_loss_per_unit: Maximum loss per unit
        
        Returns:
            Adjusted quantity respecting heat limits
        """
        # Calculate max quantity from available heat
        max_risk_amount = account_balance * available_heat
        
        if max_loss_per_unit <= 0:
            return 0
        
        max_quantity_from_heat = int(max_risk_amount / max_loss_per_unit)
        
        # Use minimum of Kelly quantity and heat limit
        adjusted_quantity = min(base_quantity, max_quantity_from_heat)
        
        return max(0, adjusted_quantity)
