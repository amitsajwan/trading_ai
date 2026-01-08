"""UI Shell contracts for dashboard and CLI interactions."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DecisionDisplay:
    """Data structure for displaying trading decisions in UI."""
    instrument: str
    signal: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 to 1.0
    reasoning: str
    timestamp: datetime
    technical_indicators: Optional[Dict[str, Any]] = None
    sentiment_score: Optional[float] = None
    macro_factors: Optional[Dict[str, Any]] = None


@dataclass
class PortfolioSummary:
    """Portfolio summary for dashboard display."""
    total_value: float
    cash_balance: float
    positions: Dict[str, Dict[str, Any]]  # instrument -> position data
    pnl_today: float
    pnl_total: float
    timestamp: datetime


@dataclass
class MarketOverview:
    """Market overview data for dashboard."""
    nifty_price: float
    banknifty_price: float
    market_status: str  # "OPEN", "CLOSED", "PRE_OPEN"
    volume_24h: int
    timestamp: datetime


class UserAction:
    """Base class for user actions from UI."""
    def __init__(self, action_type: str, **kwargs):
        self.action_type = action_type
        self.timestamp = datetime.utcnow()
        for key, value in kwargs.items():
            setattr(self, key, value)


class BuyOverride(UserAction):
    """User override to force buy signal."""
    def __init__(self, instrument: str, quantity: int, price_limit: Optional[float] = None):
        super().__init__("BUY_OVERRIDE", instrument=instrument, quantity=quantity, price_limit=price_limit)


class SellOverride(UserAction):
    """User override to force sell signal."""
    def __init__(self, instrument: str, quantity: int, price_limit: Optional[float] = None):
        super().__init__("SELL_OVERRIDE", instrument=instrument, quantity=quantity, price_limit=price_limit)


class StopLossUpdate(UserAction):
    """Update stop loss for a position."""
    def __init__(self, instrument: str, stop_loss_price: float):
        super().__init__("STOP_LOSS_UPDATE", instrument=instrument, stop_loss_price=stop_loss_price)


class RiskLimitUpdate(UserAction):
    """Update risk management limits."""
    def __init__(self, max_position_size: float, max_daily_loss: float):
        super().__init__("RISK_LIMIT_UPDATE", max_position_size=max_position_size, max_daily_loss=max_daily_loss)


class UIDataProvider(Protocol):
    """Protocol for providing data to UI components."""

    async def get_latest_decision(self) -> Optional[DecisionDisplay]:
        """Get the latest trading decision for dashboard display.

        Returns:
            DecisionDisplay with current trading recommendation, or None if no decision available
        """
        ...

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get current portfolio summary for dashboard.

        Returns:
            PortfolioSummary with positions, P&L, balances
        """
        ...

    async def get_market_overview(self) -> MarketOverview:
        """Get current market overview for dashboard header.

        Returns:
            MarketOverview with key market indicators
        """
        ...

    async def get_recent_decisions(self, limit: int = 10) -> list[DecisionDisplay]:
        """Get recent trading decisions history.

        Args:
            limit: Maximum number of recent decisions to return

        Returns:
            List of recent DecisionDisplay objects
        """
        ...

    async def get_snapshot(self) -> Dict[str, Any]:
        """Get complete system snapshot for dashboard.

        Returns:
            Dict containing latest decision, portfolio, market data, etc.
        """
        ...

    async def get_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics.

        Returns:
            Dict with trading metrics, system health, performance stats
        """
        ...


class UIDispatcher(Protocol):
    """Protocol for dispatching user actions from UI to trading engine."""

    async def submit_override(self, action: UserAction) -> Dict[str, Any]:
        """Submit a user override action to the trading engine.

        Args:
            action: UserAction to process (BuyOverride, SellOverride, etc.)

        Returns:
            Dict with action result status and any relevant data
        """
        ...

    async def pause_trading(self, reason: str = "User requested pause") -> Dict[str, Any]:
        """Pause automated trading.

        Args:
            reason: Reason for pausing trading

        Returns:
            Dict with pause status
        """
        ...

    async def resume_trading(self) -> Dict[str, Any]:
        """Resume automated trading after pause.

        Returns:
            Dict with resume status
        """
        ...

    async def emergency_stop(self, reason: str = "Emergency stop activated") -> Dict[str, Any]:
        """Emergency stop all trading activities.

        Args:
            reason: Reason for emergency stop

        Returns:
            Dict with stop status
        """
        ...

    async def publish(self, event: str, data: Dict[str, Any]) -> None:
        """Publish event to UI subscribers.

        Args:
            event: Event type/name
            data: Event data payload
        """
        ...


class UINotificationHandler(Protocol):
    """Protocol for handling UI notifications and alerts."""

    async def send_notification(self, title: str, message: str, level: str = "info") -> None:
        """Send notification to UI.

        Args:
            title: Notification title
            message: Notification message
            level: Notification level ("info", "warning", "error", "success")
        """
        ...

    async def get_pending_notifications(self) -> list[Dict[str, Any]]:
        """Get pending notifications for UI display.

        Returns:
            List of notification dictionaries
        """
        ...


__all__ = [
    "DecisionDisplay",
    "PortfolioSummary",
    "MarketOverview",
    "UserAction",
    "BuyOverride",
    "SellOverride",
    "StopLossUpdate",
    "RiskLimitUpdate",
    "UIDataProvider",
    "UIDispatcher",
    "UINotificationHandler",
]
