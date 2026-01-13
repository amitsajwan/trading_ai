"""Structured Reports for Agent Communication.

This module provides a standardized format for agent analysis and reasoning,
inspired by TradingAgents framework's structured communication approach.

Structured reports enable:
- Clear, hierarchical information presentation
- Evidence-based reasoning
- Standardized action recommendations
- Easy aggregation and comparison
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of structured reports."""
    ANALYSIS = "analysis"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    UPDATE = "update"
    DEBATE_ARGUMENT = "debate_argument"


class ReportPriority(Enum):
    """Priority levels for reports."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceType(Enum):
    """Types of evidence in reports."""
    TECHNICAL_INDICATOR = "technical_indicator"
    MARKET_DATA = "market_data"
    HISTORICAL_PATTERN = "historical_pattern"
    FUNDAMENTAL_DATA = "fundamental_data"
    SENTIMENT_DATA = "sentiment_data"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    EXPERT_OPINION = "expert_opinion"


@dataclass
class ReportEvidence:
    """Evidence supporting a report claim.
    
    Attributes:
        type: Type of evidence (technical, market data, etc.)
        description: Description of the evidence
        value: The actual evidence value
        source: Source of the evidence (indicator name, data source, etc.)
        confidence: Confidence in this evidence (0.0 to 1.0)
        timestamp: When this evidence was collected
    """
    type: EvidenceType
    description: str
    value: Union[float, str, Dict[str, Any]]
    source: str
    confidence: float = 0.5
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        # Validate confidence
        if not 0.0 <= self.confidence <= 1.0:
            logger.warning(f"Invalid confidence {self.confidence}, clamping to [0.0, 1.0]")
            self.confidence = max(0.0, min(1.0, self.confidence))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "description": self.description,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class ReportSection:
    """A section within a structured report.
    
    Attributes:
        title: Section title
        content: Main content/text of the section
        evidence: List of evidence supporting this section
        subsections: Nested subsections
        confidence: Confidence in this section's claims (0.0 to 1.0)
    """
    title: str
    content: str
    evidence: List[ReportEvidence] = field(default_factory=list)
    subsections: List['ReportSection'] = field(default_factory=list)
    confidence: float = 0.5
    
    def __post_init__(self):
        """Validate confidence."""
        if not 0.0 <= self.confidence <= 1.0:
            logger.warning(f"Invalid confidence {self.confidence}, clamping to [0.0, 1.0]")
            self.confidence = max(0.0, min(1.0, self.confidence))
    
    def add_evidence(self, evidence: ReportEvidence):
        """Add evidence to this section."""
        self.evidence.append(evidence)
    
    def add_subsection(self, subsection: 'ReportSection'):
        """Add a subsection."""
        self.subsections.append(subsection)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "content": self.content,
            "evidence": [e.to_dict() for e in self.evidence],
            "subsections": [s.to_dict() for s in self.subsections],
            "confidence": self.confidence
        }


@dataclass
class ReportAction:
    """Action recommendation from a report.
    
    Attributes:
        action: Recommended action (BUY, SELL, HOLD, etc.)
        target: Target instrument or strategy
        quantity: Recommended quantity (if applicable)
        reasoning: Reasoning for this action
        urgency: Urgency level (immediate, scheduled, optional)
        confidence: Confidence in this action (0.0 to 1.0)
        risk_assessment: Risk assessment for this action
        alternatives: Alternative actions to consider
    """
    action: str
    target: str
    quantity: Optional[float] = None
    reasoning: str = ""
    urgency: str = "scheduled"  # immediate, scheduled, optional
    confidence: float = 0.5
    risk_assessment: Optional[Dict[str, Any]] = None
    alternatives: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate confidence."""
        if not 0.0 <= self.confidence <= 1.0:
            logger.warning(f"Invalid confidence {self.confidence}, clamping to [0.0, 1.0]")
            self.confidence = max(0.0, min(1.0, self.confidence))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action": self.action,
            "target": self.target,
            "quantity": self.quantity,
            "reasoning": self.reasoning,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "risk_assessment": self.risk_assessment,
            "alternatives": self.alternatives
        }


@dataclass
class StructuredReport:
    """A structured report from an agent.
    
    Attributes:
        agent_name: Name of the agent generating this report
        report_type: Type of report (analysis, recommendation, etc.)
        priority: Priority level
        title: Report title
        summary: Executive summary
        sections: Main sections of the report
        actions: Recommended actions
        confidence: Overall confidence in the report (0.0 to 1.0)
        timestamp: When the report was generated
        metadata: Additional metadata
    """
    agent_name: str
    report_type: ReportType
    priority: ReportPriority
    title: str
    summary: str
    sections: List[ReportSection] = field(default_factory=list)
    actions: List[ReportAction] = field(default_factory=list)
    confidence: float = 0.5
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        # Validate confidence
        if not 0.0 <= self.confidence <= 1.0:
            logger.warning(f"Invalid confidence {self.confidence}, clamping to [0.0, 1.0]")
            self.confidence = max(0.0, min(1.0, self.confidence))
    
    def add_section(self, section: ReportSection):
        """Add a section to the report."""
        self.sections.append(section)
    
    def add_action(self, action: ReportAction):
        """Add an action recommendation."""
        self.actions.append(action)
    
    def get_overall_confidence(self) -> float:
        """Calculate overall confidence from sections and actions.
        
        Returns weighted average of section confidences and action confidences.
        """
        if not self.sections and not self.actions:
            return self.confidence
        
        confidences = []
        
        # Collect confidences from sections
        for section in self.sections:
            confidences.append(section.confidence)
            # Include subsection confidences
            for subsection in section.subsections:
                confidences.append(subsection.confidence)
        
        # Collect confidences from actions
        for action in self.actions:
            confidences.append(action.confidence)
        
        if not confidences:
            return self.confidence
        
        # Calculate weighted average (sections and actions equally weighted)
        overall = sum(confidences) / len(confidences)
        
        # Combine with base confidence
        return (self.confidence + overall) / 2.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "report_type": self.report_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
            "actions": [a.to_dict() for a in self.actions],
            "confidence": self.get_overall_confidence(),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata
        }
    
    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = []
        lines.append(f"# {self.title}")
        lines.append(f"**Agent:** {self.agent_name} | **Type:** {self.report_type.value} | **Priority:** {self.priority.value}")
        lines.append(f"**Generated:** {self.timestamp.isoformat() if self.timestamp else 'N/A'}")
        lines.append("")
        lines.append(f"## Summary")
        lines.append(self.summary)
        lines.append("")
        
        for section in self.sections:
            lines.append(f"## {section.title}")
            lines.append(section.content)
            
            if section.evidence:
                lines.append("### Evidence")
                for evidence in section.evidence:
                    lines.append(f"- **{evidence.source}**: {evidence.description}")
                    lines.append(f"  - Value: {evidence.value}")
                    lines.append(f"  - Confidence: {evidence.confidence:.2%}")
            
            for subsection in section.subsections:
                lines.append(f"### {subsection.title}")
                lines.append(subsection.content)
        
        if self.actions:
            lines.append("## Recommended Actions")
            for action in self.actions:
                lines.append(f"### {action.action}: {action.target}")
                lines.append(f"**Confidence:** {action.confidence:.2%}")
                lines.append(f"**Reasoning:** {action.reasoning}")
                if action.risk_assessment:
                    lines.append(f"**Risk:** {action.risk_assessment}")
        
        return "\n".join(lines)


class ReportBuilder:
    """Builder class for constructing structured reports."""
    
    def __init__(self, agent_name: str):
        """Initialize report builder.
        
        Args:
            agent_name: Name of the agent creating the report
        """
        self.agent_name = agent_name
        self.report_type = ReportType.ANALYSIS
        self.priority = ReportPriority.MEDIUM
        self.title = ""
        self.summary = ""
        self.sections: List[ReportSection] = []
        self.actions: List[ReportAction] = []
        self.confidence = 0.5
        self.metadata: Dict[str, Any] = {}
    
    def set_type(self, report_type: ReportType) -> 'ReportBuilder':
        """Set report type."""
        self.report_type = report_type
        return self
    
    def set_priority(self, priority: ReportPriority) -> 'ReportBuilder':
        """Set report priority."""
        self.priority = priority
        return self
    
    def set_title(self, title: str) -> 'ReportBuilder':
        """Set report title."""
        self.title = title
        return self
    
    def set_summary(self, summary: str) -> 'ReportBuilder':
        """Set report summary."""
        self.summary = summary
        return self
    
    def set_confidence(self, confidence: float) -> 'ReportBuilder':
        """Set base confidence."""
        self.confidence = confidence
        return self
    
    def add_section(
        self,
        title: str,
        content: str,
        confidence: float = 0.5,
        evidence: Optional[List[ReportEvidence]] = None
    ) -> 'ReportBuilder':
        """Add a section to the report."""
        section = ReportSection(
            title=title,
            content=content,
            confidence=confidence
        )
        if evidence:
            section.evidence = evidence
        self.sections.append(section)
        return self
    
    def add_evidence_to_last_section(self, evidence: ReportEvidence) -> 'ReportBuilder':
        """Add evidence to the last added section."""
        if self.sections:
            self.sections[-1].add_evidence(evidence)
        return self
    
    def add_action(
        self,
        action: str,
        target: str,
        reasoning: str = "",
        confidence: float = 0.5,
        **kwargs
    ) -> 'ReportBuilder':
        """Add an action recommendation."""
        action_obj = ReportAction(
            action=action,
            target=target,
            reasoning=reasoning,
            confidence=confidence,
            **kwargs
        )
        self.actions.append(action_obj)
        return self
    
    def add_metadata(self, key: str, value: Any) -> 'ReportBuilder':
        """Add metadata."""
        self.metadata[key] = value
        return self
    
    def build(self) -> StructuredReport:
        """Build the structured report."""
        if not self.title:
            self.title = f"{self.report_type.value.capitalize()} Report"
        
        return StructuredReport(
            agent_name=self.agent_name,
            report_type=self.report_type,
            priority=self.priority,
            title=self.title,
            summary=self.summary,
            sections=self.sections.copy(),
            actions=self.actions.copy(),
            confidence=self.confidence,
            metadata=self.metadata.copy()
        )
