"""Debate Protocol for Agent Argumentation.

This module provides a formal debate framework for agent interactions,
enabling structured argumentation between agents (e.g., Bull vs Bear).

The debate protocol enables:
- Structured argument presentation
- Counter-argument support
- Evidence-based reasoning
- Formal debate rounds
- Final synthesis
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
from .structured_reports import StructuredReport, ReportEvidence, EvidenceType

logger = logging.getLogger(__name__)


class ArgumentType(Enum):
    """Types of arguments in debates."""
    INITIAL = "initial"  # Opening argument
    REBUTTAL = "rebuttal"  # Counter-argument
    REBUTTAL_TO_REBUTTAL = "rebuttal_to_rebuttal"  # Counter to counter
    CLOSING = "closing"  # Final statement


class ArgumentStrength(Enum):
    """Strength levels for arguments."""
    VERY_STRONG = "very_strong"  # > 0.8 confidence
    STRONG = "strong"  # 0.6 - 0.8 confidence
    MODERATE = "moderate"  # 0.4 - 0.6 confidence
    WEAK = "weak"  # < 0.4 confidence


@dataclass
class DebateArgument:
    """An argument in a debate.
    
    Attributes:
        participant_name: Name of the participant making the argument
        argument_type: Type of argument (initial, rebuttal, etc.)
        claim: The main claim being made
        reasoning: Reasoning supporting the claim
        evidence: List of evidence supporting the argument
        confidence: Confidence in this argument (0.0 to 1.0)
        counter_argument_to: Optional ID of argument this counters
        timestamp: When the argument was made
    """
    participant_name: str
    argument_type: ArgumentType
    claim: str
    reasoning: str
    evidence: List[ReportEvidence] = field(default_factory=list)
    confidence: float = 0.5
    counter_argument_to: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamp and validate."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        if not 0.0 <= self.confidence <= 1.0:
            logger.warning(f"Invalid confidence {self.confidence}, clamping to [0.0, 1.0]")
            self.confidence = max(0.0, min(1.0, self.confidence))
    
    def get_strength(self) -> ArgumentStrength:
        """Get argument strength based on confidence."""
        if self.confidence >= 0.8:
            return ArgumentStrength.VERY_STRONG
        elif self.confidence >= 0.6:
            return ArgumentStrength.STRONG
        elif self.confidence >= 0.4:
            return ArgumentStrength.MODERATE
        else:
            return ArgumentStrength.WEAK
    
    def add_evidence(self, evidence: ReportEvidence):
        """Add evidence to this argument."""
        self.evidence.append(evidence)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "participant_name": self.participant_name,
            "argument_type": self.argument_type.value,
            "claim": self.claim,
            "reasoning": self.reasoning,
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence,
            "counter_argument_to": self.counter_argument_to,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "strength": self.get_strength().value
        }


@dataclass
class DebateParticipant:
    """A participant in a debate.
    
    Attributes:
        name: Participant name
        position: Their position (e.g., "bull", "bear", "neutral")
        agent: Optional reference to the agent object
        arguments: Arguments made by this participant
    """
    name: str
    position: str
    agent: Optional[Any] = None
    arguments: List[DebateArgument] = field(default_factory=list)
    
    def add_argument(self, argument: DebateArgument):
        """Add an argument made by this participant."""
        self.arguments.append(argument)
    
    def get_argument_count(self) -> int:
        """Get total number of arguments made."""
        return len(self.arguments)
    
    def get_average_confidence(self) -> float:
        """Get average confidence of all arguments."""
        if not self.arguments:
            return 0.5
        
        return sum(arg.confidence for arg in self.arguments) / len(self.arguments)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "position": self.position,
            "argument_count": self.get_argument_count(),
            "average_confidence": self.get_average_confidence(),
            "arguments": [arg.to_dict() for arg in self.arguments]
        }


@dataclass
class DebateRound:
    """A round in a debate.
    
    Attributes:
        round_number: Round number (1, 2, 3, etc.)
        arguments: Arguments made in this round
        timestamp: When the round started
    """
    round_number: int
    arguments: List[DebateArgument] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def add_argument(self, argument: DebateArgument):
        """Add an argument to this round."""
        self.arguments.append(argument)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "round_number": self.round_number,
            "arguments": [arg.to_dict() for arg in self.arguments],
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class DebateResult:
    """Result of a debate.
    
    Attributes:
        winner: Name of the winning participant (or None if no clear winner)
        winner_confidence: Confidence in the winner
        summary: Summary of the debate
        key_points: Key points from the debate
        consensus: Consensus reached (if any)
        recommended_action: Recommended action based on debate
        participants: All participants
        rounds: All debate rounds
        timestamp: When the debate concluded
    """
    winner: Optional[str]
    winner_confidence: float
    summary: str
    key_points: List[str] = field(default_factory=list)
    consensus: Optional[str] = None
    recommended_action: Optional[str] = None
    participants: List[DebateParticipant] = field(default_factory=list)
    rounds: List[DebateRound] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "winner": self.winner,
            "winner_confidence": self.winner_confidence,
            "summary": self.summary,
            "key_points": self.key_points,
            "consensus": self.consensus,
            "recommended_action": self.recommended_action,
            "participants": [p.to_dict() for p in self.participants],
            "rounds": [r.to_dict() for r in self.rounds],
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class DebateProtocol:
    """Protocol for conducting formal debates between agents.
    
    This class manages the debate process:
    1. Registration of participants
    2. Structured argument presentation
    3. Rebuttal management
    4. Final synthesis
    """
    
    def __init__(self, max_rounds: int = 3, min_confidence_threshold: float = 0.6):
        """Initialize debate protocol.
        
        Args:
            max_rounds: Maximum number of debate rounds (default: 3)
            min_confidence_threshold: Minimum confidence for clear winner (default: 0.6)
        """
        self.max_rounds = max_rounds
        self.min_confidence_threshold = min_confidence_threshold
        self.participants: Dict[str, DebateParticipant] = {}
        self.rounds: List[DebateRound] = []
        self.argument_counter = 0
    
    def register_participant(
        self,
        name: str,
        position: str,
        agent: Optional[Any] = None
    ) -> DebateParticipant:
        """Register a participant in the debate.
        
        Args:
            name: Participant name
            position: Their position (e.g., "bull", "bear")
            agent: Optional reference to the agent object
        
        Returns:
            DebateParticipant object
        """
        participant = DebateParticipant(name=name, position=position, agent=agent)
        self.participants[name] = participant
        logger.info(f"Registered debate participant: {name} ({position})")
        return participant
    
    def start_round(self, round_number: int) -> DebateRound:
        """Start a new debate round.
        
        Args:
            round_number: Round number
        
        Returns:
            DebateRound object
        """
        if round_number > self.max_rounds:
            raise ValueError(f"Maximum rounds ({self.max_rounds}) exceeded")
        
        round_obj = DebateRound(round_number=round_number)
        self.rounds.append(round_obj)
        logger.info(f"Started debate round {round_number}")
        return round_obj
    
    def submit_argument(
        self,
        participant_name: str,
        claim: str,
        reasoning: str,
        argument_type: ArgumentType = ArgumentType.INITIAL,
        confidence: float = 0.5,
        evidence: Optional[List[ReportEvidence]] = None,
        counter_argument_to: Optional[str] = None,
        round_number: Optional[int] = None
    ) -> DebateArgument:
        """Submit an argument to the debate.
        
        Args:
            participant_name: Name of the participant
            claim: The main claim
            reasoning: Reasoning supporting the claim
            argument_type: Type of argument (initial, rebuttal, etc.)
            confidence: Confidence in the argument (0.0 to 1.0)
            evidence: Optional list of evidence
            counter_argument_to: Optional ID of argument this counters
            round_number: Round number (uses current round if None)
        
        Returns:
            DebateArgument object
        """
        if participant_name not in self.participants:
            raise ValueError(f"Participant {participant_name} not registered")
        
        # Determine round number
        if round_number is None:
            round_number = len(self.rounds) if self.rounds else 1
            if not self.rounds or self.rounds[-1].round_number != round_number:
                self.start_round(round_number)
        
        # Ensure round exists
        current_round = None
        for r in self.rounds:
            if r.round_number == round_number:
                current_round = r
                break
        
        if current_round is None:
            current_round = self.start_round(round_number)
        
        # Create argument
        argument = DebateArgument(
            participant_name=participant_name,
            argument_type=argument_type,
            claim=claim,
            reasoning=reasoning,
            confidence=confidence,
            counter_argument_to=counter_argument_to
        )
        
        if evidence:
            argument.evidence = evidence
        
        # Add to participant and round
        self.participants[participant_name].add_argument(argument)
        current_round.add_argument(argument)
        
        self.argument_counter += 1
        logger.debug(f"Argument submitted by {participant_name}: {claim[:50]}...")
        
        return argument
    
    def conduct_debate(
        self,
        initial_arguments: Optional[Dict[str, Dict[str, Any]]] = None,
        llm_synthesizer: Optional[Any] = None
    ) -> DebateResult:
        """Conduct the full debate and synthesize result.
        
        Args:
            initial_arguments: Optional dict mapping participant names to initial argument data
            llm_synthesizer: Optional LLM client for synthesis
        
        Returns:
            DebateResult object
        """
        # Start round 1
        self.start_round(1)
        
        # Submit initial arguments if provided
        if initial_arguments:
            for participant_name, arg_data in initial_arguments.items():
                self.submit_argument(
                    participant_name=participant_name,
                    claim=arg_data.get("claim", ""),
                    reasoning=arg_data.get("reasoning", ""),
                    argument_type=ArgumentType.INITIAL,
                    confidence=arg_data.get("confidence", 0.5),
                    evidence=arg_data.get("evidence"),
                    round_number=1
                )
        
        # Conduct additional rounds (rebuttals)
        for round_num in range(2, self.max_rounds + 1):
            if self._should_continue_debate():
                self.start_round(round_num)
                # In a real implementation, participants would submit rebuttals here
                # For now, we'll just create the structure
        
        # Synthesize result
        result = self._synthesize_debate(llm_synthesizer)
        
        return result
    
    def _should_continue_debate(self) -> bool:
        """Determine if debate should continue.
        
        Returns:
            True if debate should continue, False otherwise
        """
        if not self.participants:
            return False
        
        # Check if we have arguments from all participants
        participant_confidences = [
            p.get_average_confidence() for p in self.participants.values()
        ]
        
        # If confidence gap is large, no need for more rounds
        if len(participant_confidences) >= 2:
            max_conf = max(participant_confidences)
            min_conf = min(participant_confidences)
            if (max_conf - min_conf) > 0.3:  # Clear winner
                return False
        
        return True
    
    def _synthesize_debate(self, llm_synthesizer: Optional[Any] = None) -> DebateResult:
        """Synthesize debate results.
        
        Args:
            llm_synthesizer: Optional LLM client for synthesis
        
        Returns:
            DebateResult object
        """
        if not self.participants:
            return DebateResult(
                winner=None,
                winner_confidence=0.0,
                summary="No participants in debate"
            )
        
        # Calculate winner based on average confidence and argument strength
        participant_scores = {}
        for name, participant in self.participants.items():
            avg_confidence = participant.get_average_confidence()
            argument_count = participant.get_argument_count()
            
            # Score = weighted average of confidence and argument count
            score = (avg_confidence * 0.7) + (min(argument_count / 5.0, 1.0) * 0.3)
            participant_scores[name] = score
        
        # Determine winner
        if len(participant_scores) >= 2:
            sorted_participants = sorted(
                participant_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            winner_name, winner_score = sorted_participants[0]
            runner_up_name, runner_up_score = sorted_participants[1] if len(sorted_participants) > 1 else (None, 0.0)
            
            # Check if clear winner
            confidence_gap = winner_score - (runner_up_score if runner_up_score else 0.0)
            
            if confidence_gap >= 0.15 and winner_score >= self.min_confidence_threshold:
                winner = winner_name
                winner_confidence = winner_score
            else:
                winner = None
                winner_confidence = 0.5
        else:
            winner = list(participant_scores.keys())[0] if participant_scores else None
            winner_confidence = list(participant_scores.values())[0] if participant_scores else 0.0
        
        # Generate summary
        summary_parts = []
        for name, participant in self.participants.items():
            position = participant.position
            avg_conf = participant.get_average_confidence()
            arg_count = participant.get_argument_count()
            summary_parts.append(
                f"{name} ({position}): {arg_count} arguments, "
                f"avg confidence {avg_conf:.2%}"
            )
        
        summary = f"Debate concluded. {' | '.join(summary_parts)}"
        
        # Extract key points
        key_points = []
        for participant in self.participants.values():
            for argument in participant.arguments:
                if argument.confidence >= 0.6:
                    key_points.append(f"{participant.name}: {argument.claim}")
        
        # Determine consensus and recommended action
        consensus = None
        recommended_action = None
        
        if winner:
            winner_participant = self.participants[winner]
            if winner_participant.arguments:
                top_argument = max(winner_participant.arguments, key=lambda a: a.confidence)
                recommended_action = top_argument.claim
                consensus = f"Consensus favors {winner} position"
        
        return DebateResult(
            winner=winner,
            winner_confidence=winner_confidence,
            summary=summary,
            key_points=key_points,
            consensus=consensus,
            recommended_action=recommended_action,
            participants=list(self.participants.values()),
            rounds=self.rounds.copy()
        )
