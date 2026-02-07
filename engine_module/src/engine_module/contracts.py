"""Orchestrator and agent contracts for options trading."""
from dataclasses import dataclass
from datetime import datetime
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
    decision: str  # Analysis decision: BUY/SELL/HOLD or strategy name
    confidence: float  # 0.0 to 1.0 confidence level
    details: dict[str, Any] | None = None  # Structured analysis data + natural language reasoning
    input_data: dict[str, Any] | None = None  # Data used for analysis (for debugging)
    options_strategy: OptionsStrategyDetails | None = None  # For options strategies only
    agent: str | None = None  # Agent identifier (populated by orchestrator)
    excluded: bool = False  # Whether this agent should be excluded from decision making
    exclusion_reason: str | None = None  # Why the agent was excluded

    def __post_init__(self):
        """Validate AnalysisResult after creation."""
        # Ensure confidence is within valid range
        if not isinstance(self.confidence, (int, float)) or self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

        # Ensure decision is not empty
        if not self.decision or not isinstance(self.decision, str):
            raise ValueError(f"Decision must be a non-empty string, got {self.decision}")

        # Ensure details is a dict if provided
        if self.details is not None and not isinstance(self.details, dict):
            raise ValueError(f"Details must be a dict or None, got {type(self.details)}")

        # Validate recommended details structure
        if self.details:
            self._validate_details_structure()

    def _validate_details_structure(self):
        """Ensure details follows recommended structure."""
        recommended_keys = [
            'reasoning',      # Natural language explanation
            'indicators',     # Technical indicators used
            'analysis',       # Domain-specific analysis results
            'signals',        # Structured signal specs (for signal creation agents only)
        ]

        # Warn if no reasoning provided
        if 'reasoning' not in self.details:
            import warnings
            warnings.warn(f"Agent {self.agent or 'Unknown'} should include 'reasoning' in details for explainability")

        # Ensure no trade parameters are set by analysis agents
        trade_params = ['entry_price', 'stop_loss', 'take_profit', 'position_size']
        for param in trade_params:
            if param in self.details:
                import warnings
                warnings.warn(f"Agent {self.agent or 'Unknown'} should not set '{param}' - that's for signal creation layer")


def create_valid_analysis_result(
    decision: str,
    confidence: float,
    details: dict[str, Any] | None = None,
    input_data: dict[str, Any] | None = None,
    options_strategy: OptionsStrategyDetails | None = None,
    agent: str | None = None,
    min_confidence: float = 0.0
) -> AnalysisResult:
    """Create a validated AnalysisResult, ensuring no fake data.

    Args:
        decision: Trading decision
        confidence: Confidence level (0.0 to 1.0)
        details: Additional analysis details
        input_data: Data used for analysis
        options_strategy: Options strategy details if applicable
        agent: Agent identifier
        min_confidence: Minimum confidence threshold (default 0.0)

    Returns:
        Validated AnalysisResult

    Raises:
        ValueError: If confidence is below minimum or data is invalid
    """
    # Validate minimum confidence to prevent fake data
    if confidence < min_confidence:
        raise ValueError(f"Confidence {confidence} below minimum threshold {min_confidence}")

    # For HOLD decisions, confidence should be low
    if decision.upper() == "HOLD" and confidence > 0.8:
        raise ValueError(f"HOLD decision should not have high confidence {confidence}")

    # For strong decisions, confidence should be reasonable
    if decision.upper() not in ["HOLD", "UNKNOWN"] and confidence < 0.1:
        raise ValueError(f"Strong decision {decision} should have confidence >= 0.1, got {confidence}")

    return AnalysisResult(
        decision=decision,
        confidence=confidence,
        details=details,
        input_data=input_data,
        options_strategy=options_strategy,
        agent=agent
    )


@dataclass
class TechnicalIndicators:
    """Container for calculated technical indicators."""
    # Use field names that match market_data constants for consistency
    rsi_14: float | None = None
    rsi_9: float | None = None
    sma_10: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    ema_10: float | None = None
    ema_12: float | None = None
    ema_20: float | None = None
    ema_26: float | None = None
    ema_50: float | None = None
    wma_20: float | None = None
    macd_value: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    adx_14: float | None = None
    di_plus: float | None = None
    di_minus: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None
    bb_percent_b: float | None = None
    atr_14: float | None = None
    atr_20: float | None = None
    obv: float | None = None
    volume_sma_20: float | None = None
    volume_rsi_14: float | None = None
    cmf_20: float | None = None
    cci_20: float | None = None
    mfi_14: float | None = None
    roc_12: float | None = None
    momentum_10: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None
    williams_r: float | None = None
    pivot_point: float | None = None
    pivot_r1: float | None = None
    pivot_r2: float | None = None
    pivot_s1: float | None = None
    pivot_s2: float | None = None
    high_20: float | None = None
    low_20: float | None = None
    range_20: float | None = None
    trend_direction: str | None = None
    trend_strength: float | None = None
    signal_strength: float | None = None
    volatility_level: str | None = None
    rsi_status: str | None = None
    current_price: float | None = None
    price_change_pct: float | None = None
    timestamp: str | None = None
    instrument: str | None = None
    timeframe: str | None = None

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


@dataclass
class TradingDecision:
    """Complete trading decision from orchestrator."""
    instrument: str
    decision: str  # BUY, SELL, HOLD, or strategy name
    confidence: float
    timestamp: datetime
    reasoning: str
    agent_results: List[AnalysisResult]
    technical_indicators: Dict[str, Any]
    execution_result: Optional[Dict[str, Any]] = None
    mode: str = "LIVE"  # LIVE, PAPER, BACKTEST
    run_id: Optional[str] = None


@runtime_checkable
class Orchestrator(Protocol):
    async def run_cycle(self, context: dict[str, Any]) -> AnalysisResult:
        ...

