"""Orchestrator and agent contracts."""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Any, Dict, List, Optional


@dataclass
class AnalysisResult:
    decision: str
    confidence: float
    details: dict[str, Any] | None = None


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

