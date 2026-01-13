"""Unit tests for Enhanced Base Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from engine_module.agents.base_agent import BaseAgent, SignalStrength
from engine_module.contracts import AnalysisResult
from engine_module.communication import ReportType, ReportPriority


class MockEnhancedAgent(BaseAgent):
    """Mock agent for testing BaseAgent."""
    
    async def _analyze_internal(
        self,
        market_data,
        multi_timeframe,
        regime,
        current_positions,
        technical_indicators,
        context
    ):
        """Mock analysis implementation."""
        return AnalysisResult(
            decision="BUY",
            confidence=0.75,
            details={
                "reasoning": "Test reasoning",
                "target": "BANKNIFTY"
            },
            agent=self.name
        )


class TestBaseAgent:
    """Tests for BaseAgent."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        agent = MockEnhancedAgent("TestAgent")
        
        assert agent.name == "TestAgent"
        assert agent._agent_name == "TestAgent"
        assert agent.min_confidence == 0.60
        assert agent.use_structured_reports is True
        assert agent.use_multi_timeframe is True
        assert agent.use_regime_detection is True
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        config = {
            'min_confidence': 0.70,
            'use_structured_reports': False,
            'use_multi_timeframe': False
        }
        agent = MockEnhancedAgent("TestAgent", config)
        
        assert agent.min_confidence == 0.70
        assert agent.use_structured_reports is False
        assert agent.use_multi_timeframe is False
    
    @pytest.mark.asyncio
    async def test_analyze_with_structured_reports(self):
        """Test analyze method with structured reports enabled."""
        agent = MockEnhancedAgent("TestAgent")
        
        context = {
            'market_data': {
                'close': 45000,
                'rsi': 65.0,
                'instrument': 'BANKNIFTY'
            },
            'multi_timeframe': {},
            'regime': 'trending_up',
            'current_positions': [],
            'technical_indicators': {'rsi': 65.0}
        }
        
        result = await agent.analyze(context)
        
        assert result.decision == "BUY"
        assert result.confidence == 0.75
        assert 'structured_report' in result.details
        assert result.details['signal_strength'] == 'strong'
        
        structured_report = result.details['structured_report']
        assert structured_report['agent_name'] == "TestAgent"
        assert structured_report['report_type'] == 'recommendation'
    
    @pytest.mark.asyncio
    async def test_analyze_without_structured_reports(self):
        """Test analyze method with structured reports disabled."""
        config = {'use_structured_reports': False}
        agent = MockEnhancedAgent("TestAgent", config)
        
        context = {
            'market_data': {'close': 45000},
            'multi_timeframe': {},
            'regime': None,
            'current_positions': [],
            'technical_indicators': {}
        }
        
        result = await agent.analyze(context)
        
        assert result.decision == "BUY"
        assert 'structured_report' not in result.details or result.details.get('structured_report') is None
    
    @pytest.mark.asyncio
    async def test_analyze_error_handling(self):
        """Test error handling in analyze method."""
        class FailingAgent(BaseAgent):
            async def _analyze_internal(self, *args, **kwargs):
                raise ValueError("Test error")
        
        agent = FailingAgent("FailingAgent")
        
        context = {
            'market_data': {},
            'multi_timeframe': {},
            'regime': None,
            'current_positions': [],
            'technical_indicators': {}
        }
        
        result = await agent.analyze(context)
        
        assert result.decision == "HOLD"
        assert result.confidence == 0.0
        assert 'error' in result.details
        assert result.details['reason'] == "ANALYSIS_ERROR"
    
    def test_calculate_confidence(self):
        """Test confidence calculation."""
        agent = MockEnhancedAgent("TestAgent")
        
        conditions = {
            'condition1': True,
            'condition2': True,
            'condition3': False,
            'condition4': True
        }
        
        confidence = agent._calculate_confidence(conditions)
        assert confidence == 0.75  # 3/4 conditions met
        
        # With weights
        weights = {
            'condition1': 2.0,
            'condition2': 1.0,
            'condition3': 1.0,
            'condition4': 1.0
        }
        
        weighted_confidence = agent._calculate_confidence(conditions, weights)
        # (2.0 + 1.0 + 0.0 + 1.0) / 5.0 = 0.8
        assert abs(weighted_confidence - 0.8) < 0.01
    
    def test_assess_risk(self):
        """Test risk assessment."""
        agent = MockEnhancedAgent("TestAgent")
        
        market_data = {
            'iv_percentile': 85,
            'close': 45000
        }
        current_positions = [
            {'exposure': 0.3},
            {'exposure': 0.2}
        ]
        
        risk_assessment = agent._assess_risk(market_data, "BUY", current_positions)
        
        assert 'risk_score' in risk_assessment
        assert 'risk_level' in risk_assessment
        assert risk_assessment['portfolio_exposure'] == 0.5
        assert risk_assessment['risk_score'] >= 30  # High IV + exposure
    
    def test_check_exit_conditions(self):
        """Test exit condition checking."""
        agent = MockEnhancedAgent("TestAgent")
        
        market_data = {
            'close': 44000,
            'current_price': 44000
        }
        current_positions = [
            {
                'id': 'pos_1',
                'type': 'LONG',
                'entry_price': 45000
            }
        ]
        
        exit_signal = agent._check_exit_conditions(market_data, current_positions, {})
        
        assert exit_signal is not None
        assert exit_signal.decision == "CLOSE"
        assert exit_signal.confidence == 0.80
    
    def test_check_exit_conditions_no_exit(self):
        """Test exit conditions when no exit needed."""
        agent = MockEnhancedAgent("TestAgent")
        
        market_data = {
            'close': 44800,  # Small loss, not enough to trigger exit
            'current_price': 44800
        }
        current_positions = [
            {
                'id': 'pos_1',
                'type': 'LONG',
                'entry_price': 45000
            }
        ]
        
        exit_signal = agent._check_exit_conditions(market_data, current_positions, {})
        
        assert exit_signal is None
    
    def test_signal_strength_from_confidence(self):
        """Test signal strength calculation."""
        assert SignalStrength.from_confidence(0.95) == SignalStrength.VERY_STRONG
        assert SignalStrength.from_confidence(0.75) == SignalStrength.STRONG
        assert SignalStrength.from_confidence(0.60) == SignalStrength.MODERATE
        assert SignalStrength.from_confidence(0.40) == SignalStrength.WEAK
        assert SignalStrength.from_confidence(0.20) == SignalStrength.VERY_WEAK
