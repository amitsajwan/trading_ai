"""Unit tests for Debate Protocol."""

import pytest
from datetime import datetime
from engine_module.communication.debate_protocol import (
    DebateArgument,
    DebateRound,
    DebateParticipant,
    DebateProtocol,
    DebateResult,
    ArgumentType,
    ArgumentStrength
)
from engine_module.communication.structured_reports import ReportEvidence, EvidenceType


class TestDebateArgument:
    """Tests for DebateArgument."""
    
    def test_argument_creation(self):
        """Test DebateArgument creation."""
        argument = DebateArgument(
            participant_name="BullResearcher",
            argument_type=ArgumentType.INITIAL,
            claim="Market is bullish",
            reasoning="RSI oversold, MACD bullish crossover",
            confidence=0.75
        )
        
        assert argument.participant_name == "BullResearcher"
        assert argument.argument_type == ArgumentType.INITIAL
        assert argument.claim == "Market is bullish"
        assert argument.reasoning == "RSI oversold, MACD bullish crossover"
        assert argument.confidence == 0.75
        assert argument.timestamp is not None
    
    def test_argument_get_strength(self):
        """Test argument strength calculation."""
        # Very strong
        arg1 = DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Test",
            reasoning="Test",
            confidence=0.85
        )
        assert arg1.get_strength() == ArgumentStrength.VERY_STRONG
        
        # Strong
        arg2 = DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Test",
            reasoning="Test",
            confidence=0.70
        )
        assert arg2.get_strength() == ArgumentStrength.STRONG
        
        # Moderate
        arg3 = DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Test",
            reasoning="Test",
            confidence=0.50
        )
        assert arg3.get_strength() == ArgumentStrength.MODERATE
        
        # Weak
        arg4 = DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Test",
            reasoning="Test",
            confidence=0.30
        )
        assert arg4.get_strength() == ArgumentStrength.WEAK
    
    def test_argument_add_evidence(self):
        """Test adding evidence to argument."""
        argument = DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Test claim",
            reasoning="Test reasoning"
        )
        
        evidence = ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI oversold",
            value=28.5,
            source="RSI_14"
        )
        
        argument.add_evidence(evidence)
        assert len(argument.evidence) == 1
        assert argument.evidence[0].value == 28.5
    
    def test_argument_to_dict(self):
        """Test argument serialization."""
        argument = DebateArgument(
            participant_name="BullResearcher",
            argument_type=ArgumentType.REBUTTAL,
            claim="Market is bullish",
            reasoning="Strong signals",
            confidence=0.80,
            counter_argument_to="arg_1"
        )
        
        arg_dict = argument.to_dict()
        assert arg_dict['participant_name'] == "BullResearcher"
        assert arg_dict['argument_type'] == "rebuttal"
        assert arg_dict['claim'] == "Market is bullish"
        assert arg_dict['strength'] == "very_strong"
        assert arg_dict['counter_argument_to'] == "arg_1"


class TestDebateParticipant:
    """Tests for DebateParticipant."""
    
    def test_participant_creation(self):
        """Test DebateParticipant creation."""
        participant = DebateParticipant(
            name="BullResearcher",
            position="bull"
        )
        
        assert participant.name == "BullResearcher"
        assert participant.position == "bull"
        assert len(participant.arguments) == 0
    
    def test_participant_add_argument(self):
        """Test adding argument to participant."""
        participant = DebateParticipant(name="Test", position="neutral")
        
        argument = DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Test claim",
            reasoning="Test",
            confidence=0.75
        )
        
        participant.add_argument(argument)
        assert participant.get_argument_count() == 1
        assert participant.arguments[0].claim == "Test claim"
    
    def test_participant_get_average_confidence(self):
        """Test average confidence calculation."""
        participant = DebateParticipant(name="Test", position="neutral")
        
        # Add arguments with different confidences
        participant.add_argument(DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Claim 1",
            reasoning="Test",
            confidence=0.80
        ))
        
        participant.add_argument(DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Claim 2",
            reasoning="Test",
            confidence=0.60
        ))
        
        avg_conf = participant.get_average_confidence()
        assert avg_conf == 0.70  # (0.80 + 0.60) / 2
    
    def test_participant_no_arguments_average_confidence(self):
        """Test average confidence with no arguments."""
        participant = DebateParticipant(name="Test", position="neutral")
        assert participant.get_average_confidence() == 0.5  # Default


class TestDebateRound:
    """Tests for DebateRound."""
    
    def test_round_creation(self):
        """Test DebateRound creation."""
        round_obj = DebateRound(round_number=1)
        
        assert round_obj.round_number == 1
        assert len(round_obj.arguments) == 0
        assert round_obj.timestamp is not None
    
    def test_round_add_argument(self):
        """Test adding argument to round."""
        round_obj = DebateRound(round_number=1)
        
        argument = DebateArgument(
            participant_name="Test",
            argument_type=ArgumentType.INITIAL,
            claim="Test claim",
            reasoning="Test"
        )
        
        round_obj.add_argument(argument)
        assert len(round_obj.arguments) == 1


class TestDebateProtocol:
    """Tests for DebateProtocol."""
    
    def test_protocol_creation(self):
        """Test DebateProtocol creation."""
        protocol = DebateProtocol(max_rounds=3, min_confidence_threshold=0.6)
        
        assert protocol.max_rounds == 3
        assert protocol.min_confidence_threshold == 0.6
        assert len(protocol.participants) == 0
        assert len(protocol.rounds) == 0
    
    def test_register_participant(self):
        """Test participant registration."""
        protocol = DebateProtocol()
        
        participant = protocol.register_participant(
            name="BullResearcher",
            position="bull"
        )
        
        assert "BullResearcher" in protocol.participants
        assert protocol.participants["BullResearcher"].position == "bull"
        assert participant.name == "BullResearcher"
    
    def test_start_round(self):
        """Test starting a debate round."""
        protocol = DebateProtocol()
        
        round_obj = protocol.start_round(1)
        
        assert round_obj.round_number == 1
        assert len(protocol.rounds) == 1
        assert protocol.rounds[0].round_number == 1
    
    def test_start_round_exceeds_max(self):
        """Test starting round that exceeds max rounds."""
        protocol = DebateProtocol(max_rounds=2)
        
        protocol.start_round(1)
        protocol.start_round(2)
        
        with pytest.raises(ValueError, match="Maximum rounds"):
            protocol.start_round(3)
    
    def test_submit_argument(self):
        """Test submitting an argument."""
        protocol = DebateProtocol()
        protocol.register_participant("BullResearcher", "bull")
        protocol.start_round(1)
        
        argument = protocol.submit_argument(
            participant_name="BullResearcher",
            claim="Market is bullish",
            reasoning="Strong signals",
            argument_type=ArgumentType.INITIAL,
            confidence=0.75,
            round_number=1
        )
        
        assert argument.claim == "Market is bullish"
        assert len(protocol.participants["BullResearcher"].arguments) == 1
        assert len(protocol.rounds[0].arguments) == 1
    
    def test_submit_argument_unregistered_participant(self):
        """Test submitting argument for unregistered participant."""
        protocol = DebateProtocol()
        
        with pytest.raises(ValueError, match="not registered"):
            protocol.submit_argument(
                participant_name="Unknown",
                claim="Test",
                reasoning="Test"
            )
    
    def test_submit_argument_auto_round(self):
        """Test auto-creating round when submitting argument."""
        protocol = DebateProtocol()
        protocol.register_participant("Test", "neutral")
        
        # No rounds exist, should auto-create round 1
        argument = protocol.submit_argument(
            participant_name="Test",
            claim="Test claim",
            reasoning="Test"
        )
        
        assert len(protocol.rounds) == 1
        assert protocol.rounds[0].round_number == 1
    
    def test_conduct_debate_simple(self):
        """Test conducting a simple debate."""
        protocol = DebateProtocol(max_rounds=2)
        
        # Register participants
        protocol.register_participant("BullResearcher", "bull")
        protocol.register_participant("BearResearcher", "bear")
        
        # Conduct debate with initial arguments
        initial_arguments = {
            "BullResearcher": {
                "claim": "Market is bullish",
                "reasoning": "RSI oversold, MACD bullish",
                "confidence": 0.75
            },
            "BearResearcher": {
                "claim": "Market is bearish",
                "reasoning": "Resistance level, volume decreasing",
                "confidence": 0.65
            }
        }
        
        result = protocol.conduct_debate(initial_arguments=initial_arguments)
        
        assert result is not None
        assert result.winner in ["BullResearcher", "BearResearcher", None]
        assert len(result.participants) == 2
        assert len(result.rounds) >= 1
        assert result.summary is not None
    
    def test_conduct_debate_winner_determination(self):
        """Test winner determination in debate."""
        protocol = DebateProtocol(max_rounds=1, min_confidence_threshold=0.6)
        
        protocol.register_participant("BullResearcher", "bull")
        protocol.register_participant("BearResearcher", "bear")
        
        # Bull has higher confidence
        initial_arguments = {
            "BullResearcher": {
                "claim": "Strong bullish signals",
                "reasoning": "Multiple indicators bullish",
                "confidence": 0.85  # High confidence
            },
            "BearResearcher": {
                "claim": "Bearish signals",
                "reasoning": "Some bearish indicators",
                "confidence": 0.55  # Lower confidence
            }
        }
        
        result = protocol.conduct_debate(initial_arguments=initial_arguments)
        
        # Bull should win due to higher confidence and clear gap
        assert result.winner == "BullResearcher"
        assert result.winner_confidence >= 0.6
    
    def test_conduct_debate_no_clear_winner(self):
        """Test debate with no clear winner."""
        protocol = DebateProtocol(max_rounds=1, min_confidence_threshold=0.7)
        
        protocol.register_participant("BullResearcher", "bull")
        protocol.register_participant("BearResearcher", "bear")
        
        # Close confidences, no clear winner
        initial_arguments = {
            "BullResearcher": {
                "claim": "Bullish",
                "reasoning": "Test",
                "confidence": 0.55
            },
            "BearResearcher": {
                "claim": "Bearish",
                "reasoning": "Test",
                "confidence": 0.52  # Very close
            }
        }
        
        result = protocol.conduct_debate(initial_arguments=initial_arguments)
        
        # Should have no clear winner due to close scores
        assert result.winner is None or result.winner_confidence < protocol.min_confidence_threshold
    
    def test_debate_result_serialization(self):
        """Test debate result serialization."""
        protocol = DebateProtocol()
        protocol.register_participant("BullResearcher", "bull")
        
        initial_arguments = {
            "BullResearcher": {
                "claim": "Bullish",
                "reasoning": "Test",
                "confidence": 0.75
            }
        }
        
        result = protocol.conduct_debate(initial_arguments=initial_arguments)
        result_dict = result.to_dict()
        
        assert 'winner' in result_dict
        assert 'summary' in result_dict
        assert 'participants' in result_dict
        assert 'rounds' in result_dict
        assert 'timestamp' in result_dict
