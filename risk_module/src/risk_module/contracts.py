"""Risk management contracts and data structures."""

from dataclasses import dataclass
from typing import Dict, Any, Protocol, runtime_checkable
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    """Risk assessment result."""
    can_trade: bool
    risk_level: RiskLevel
    risk_score: float
    warnings: list[str]
    recommendations: list[str]
    position_limit: int
    max_risk_amount: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'can_trade': self.can_trade,
            'risk_level': self.risk_level.value,
            'risk_score': self.risk_score,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'position_limit': self.position_limit,
            'max_risk_amount': self.max_risk_amount,
            'details': self.details
        }


@runtime_checkable
class RiskProvider(Protocol):
    """Protocol for risk data providers."""

    async def get_portfolio_value(self) -> float:
        """Get current portfolio value."""
        ...

    async def get_open_positions(self) -> Dict[str, Any]:
        """Get current open positions."""
        ...

    async def get_daily_pnl(self) -> float:
        """Get daily P&L."""
        ...

