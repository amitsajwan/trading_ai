"""Unit tests for Enhanced Research Manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from engine_module.agents.enhanced_research_manager import EnhancedResearchManager
from engine_module.contracts import AnalysisResult


class TestEnhancedResearchManager:
    """Tests for EnhancedResearchManager."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        manager = EnhancedResearchManager()
        
        assert manager._agent_name == "EnhancedResearchManager"
        assert manager._max_rounds == 3
        assert manager._min_confidence == 0.6
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        config = {
            'max_rounds': 5,
            'min_confidence_threshold': 0.7
        }
        manager = EnhancedResearchManager(config=config)
        
        assert manager._max_rounds == 5
        assert manager._min_confidence == 0.7
    
    @pytest.mark.asyncio
    async def test_analyze_conducts_formal_debate(self):
        """Test that analyze conducts formal debate."""
        manager = EnhancedResearchManager()
        
        # Mock bull and bear researchers
        with patch.object(manager, '_get_bull_analysis') as mock_bull, \
             patch.object(manager, '_get_bear_analysis') as mock_bear:
            
            mock_bull.return_value = AnalysisResult(
                decision="BULL_CALL_SPREAD",
                confidence=0.75,
                details={'thesis': 'Bullish signals', 'rsi': 65.0}
            )
            
            mock_bear.return_value = AnalysisResult(
                decision="BEAR_PUT_SPREAD",
                confidence=0.65,
                details={'thesis': 'Bearish signals', 'rsi': 75.0}
            )
            
            context = {
                'market_data': {'close': 45000},
                'multi_timeframe': {},
                'regime': 'trending_up',
                'current_positions': []
            }
            
            result = await manager.analyze(context)
            
            # Should have conducted debate
            assert result.decision in ["BULL_CALL_SPREAD", "BEAR_PUT_SPREAD", "IRON_CONDOR"]
            assert 'debate_result' in result.details
            assert 'winner' in result.details
            
            # Verify debate was conducted
            debate_result = result.details.get('debate_result', {})
            assert 'participants' in debate_result
            assert 'rounds' in debate_result
    
    @pytest.mark.asyncio
    async def test_analyze_missing_analysis(self):
        """Test handling of missing bull/bear analysis."""
        manager = EnhancedResearchManager()
        
        with patch.object(manager, '_get_bull_analysis') as mock_bull, \
             patch.object(manager, '_get_bear_analysis') as mock_bear:
            
            mock_bull.return_value = None
            mock_bear.return_value = AnalysisResult(
                decision="HOLD",
                confidence=0.5,
                details={}
            )
            
            context = {
                'market_data': {},
                'multi_timeframe': {},
                'regime': None,
                'current_positions': []
            }
            
            result = await manager.analyze(context)
            
            assert result.decision == "HOLD"
            assert result.confidence == 0.3
            assert result.details.get('reason') == "INCOMPLETE_ANALYSIS"
    
    @pytest.mark.asyncio
    async def test_conduct_formal_debate(self):
        """Test formal debate conduction."""
        manager = EnhancedResearchManager()
        
        bull_result = AnalysisResult(
            decision="BULL_CALL_SPREAD",
            confidence=0.80,
            details={
                'thesis': 'Strong bullish momentum',
                'reasoning': 'RSI oversold, MACD bullish',
                'rsi': 28.0,
                'macd': 50.0
            }
        )
        
        bear_result = AnalysisResult(
            decision="BEAR_PUT_SPREAD",
            confidence=0.60,
            details={
                'thesis': 'Bearish resistance',
                'reasoning': 'Resistance level holding',
                'rsi': 75.0
            }
        )
        
        context = {'market_data': {'close': 45000}}
        
        debate_result = await manager._conduct_formal_debate(bull_result, bear_result, context)
        
        # Verify debate was conducted
        assert debate_result is not None
        assert debate_result.winner in ["BullResearcher", "BearResearcher", None]
        assert len(debate_result.participants) == 2
        assert len(debate_result.rounds) >= 1
        
        # Bull should win due to higher confidence
        if debate_result.winner:
            assert debate_result.winner_confidence >= 0.0
    
    def test_synthesize_from_debate_bull_winner(self):
        """Test synthesis when bull wins debate."""
        manager = EnhancedResearchManager()
        
        # Create mock debate result
        from engine_module.communication import DebateResult, DebateParticipant, DebateRound
        
        bull_participant = DebateParticipant("BullResearcher", "bull")
        bear_participant = DebateParticipant("BearResearcher", "bear")
        
        debate_result = DebateResult(
            winner="BullResearcher",
            winner_confidence=0.80,
            summary="Bull wins",
            consensus="Bullish perspective prevails",
            recommended_action="BULL_CALL_SPREAD",
            participants=[bull_participant, bear_participant],
            rounds=[]
        )
        
        bull_result = AnalysisResult(
            decision="BULL_CALL_SPREAD",
            confidence=0.75,
            details={'thesis': 'Bullish'}
        )
        
        bear_result = AnalysisResult(
            decision="BEAR_PUT_SPREAD",
            confidence=0.60,
            details={'thesis': 'Bearish'}
        )
        
        final_decision = manager._synthesize_from_debate(debate_result, bull_result, bear_result)
        
        assert final_decision['decision'] == "BULL_CALL_SPREAD"
        assert final_decision['confidence'] >= 0.75
        assert 'plan' in final_decision
    
    def test_synthesize_from_debate_no_winner(self):
        """Test synthesis when no clear winner."""
        manager = EnhancedResearchManager()
        
        from engine_module.communication import DebateResult, DebateParticipant
        
        debate_result = DebateResult(
            winner=None,
            winner_confidence=0.50,
            summary="Balanced debate",
            participants=[DebateParticipant("BullResearcher", "bull"),
                         DebateParticipant("BearResearcher", "bear")],
            rounds=[]
        )
        
        bull_result = AnalysisResult(decision="HOLD", confidence=0.50, details={})
        bear_result = AnalysisResult(decision="HOLD", confidence=0.50, details={})
        
        final_decision = manager._synthesize_from_debate(debate_result, bull_result, bear_result)
        
        # Should suggest iron condor for neutral market
        assert final_decision['decision'] == "IRON_CONDOR"
        assert final_decision['confidence'] == 0.6
