"""Communication Layer for Agent Interaction.

This module provides structured communication mechanisms for trading agents:
- Structured Reports: Standardized format for agent analysis and reasoning
- Debate Protocol: Formal argumentation framework for agent debates
"""

from .structured_reports import (
    StructuredReport,
    ReportSection,
    ReportEvidence,
    ReportAction,
    ReportBuilder,
    ReportType,
    ReportPriority,
    EvidenceType
)

from .debate_protocol import (
    DebateArgument,
    DebateRound,
    DebateParticipant,
    DebateProtocol,
    DebateResult,
    ArgumentType,
    ArgumentStrength
)

__all__ = [
    # Structured Reports
    "StructuredReport",
    "ReportSection",
    "ReportEvidence",
    "ReportAction",
    "ReportBuilder",
    "ReportType",
    "ReportPriority",
    "EvidenceType",
    # Debate Protocol
    "DebateArgument",
    "DebateRound",
    "DebateParticipant",
    "DebateProtocol",
    "DebateResult",
    "ArgumentType",
    "ArgumentStrength"
]
