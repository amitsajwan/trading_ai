"""AgentState model for shared context between all agents."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Annotated
from datetime import datetime
from enum import Enum
from operator import add


class SignalType(str, Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    ADJUST_POSITION = "ADJUST_POSITION"


class TrendSignal(str, Enum):
    """Market trend signal types."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class OHLCData(BaseModel):
    """OHLC candle data structure."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class NewsItem(BaseModel):
    """News item structure."""
    title: str
    content: Optional[str] = None
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    source: str
    timestamp: datetime


class AgentState(BaseModel):
    """
    Shared state passed between all agents.
    Updated by each agent as it processes.
    """
    
    # Market context
    current_price: float = 0.0
    current_time: datetime = Field(default_factory=datetime.now)
    ohlc_1min: List[Dict[str, Any]] = Field(default_factory=list)  # Last 60 1-min candles
    ohlc_5min: List[Dict[str, Any]] = Field(default_factory=list)  # Last 100 5-min candles
    ohlc_15min: List[Dict[str, Any]] = Field(default_factory=list)  # Last 100 15-min candles
    ohlc_hourly: List[Dict[str, Any]] = Field(default_factory=list)  # Last 60 hourly candles
    ohlc_daily: List[Dict[str, Any]] = Field(default_factory=list)  # Last 60 daily candles
    
    # Order flow data
    best_bid_price: Optional[float] = None
    best_ask_price: Optional[float] = None
    best_bid_quantity: int = 0
    best_ask_quantity: int = 0
    bid_ask_spread: Optional[float] = None
    buy_quantity: int = 0
    sell_quantity: int = 0
    buy_sell_imbalance: float = Field(default=0.5, ge=0.0, le=1.0)  # 0.5 = balanced
    
    # Volume analysis
    volume_profile: Dict[str, Any] = Field(default_factory=dict)
    volume_trends: Dict[str, Any] = Field(default_factory=dict)
    vwap: Optional[float] = None
    obv: Optional[float] = None
    
    # Order flow signals
    order_flow_signals: Dict[str, Any] = Field(default_factory=dict)
    
    # News & sentiment
    latest_news: List[Dict[str, Any]] = Field(default_factory=list)  # News items with sentiment
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)  # Overall sentiment -1 to +1
    
    # Macro context
    rbi_rate: Optional[float] = None  # Current repo rate
    inflation_rate: Optional[float] = None  # Latest CPI
    npa_ratio: Optional[float] = None  # Banking sector NPA
    
    # Agent outputs (accumulated)
    fundamental_analysis: Dict[str, Any] = Field(default_factory=dict)
    technical_analysis: Dict[str, Any] = Field(default_factory=dict)
    sentiment_analysis: Dict[str, Any] = Field(default_factory=dict)
    macro_analysis: Dict[str, Any] = Field(default_factory=dict)
    
    # Bull vs Bear debate
    bull_thesis: str = ""
    bear_thesis: str = ""
    bull_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    bear_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Risk management recommendations
    aggressive_risk_recommendation: Dict[str, Any] = Field(default_factory=dict)
    conservative_risk_recommendation: Dict[str, Any] = Field(default_factory=dict)
    neutral_risk_recommendation: Dict[str, Any] = Field(default_factory=dict)
    
    # Portfolio manager decision
    final_signal: SignalType = SignalType.HOLD
    trend_signal: TrendSignal = TrendSignal.NEUTRAL  # Overall market trend: BULLISH, BEARISH, or NEUTRAL
    position_size: int = 0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    # Execution details
    order_id: str = ""
    filled_price: float = 0.0
    filled_quantity: int = 0
    execution_timestamp: Optional[datetime] = None
    
    # Trade metadata
    trade_id: str = ""
    agent_explanations: Annotated[List[str], add] = Field(default_factory=list)  # Reasoning from each agent (reducer for concurrent updates)
    decision_audit_trail: Dict[str, Any] = Field(default_factory=dict)  # Full decision history
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return self.model_dump(mode='json')
    
    def update_agent_output(self, agent_name: str, output: Dict[str, Any]) -> None:
        """Update state with agent output."""
        if agent_name == "fundamental":
            self.fundamental_analysis = output
        elif agent_name == "technical":
            self.technical_analysis = output
        elif agent_name == "sentiment":
            self.sentiment_analysis = output
        elif agent_name == "macro":
            self.macro_analysis = output
        elif agent_name == "bull":
            self.bull_thesis = output.get("thesis", "")
            self.bull_confidence = output.get("conviction_score", 0.5)
        elif agent_name == "bear":
            self.bear_thesis = output.get("thesis", "")
            self.bear_confidence = output.get("conviction_score", 0.5)
        elif agent_name == "portfolio_manager":
            # Portfolio manager output is stored separately and includes scores
            # Store it in a dict for later retrieval
            if not hasattr(self, '_portfolio_manager_output'):
                self._portfolio_manager_output = {}
            self._portfolio_manager_output.update(output)
        elif agent_name == "aggressive_risk":
            self.aggressive_risk_recommendation = output
        elif agent_name == "conservative_risk":
            self.conservative_risk_recommendation = output
        elif agent_name == "neutral_risk":
            self.neutral_risk_recommendation = output
    
    def add_explanation(self, agent_name: str, explanation: str) -> None:
        """Add agent explanation to audit trail."""
        self.agent_explanations.append(f"[{agent_name}]: {explanation}")

