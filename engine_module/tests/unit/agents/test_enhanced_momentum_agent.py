"""Unit tests for Enhanced Momentum Agent."""

import pytest
from engine_module.agents.enhanced_momentum_agent import EnhancedMomentumAgent
from engine_module.contracts import AnalysisResult


class TestEnhancedMomentumAgent:
    """Tests for EnhancedMomentumAgent."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        agent = EnhancedMomentumAgent()
        
        assert agent.name == "EnhancedMomentumAgent"
        assert agent.rsi_oversold == 30
        assert agent.rsi_overbought == 70
        assert agent.volume_threshold == 1.5
        assert agent.adx_threshold == 25
        assert agent.min_confidence == 0.60
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        config = {
            'rsi_oversold': 25,
            'rsi_overbought': 75,
            'volume_threshold': 2.0,
            'adx_threshold': 30,
            'min_confidence': 0.70
        }
        agent = EnhancedMomentumAgent(config)
        
        assert agent.rsi_oversold == 25
        assert agent.rsi_overbought == 75
        assert agent.volume_threshold == 2.0
        assert agent.adx_threshold == 30
        assert agent.min_confidence == 0.70
    
    @pytest.mark.asyncio
    async def test_analyze_bullish_momentum(self):
        """Test bullish momentum signal generation."""
        agent = EnhancedMomentumAgent({'min_confidence': 0.50})
        
        context = {
            'market_data': {
                'close': 45000,
                'current_price': 45000,
                'instrument': 'BANKNIFTY'
            },
            'multi_timeframe': {
                '15m': {'rsi': 28.0},
                '1h': {'rsi': 35.0}
            },
            'regime': 'trending_up',
            'current_positions': [],
            'technical_indicators': {
                'rsi': 28.0,
                'macd': 50.0,
                'macd_signal': 45.0,
                'adx': 30.0,
                'volume_ratio': 2.0,
                'ema_50': 44800
            }
        }
        
        result = await agent.analyze(context)
        
        assert result.decision in ['BUY', 'HOLD']
        assert result.confidence >= 0.50
        assert 'structured_report' in result.details
        assert result.details['strategy'] == 'momentum'
    
    @pytest.mark.asyncio
    async def test_analyze_bearish_momentum(self):
        """Test bearish momentum signal generation."""
        agent = EnhancedMomentumAgent({'min_confidence': 0.50})
        
        context = {
            'market_data': {
                'close': 45000,
                'current_price': 45000,
                'instrument': 'BANKNIFTY'
            },
            'multi_timeframe': {
                '15m': {'rsi': 75.0},
                '1h': {'rsi': 70.0}
            },
            'regime': 'trending_down',
            'current_positions': [],
            'technical_indicators': {
                'rsi': 75.0,
                'macd': 40.0,
                'macd_signal': 50.0,
                'adx': 28.0,
                'volume_ratio': 1.8,
                'ema_50': 45200
            }
        }
        
        result = await agent.analyze(context)
        
        assert result.decision in ['SELL', 'HOLD']
        assert 'structured_report' in result.details
    
    @pytest.mark.asyncio
    async def test_analyze_hold_no_signals(self):
        """Test HOLD when no clear momentum signals."""
        agent = EnhancedMomentumAgent({'min_confidence': 0.70})
        
        context = {
            'market_data': {
                'close': 45000,
                'current_price': 45000
            },
            'multi_timeframe': {
                '15m': {'rsi': 50.0}
            },
            'regime': 'ranging',
            'current_positions': [],
            'technical_indicators': {
                'rsi': 50.0,
                'macd': 45.0,
                'macd_signal': 45.0,
                'adx': 15.0,
                'volume_ratio': 1.0,
                'ema_50': 45000
            }
        }
        
        result = await agent.analyze(context)
        
        assert result.decision == "HOLD"
        assert result.confidence < agent.min_confidence
    
    @pytest.mark.asyncio
    async def test_exit_conditions_rsi_reversal(self):
        """Test exit signal on RSI reversal."""
        agent = EnhancedMomentumAgent()
        
        context = {
            'market_data': {
                'close': 44800,
                'current_price': 44800
            },
            'multi_timeframe': {},
            'regime': None,
            'current_positions': [
                {
                    'id': 'pos_1',
                    'type': 'LONG',
                    'entry_price': 45000,
                    'strategy': 'momentum'
                }
            ],
            'technical_indicators': {
                'rsi': 45.0,  # Below 50 for long position
                'volume_ratio': 1.0
            }
        }
        
        result = await agent.analyze(context)
        
        # Should exit long position due to RSI reversal
        assert result.decision == "CLOSE" or result.decision == "HOLD"
    
    @pytest.mark.asyncio
    async def test_exit_conditions_stop_loss(self):
        """Test exit signal on stop loss hit."""
        agent = EnhancedMomentumAgent()
        
        context = {
            'market_data': {
                'close': 44100,  # 2% loss
                'current_price': 44100
            },
            'multi_timeframe': {},
            'regime': None,
            'current_positions': [
                {
                    'id': 'pos_1',
                    'type': 'LONG',
                    'entry_price': 45000,
                    'strategy': 'momentum'
                }
            ],
            'technical_indicators': {
                'rsi': 55.0,  # Not reversal level
                'volume_ratio': 1.0
            }
        }
        
        result = await agent.analyze(context)
        
        # Should exit due to stop loss (-2%)
        assert result.decision == "CLOSE"
        assert result.confidence >= 0.80
        assert 'reason' in result.details
        assert 'stop' in result.details['reason'].lower() or 'loss' in result.details['reason'].lower()
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_integration(self):
        """Test multi-timeframe analysis integration."""
        agent = EnhancedMomentumAgent()
        
        context = {
            'market_data': {
                'close': 45000,
                'current_price': 45000,
                'instrument': 'BANKNIFTY'
            },
            'multi_timeframe': {
                '15m': {'rsi': 28.0},
                '1h': {'rsi': 32.0},
                'daily': {'rsi': 40.0}
            },
            'regime': 'trending_up',
            'current_positions': [],
            'technical_indicators': {
                'rsi': 28.0,
                'macd': 50.0,
                'macd_signal': 45.0,
                'adx': 30.0,
                'volume_ratio': 2.0,
                'ema_50': 44800
            }
        }
        
        result = await agent.analyze(context)
        
        # Check that multi-timeframe data is used
        details = result.details
        technical_data = details.get('technical_data', {})
        assert 'rsi_15m' in technical_data or 'rsi_1h' in technical_data
        
        # Check structured report has multi-timeframe section
        structured_report = details.get('structured_report', {})
        sections = structured_report.get('sections', [])
        mtf_section = next((s for s in sections if 'Multi-Timeframe' in s.get('title', '')), None)
        assert mtf_section is not None
    
    def test_build_reasoning(self):
        """Test reasoning building."""
        agent = EnhancedMomentumAgent()
        
        conditions = {
            'rsi_oversold_15m': True,
            'volume_spike': True,
            'macd_bullish': True,
            'adx_strong': False
        }
        
        market_data = {
            'rsi': 28.0,
            'volume_ratio': 2.0,
            'adx': 20.0
        }
        
        reasoning = agent._build_reasoning('BUY', conditions, market_data, {})
        
        assert 'BUY signal detected' in reasoning
        assert 'Conditions Met' in reasoning
        assert 'rsi_oversold_15m' in reasoning.lower() or 'rsi oversold' in reasoning.lower()
    
    def test_recommend_position(self):
        """Test position recommendation."""
        agent = EnhancedMomentumAgent()
        
        risk_assessment = {'risk_score': 50}
        
        recommendation = agent._recommend_position('BUY', 0.85, risk_assessment)
        
        assert recommendation['action'] == 'BUY'
        assert recommendation['size_multiplier'] == 1.5  # High confidence
        assert recommendation['stop_loss_pct'] == 0.02
        assert recommendation['take_profit_pct'] == 0.04
