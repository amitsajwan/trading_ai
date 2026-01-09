"""User module contracts for account management, portfolios, and trading."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Protocol, Any
from decimal import Decimal


@dataclass
class UserAccount:
    """User account information."""
    user_id: str
    email: str
    full_name: str
    created_at: datetime
    is_active: bool = True
    risk_profile: str = "moderate"  # conservative, moderate, aggressive
    max_daily_loss_pct: float = 5.0  # Max daily loss as % of capital
    max_position_size_pct: float = 10.0  # Max position size as % of capital
    preferences: Dict[str, Any] = None


@dataclass
class AccountBalance:
    """Account balance and margin information."""
    user_id: str
    cash_balance: Decimal
    margin_available: Decimal
    margin_used: Decimal
    total_equity: Decimal
    day_pnl: Decimal
    total_pnl: Decimal
    last_updated: datetime


@dataclass
class Position:
    """Portfolio position (stock, option, future)."""
    user_id: str
    instrument: str
    instrument_type: str  # "stock", "option", "future"
    quantity: int
    average_price: Decimal
    current_price: Optional[Decimal]
    market_value: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    realized_pnl: Decimal
    last_updated: datetime

    # Option-specific fields
    strike_price: Optional[Decimal] = None
    expiry_date: Optional[datetime] = None
    option_type: Optional[str] = None  # "CE", "PE"


@dataclass
class Trade:
    """Executed trade record."""
    user_id: str
    trade_id: str
    order_id: str
    instrument: str
    side: str  # "BUY", "SELL"
    quantity: int
    price: Decimal
    order_type: str  # "MARKET", "LIMIT", "SL", "SL-M"
    timestamp: datetime
    status: str  # "EXECUTED", "PENDING", "CANCELLED", "FAILED"
    broker_fees: Decimal
    exchange_fees: Decimal

    # Option-specific
    strike_price: Optional[Decimal] = None
    expiry_date: Optional[datetime] = None
    option_type: Optional[str] = None

    # Risk management
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    risk_amount: Optional[Decimal] = None

    # Link back to originating signal (optional)
    signal_id: Optional[str] = None


@dataclass
class RiskProfile:
    """User risk profile configuration."""
    profile_name: str
    max_daily_loss_pct: float
    max_position_size_pct: float
    max_sector_exposure_pct: float
    max_single_stock_pct: float
    max_options_exposure_pct: float
    required_risk_reward_ratio: float
    max_open_positions: int
    max_leverage: float
    stop_loss_required: bool
    diversification_required: bool


@dataclass
class PortfolioSummary:
    """Portfolio summary for dashboard."""
    user_id: str
    total_value: Decimal
    cash_balance: Decimal
    margin_available: Decimal
    day_pnl: Decimal
    total_pnl: Decimal
    positions_count: int
    winning_positions: int
    losing_positions: int
    risk_exposure_pct: float
    last_updated: datetime


@dataclass
class TradeExecutionRequest:
    """Request to execute a trade."""
    user_id: str
    instrument: str
    side: str  # "BUY", "SELL"
    quantity: int
    order_type: str  # "MARKET", "LIMIT"
    price: Optional[Decimal] = None  # Required for LIMIT orders
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None

    # Option-specific
    strike_price: Optional[Decimal] = None
    expiry_date: Optional[datetime] = None
    option_type: Optional[str] = None


@dataclass
class TradeExecutionResult:
    """Result of trade execution."""
    success: bool
    trade_id: Optional[str] = None
    order_id: Optional[str] = None
    executed_price: Optional[Decimal] = None
    executed_quantity: Optional[int] = None
    message: str = ""
    error_code: Optional[str] = None


class UserStore(Protocol):
    """Protocol for user account storage."""

    async def create_user(self, user: UserAccount) -> bool:
        """Create new user account."""
        ...

    async def get_user(self, user_id: str) -> Optional[UserAccount]:
        """Get user account by ID."""
        ...

    async def update_user(self, user: UserAccount) -> bool:
        """Update user account."""
        ...

    async def get_user_balance(self, user_id: str) -> Optional[AccountBalance]:
        """Get user account balance."""
        ...

    async def update_balance(self, user_id: str, balance: AccountBalance) -> bool:
        """Update user account balance."""
        ...


class PortfolioStore(Protocol):
    """Protocol for portfolio and position storage."""

    async def add_position(self, position: Position) -> bool:
        """Add or update position."""
        ...

    async def get_position(self, user_id: str, instrument: str) -> Optional[Position]:
        """Get position for user and instrument."""
        ...

    async def get_user_positions(self, user_id: str) -> List[Position]:
        """Get all positions for user."""
        ...

    async def update_position(self, position: Position) -> bool:
        """Update existing position."""
        ...

    async def close_position(self, user_id: str, instrument: str) -> bool:
        """Close position (set quantity to 0)."""
        ...

    async def get_portfolio_summary(self, user_id: str) -> PortfolioSummary:
        """Get portfolio summary for user."""
        ...


class TradeStore(Protocol):
    """Protocol for trade history storage."""

    async def record_trade(self, trade: Trade) -> bool:
        """Record executed trade."""
        ...

    async def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID."""
        ...

    async def get_user_trades(self, user_id: str, limit: int = 100) -> List[Trade]:
        """Get recent trades for user."""
        ...

    async def get_trades_by_instrument(self, user_id: str, instrument: str) -> List[Trade]:
        """Get trades for specific instrument."""
        ...

    async def get_trades_in_date_range(self, user_id: str, start_date: datetime,
                                     end_date: datetime) -> List[Trade]:
        """Get trades within date range."""
        ...


class RiskManager(Protocol):
    """Protocol for risk management and position sizing."""

    async def validate_trade_risk(self, user_id: str, trade_request: TradeExecutionRequest) -> Dict[str, Any]:
        """Validate if trade meets risk criteria.

        Returns dict with 'approved': bool and 'reasons': list of strings
        """
        ...

    async def calculate_position_size(self, user_id: str, instrument: str,
                                    risk_amount: Decimal, stop_loss_price: Decimal) -> int:
        """Calculate position size based on risk management rules."""
        ...

    async def check_portfolio_risk_limits(self, user_id: str) -> Dict[str, Any]:
        """Check if portfolio meets risk limits.

        Returns dict with limit violations and recommendations
        """
        ...


class TradeExecutor(Protocol):
    """Protocol for executing trades."""

    async def execute_trade(self, trade_request: TradeExecutionRequest) -> TradeExecutionResult:
        """Execute trade through broker API."""
        ...

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of pending order."""
        ...

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        ...


class PnLAnalytics(Protocol):
    """Protocol for P&L calculations and analytics."""

    async def calculate_realized_pnl(self, user_id: str, start_date: datetime,
                                   end_date: datetime) -> Decimal:
        """Calculate realized P&L for date range."""
        ...

    async def calculate_unrealized_pnl(self, user_id: str) -> Decimal:
        """Calculate unrealized P&L from current positions."""
        ...

    async def get_performance_metrics(self, user_id: str, timeframe: str = "1M") -> Dict[str, Any]:
        """Get performance metrics (Sharpe ratio, win rate, etc.)."""
        ...

    async def get_trade_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get trading statistics (win rate, avg profit, etc.)."""
        ...


__all__ = [
    "UserAccount",
    "AccountBalance",
    "Position",
    "Trade",
    "RiskProfile",
    "PortfolioSummary",
    "TradeExecutionRequest",
    "TradeExecutionResult",
    "UserStore",
    "PortfolioStore",
    "TradeStore",
    "RiskManager",
    "TradeExecutor",
    "PnLAnalytics",
]

