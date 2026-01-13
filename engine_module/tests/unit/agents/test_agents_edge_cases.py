import pytest
from engine_module.agents.enhanced_technical_agent import EnhancedTechnicalAgent
from engine_module.agents.enhanced_momentum_agent import EnhancedMomentumAgent
from engine_module.agents.options_analysis_agent import OptionsAnalysisAgent
from engine_module.agents.technical_agent import TechnicalAgent
from engine_module.agents.mean_reversion_agent import MeanReversionAgent
from engine_module.agents.trend_agent import TrendAgent
from engine_module.agents.volume_agent import VolumeAgent
from engine_module.agents.sentiment_agent import SentimentAgent
from engine_module.agents.execution_agent import ExecutionAgent
from engine_module.contracts import AnalysisResult


@pytest.mark.asyncio
async def test_enhanced_technical_agent_invalid_indicators():
    agent = EnhancedTechnicalAgent()
    res = await agent.analyze({'indicators': {}})
    assert res.decision == 'HOLD'
    assert isinstance(res.details, dict)
    assert 'error' in res.details


@pytest.mark.asyncio
async def test_enhanced_momentum_agent_missing_indicators():
    agent = EnhancedMomentumAgent()

    # Missing technical indicators and market data rsi
    res = await agent.analyze({
        'market_data': {},
        'technical_indicators': {},
        'multi_timeframe': {},
        'current_positions': []
    })

    assert res.decision == 'HOLD'
    assert res.confidence <= agent.min_confidence


@pytest.mark.asyncio
async def test_options_analysis_agent_insufficient_data():
    agent = OptionsAnalysisAgent()
    res = await agent.analyze({'calls': [], 'puts': [], 'underlying_price': None})
    assert res.decision == 'HOLD'
    assert res.details and res.details.get('note') == 'INSUFFICIENT_OPTIONS_DATA'


@pytest.mark.asyncio
async def test_technical_agent_missing_close_column():
    agent = TechnicalAgent()
    ohlc = [{'open': 100, 'high': 101, 'low': 99}]  # missing close
    res = await agent.analyze({'ohlc': ohlc})
    assert res.decision == 'HOLD'
    assert res.details and 'MISSING_COLUMN_close' in res.details.get('note', '')


@pytest.mark.asyncio
async def test_mean_reversion_insufficient_data():
    agent = MeanReversionAgent()
    ohlc = [{'open': 100, 'high': 101, 'low': 99, 'close': 100}] * 10
    res = await agent.analyze({'ohlc': ohlc})
    assert res.decision == 'HOLD'
    assert res.details and res.details.get('reason') == 'INSUFFICIENT_DATA'


@pytest.mark.asyncio
async def test_trend_agent_insufficient_data():
    agent = TrendAgent()
    ohlc = [{'open': 100, 'high': 101, 'low': 99, 'close': 100}] * 10
    res = await agent.analyze({'ohlc': ohlc})
    assert res.decision == 'HOLD'
    assert res.details and res.details.get('reason') == 'INSUFFICIENT_DATA'


@pytest.mark.asyncio
async def test_volume_agent_insufficient_data():
    agent = VolumeAgent()
    ohlc = [{'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1000}] * 10
    res = await agent.analyze({'ohlc': ohlc})
    assert res.decision == 'HOLD'
    assert res.details and res.details.get('reason') == 'INSUFFICIENT_DATA'


@pytest.mark.asyncio
async def test_sentiment_agent_no_news():
    agent = SentimentAgent()
    res = await agent.analyze({'latest_news': [], 'sentiment_score': 0.0})
    assert res.decision == 'HOLD'
    assert res.details.get('note') == 'No recent news'


@pytest.mark.asyncio
async def test_execution_agent_zero_quantity():
    agent = ExecutionAgent(paper_trading=True)
    ctx = {
        'final_signal': 'BUY',
        'position_size': 0,
        'entry_price': 100.0,
        'stop_loss': 95.0,
        'take_profit': 110.0,
        'current_price': 100.0,
        'confidence': 0.6
    }
    res = await agent.analyze(ctx)
    assert res.decision == 'HOLD'
    assert res.details.get('note') == 'ZERO_QUANTITY'

