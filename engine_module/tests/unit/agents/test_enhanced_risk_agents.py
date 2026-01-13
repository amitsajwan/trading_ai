"""Unit tests for Enhanced Risk Agents."""

import pytest
from engine_module.agents.enhanced_risk_agents import EnhancedRiskAgent
from engine_module.contracts import AnalysisResult


class TestEnhancedRiskAgent:
    """Tests for EnhancedRiskAgent."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        agent = EnhancedRiskAgent()
        
        assert agent.name == "EnhancedRiskAgent"
        assert agent.risk_tolerance == "moderate"
        assert agent.max_portfolio_risk == 0.02  # 2%
        assert agent.max_position_risk == 0.01  # 1%
        assert agent.deliberation_protocol.max_rounds == 2
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        config = {
            'risk_tolerance': 'conservative',
            'max_portfolio_risk': 0.01,
            'max_position_risk': 0.005
        }
        agent = EnhancedRiskAgent(config)
        
        assert agent.risk_tolerance == "conservative"
        assert agent.max_portfolio_risk == 0.01
        assert agent.max_position_risk == 0.005
    
    @pytest.mark.asyncio
    async def test_analyze_high_risk_veto(self):
        """Test risk veto when risk is too high."""
        agent = EnhancedRiskAgent({
            'max_portfolio_risk': 0.02
        })
        
        context = {
            'market_data': {
                'close': 45000,
                'iv_percentile': 85,  # High IV
                'account_balance': 1000000
            },
            'multi_timeframe': {},
            'regime': 'high_volatility',
            'current_positions': [
                {
                    'max_loss': 30000,  # 3% of 10L portfolio
                    'risk_amount': 30000
                }
            ],
            'technical_indicators': {},
            'proposed_action': 'BUY'
        }
        
        result = await agent.analyze(context)
        
        # Should veto or caution due to high risk
        assert result.decision in ["VETO", "CAUTION", "HOLD"]
        assert 'risk_level' in result.details
        assert result.details['risk_level'] in ['HIGH', 'MEDIUM']
    
    @pytest.mark.asyncio
    async def test_analyze_low_risk_approve(self):
        """Test approval when risk is acceptable."""
        agent = EnhancedRiskAgent({
            'max_portfolio_risk': 0.02
        })
        
        context = {
            'market_data': {
                'close': 45000,
                'iv_percentile': 50,  # Normal IV
                'account_balance': 1000000
            },
            'multi_timeframe': {},
            'regime': 'ranging',
            'current_positions': [
                {
                    'max_loss': 10000,  # 1% of portfolio
                    'risk_amount': 10000
                }
            ],
            'technical_indicators': {},
            'proposed_action': 'BUY'
        }
        
        result = await agent.analyze(context)
        
        # Should approve or hold (not veto)
        assert result.decision in ["APPROVE", "HOLD", "CAUTION"]
        assert 'risk_level' in result.details
        assert result.details['risk_level'] in ['LOW', 'MEDIUM']
    
    @pytest.mark.asyncio
    async def test_conduct_risk_deliberation(self):
        """Test risk deliberation mechanism."""
        agent = EnhancedRiskAgent()
        
        market_data = {
            'iv_percentile': 75,
            'close': 45000,
            'account_balance': 1000000
        }
        current_positions = [
            {'max_loss': 15000, 'risk_amount': 15000}  # 1.5% portfolio risk
        ]
        technical_indicators = {'volatility': 0.25}
        
        context = {}
        
        deliberation_result = await agent._conduct_risk_deliberation(
            market_data, current_positions, technical_indicators, context
        )
        
        assert deliberation_result is not None
        assert len(deliberation_result.participants) == 2  # Conservative and Moderate
        assert 'ConservativeRiskPerspective' in [p.name for p in deliberation_result.participants]
        assert 'ModerateRiskPerspective' in [p.name for p in deliberation_result.participants]
    
    def test_calculate_portfolio_risk(self):
        """Test portfolio risk calculation."""
        agent = EnhancedRiskAgent()
        
        current_positions = [
            {'max_loss': 10000, 'risk_amount': 10000},
            {'max_loss': 15000, 'risk_amount': 15000}
        ]
        market_data = {'account_balance': 1000000}  # 10L
        
        portfolio_risk = agent._calculate_portfolio_risk(current_positions, market_data)
        
        # Total risk = 25000, portfolio = 10L, risk % = 2.5%
        assert abs(portfolio_risk - 0.025) < 0.001
    
    def test_calculate_portfolio_risk_no_positions(self):
        """Test portfolio risk with no positions."""
        agent = EnhancedRiskAgent()
        
        portfolio_risk = agent._calculate_portfolio_risk([], {'account_balance': 1000000})
        
        assert portfolio_risk == 0.0
    
    def test_determine_risk_level(self):
        """Test risk level determination."""
        agent = EnhancedRiskAgent({'max_portfolio_risk': 0.02})
        
        from engine_module.communication import DebateResult, DebateParticipant
        
        # High risk scenario
        deliberation_result = DebateResult(
            winner="ConservativeRiskPerspective",
            winner_confidence=0.9,
            summary="High risk",
            participants=[],
            rounds=[]
        )
        
        market_data = {'account_balance': 1000000}
        current_positions = [
            {'max_loss': 30000}  # 3% risk
        ]
        
        risk_level = agent._determine_risk_level(deliberation_result, market_data, current_positions)
        
        assert risk_level == "HIGH"
    
    def test_make_risk_decision(self):
        """Test risk decision making."""
        agent = EnhancedRiskAgent()
        
        context = {'proposed_action': 'BUY'}
        
        # High risk -> VETO
        decision_high = agent._make_risk_decision("HIGH", context)
        assert decision_high == "VETO"
        
        # Medium risk -> CAUTION
        decision_medium = agent._make_risk_decision("MEDIUM", context)
        assert decision_medium == "CAUTION"
        
        # Low risk -> APPROVE
        decision_low = agent._make_risk_decision("LOW", context)
        assert decision_low == "APPROVE"
        
        # No proposed action -> HOLD
        context_no_action = {}
        decision_no_action = agent._make_risk_decision("LOW", context_no_action)
        assert decision_no_action == "HOLD"
