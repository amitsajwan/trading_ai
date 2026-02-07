"""Enhanced Agent Framework with comprehensive reasoning and inter-agent communication.

This framework provides:
- Clear documentation of agent capabilities
- Natural language reasoning
- Inter-agent communication
- Conditional signal generation
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Protocol
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context passed between agents for inter-agent communication."""
    agent_outputs: Dict[str, Any] = field(default_factory=dict)
    market_data: Dict[str, Any] = field(default_factory=dict)
    technical_data: Dict[str, Any] = field(default_factory=dict)
    macro_data: Dict[str, Any] = field(default_factory=dict)
    news_data: Dict[str, Any] = field(default_factory=dict)
    position_data: Dict[str, Any] = field(default_factory=dict)
    global_signals: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ConditionalSignal:
    """Represents a conditional trading signal that can be monitored."""
    signal_id: str
    instrument: str
    condition_type: str  # "breakout", "rsi_cross", "volume_spike", "price_level", etc.
    condition_params: Dict[str, Any]  # Parameters for the condition
    action: str  # "BUY", "SELL"
    confidence: float
    reasoning: str
    created_by_agent: str
    valid_until: Optional[str] = None
    priority: int = 1  # 1=low, 5=high


@dataclass
class AgentAnalysis:
    """Comprehensive analysis result from an agent."""
    agent_name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Agent Documentation
    inputs: List[str] = field(default_factory=list)  # What data the agent uses
    objectives: List[str] = field(default_factory=list)  # What the agent aims to achieve
    methodology: str = ""  # How the agent works

    # Analysis Results
    immediate_decision: Optional[str] = None  # BUY/SELL/HOLD (for immediate action)
    confidence: float = 0.0

    # Conditional Signals
    conditional_signals: List[ConditionalSignal] = field(default_factory=list)

    # Natural Language Reasoning
    reasoning: str = ""
    key_insights: List[str] = field(default_factory=list)
    risks_identified: List[str] = field(default_factory=list)

    # Inter-agent Communication
    outputs_for_other_agents: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    processing_time_seconds: float = 0.0
    data_quality_score: float = 1.0  # 0-1 scale


class EnhancedAgent(ABC):
    """Enhanced agent base class with comprehensive reasoning and communication."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @property
    @abstractmethod
    def agent_inputs(self) -> List[str]:
        """Document what inputs this agent requires/consumes."""
        pass

    @property
    @abstractmethod
    def agent_objectives(self) -> List[str]:
        """Document what this agent aims to achieve."""
        pass

    @property
    @abstractmethod
    def agent_methodology(self) -> str:
        """Document how this agent works."""
        pass

    @abstractmethod
    async def analyze(self, context: AgentContext) -> AgentAnalysis:
        """Perform analysis and return comprehensive results."""
        pass

    def create_conditional_signal(
        self,
        instrument: str,
        condition_type: str,
        condition_params: Dict[str, Any],
        action: str,
        confidence: float,
        reasoning: str,
        priority: int = 1
    ) -> ConditionalSignal:
        """Helper method to create conditional signals."""
        return ConditionalSignal(
            signal_id=f"{self.name}_{instrument}_{condition_type}_{datetime.now().strftime('%H%M%S')}",
            instrument=instrument,
            condition_type=condition_type,
            condition_params=condition_params,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            created_by_agent=self.name,
            priority=priority
        )

    def build_reasoning_text(self, insights: List[str], context: AgentContext) -> str:
        """Build comprehensive natural language reasoning."""
        reasoning_parts = []

        # Agent introduction
        reasoning_parts.append(f"As the {self.name}, I analyze {', '.join(self.agent_inputs)} to {', '.join(self.agent_objectives)}.")

        # Methodology explanation
        reasoning_parts.append(f"My analysis methodology: {self.agent_methodology}")

        # Key insights
        if insights:
            reasoning_parts.append("Key insights from my analysis:")
            for insight in insights:
                reasoning_parts.append(f"- {insight}")

        # Data quality assessment
        data_quality = self._assess_data_quality(context)
        if data_quality < 0.8:
            reasoning_parts.append(f"⚠️ Data quality concerns: {data_quality:.1%} confidence in input data.")

        return " ".join(reasoning_parts)

    def _assess_data_quality(self, context: AgentContext) -> float:
        """Assess quality of input data."""
        quality_score = 1.0

        # Check if key data is available
        if not context.market_data.get('current_price'):
            quality_score *= 0.7

        if not context.technical_data.get('technical_indicators'):
            quality_score *= 0.8

        if not context.macro_data.get('macro_data_available', False):
            quality_score *= 0.9

        return quality_score


class AgentCommunicationBus:
    """Handles inter-agent communication and signal aggregation."""

    def __init__(self):
        self.agent_outputs: Dict[str, Any] = {}
        self.conditional_signals: List[ConditionalSignal] = []
        self.global_insights: List[str] = []

    def register_agent_output(self, agent_name: str, output: Dict[str, Any]):
        """Register output from an agent for other agents to use."""
        self.agent_outputs[agent_name] = output

    def get_agent_output(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get output from a specific agent."""
        return self.agent_outputs.get(agent_name)

    def add_conditional_signal(self, signal: ConditionalSignal):
        """Add a conditional signal to the global pool."""
        self.conditional_signals.append(signal)

    def get_all_conditional_signals(self) -> List[ConditionalSignal]:
        """Get all conditional signals."""
        return self.conditional_signals

    def add_global_insight(self, insight: str):
        """Add an insight that all agents should consider."""
        self.global_insights.append(insight)

    def get_global_insights(self) -> List[str]:
        """Get all global insights."""
        return self.global_insights