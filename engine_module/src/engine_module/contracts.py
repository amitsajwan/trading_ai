"""Orchestrator and agent contracts for options trading."""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Any, Dict, List, Optional
from enum import Enum


class OptionsStrategy(Enum):
    """Options trading strategies."""
    CONDOR = "condor"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    IRON_CONDOR = "iron_condor"
    BUTTERFLY = "butterfly"
    CALENDAR_SPREAD = "calendar_spread"
    HOLD = "hold"


@dataclass
class OptionsLeg:
    """Individual options leg in a strategy."""
    strike_price: float
    option_type: str  # 'CE' for call, 'PE' for put
    position: str  # 'BUY' or 'SELL'
    quantity: int
    premium: float = 0.0


@dataclass
class OptionsStrategyDetails:
    """Complete options strategy specification."""
    strategy_type: OptionsStrategy
    underlying: str  # e.g., "BANKNIFTY24JANFUT"
    expiry: str  # e.g., "2024-01-25"
    legs: List[OptionsLeg]
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_points: List[float] = None
    risk_reward_ratio: float = 0.0
    margin_required: float = 0.0


@dataclass
class AnalysisResult:
    decision: str  # Now can be strategy name or "HOLD"
    confidence: float
    details: dict[str, Any] | None = None
    options_strategy: OptionsStrategyDetails | None = None
    # Optional agent identifier (populated by orchestrator when agents run)
    agent: str | None = None


@dataclass
class TechnicalIndicators:
    """Container for calculated technical indicators."""
    rsi: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    adx: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    volume_sma: float | None = None
    volume_ratio: float | None = None
    price_change_pct: float | None = None
    volatility: float | None = None
    timestamp: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@runtime_checkable
class TechnicalDataProvider(Protocol):
    """Protocol for technical data providers."""
    async def get_technical_indicators(self, symbol: str, periods: int = 100) -> TechnicalIndicators:
        """Get latest technical indicators for symbol."""
        ...


@runtime_checkable
class PositionManagerProvider(Protocol):
    """Protocol for position management."""
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current positions."""
        ...

    async def execute_trading_decision(self, instrument: str, decision: str, confidence: float, analysis_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a trading decision."""
        ...

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        ...


@runtime_checkable
class Agent(Protocol):
    async def analyze(self, context: dict[str, Any]) -> AnalysisResult:
        ...


@runtime_checkable
class Orchestrator(Protocol):
    async def run_cycle(self, context: dict[str, Any]) -> AnalysisResult:
        ...

