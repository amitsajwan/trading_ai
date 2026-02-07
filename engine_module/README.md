# ENGINE_MODULE - Trading Decision Engine

**Status: ✅ PRODUCTION READY** - Complete multi-agent trading decision system with LLM integration and comprehensive data providers.

A comprehensive trading decision engine orchestrating market data analysis, multi-agent consensus, and LLM-powered final decisions for automated trading.

**📚 Documentation:** See [docs/index.md](docs/index.md) for complete documentation index.

## 🎯 Purpose & Architecture

The engine module orchestrates the complete trading decision process:

```
Market Data → Agent Analysis → Signal Aggregation → LLM Decision → Trade Execution
```

### **Core Components:**
- **TradingOrchestrator**: Coordinates the entire analysis pipeline
- **Multi-Agent Suite**: Technical, sentiment, macro, research, risk, execution, portfolio, options agents
- **Signal Aggregation**: Combines agent opinions into consensus
- **LLM Integration**: Final decision making with reasoning
- **15-Minute Cycles**: Real-time analysis cadence
- **Direct Redis Access**: Reads market data and technical indicators directly from Redis

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Redis (running)
- MongoDB (for signal storage)
- LLM API keys (Groq/Cohere/AI21)

### Installation
```bash
# Install dependencies
pip install -r requirements.txt
```

### Basic Usage
```python
from engine_module.api import build_orchestrator

# Create orchestrator
orchestrator = build_orchestrator()

# Run analysis cycle
decision = await orchestrator.run_analysis_cycle()
print(f"Decision: {decision.action}, Confidence: {decision.confidence}")
```

## 🆕 Recent Updates (January 2026)

### ✅ Data Provider Fixes
- **Fixed EnhancedTradingOrchestrator**: Added OHLC data fetching for TechnicalAgent and VolumeAgent
- **Added Missing Data Providers**: News, Fundamental, and Macro data providers for complete agent support
- **Integrated OptionsAnalysisAgent**: Ensured proper options data flow

### ✅ Documentation Improvements
- **Created DATA_REFERENCE.md**: Comprehensive data structures and API reference
- **Organized Documentation**: Clean index structure in [docs/index.md](docs/index.md)
- **Added Data Flow Diagrams**: Complete system architecture documentation

### ✅ Agent Compatibility
All agents now have proper data access:
- ✅ **TechnicalAgent**: OHLC data from market_data_provider
- ✅ **VolumeAgent**: OHLC data from market_data_provider
- ✅ **SentimentAgent**: News data from news_data_provider
- ✅ **FundamentalAgent**: Fundamental data from fundamental_data_provider
- ✅ **MacroAgent**: Macro data from macro_data_provider
- ✅ **OptionsAnalysisAgent**: Options data from options_data_provider

## 🔧 API Reference

### Factory Functions
```python
from engine_module.api import (
    build_orchestrator,       # Main orchestrator factory
    create_agent_suite,       # Agent collection creation
    get_analysis_status      # Analysis cycle status
)
```

### Key Classes
```python
class TradingOrchestrator:
    """Coordinates the entire trading analysis pipeline."""

    async def run_analysis_cycle(self) -> Decision:
        """Execute complete analysis cycle."""

    async def get_agent_signals(self) -> Dict[str, Signal]:
        """Get signals from all agents."""
```

### Endpoints
- `GET /api/v1/analysis/status` - Current analysis status
- `POST /api/v1/analysis/run` - Trigger analysis cycle
- `GET /api/v1/agents/{agent_id}/signal` - Individual agent signals

## 🧪 Testing

### Run Tests
```bash
# From engine_module directory
cd engine_module
pytest tests/

# Run agent tests
pytest tests/test_agents.py

# With coverage
pytest --cov=src --cov-report=html
```

### Test Structure
- `tests/test_orchestrator.py` - Orchestrator tests
- `tests/test_agents.py` - Individual agent tests
- `tests/test_integration.py` - Full pipeline integration tests

## 🏗️ Development

### Project Structure
```
engine_module/
├── src/
│   ├── __init__.py
│   ├── orchestrator.py      # TradingOrchestrator
│   ├── agents/             # Agent implementations
│   └── signals.py          # Signal processing
├── tests/
│   ├── __init__.py
│   ├── test_orchestrator.py
│   └── test_agents.py
├── contracts/             # Agent protocols
├── tools/                 # Analysis utilities
└── README.md             # This file
```

### Adding New Agents
1. Define agent protocol in `contracts/`
2. Implement agent in `src/agents/`
3. Add to orchestrator agent suite
4. Add tests in `tests/`
5. Update this README

## 📊 Dependencies

### Internal Dependencies
- `core_kernel` - Service container
- `market_data` - Market data access
- `genai_module` - LLM integration
- `news_module` - News sentiment

### External Dependencies
- `redis` - Redis client
- `pymongo` - MongoDB driver
- `httpx` - HTTP client for APIs

## 🔍 Troubleshooting

### Common Issues
- **Redis connection failed**: Ensure Redis is running on port 6379
- **LLM API errors**: Check API keys and rate limits
- **Agent timeouts**: Review agent implementation for blocking calls

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python -c "from engine_module.api import build_orchestrator; print('Engine ready')"
```

## 🤝 Contributing

1. Follow the existing code style
2. Add tests for new agents
3. Update agent documentation
4. Submit PR with clear description

## 🤖 Agent Ecosystem

### **Analysis Agents (Core Set)**

#### **1. TechnicalAgent** - Price Action & Indicators
```python
# Analyzes OHLC data for trading signals
analysis = await technical_agent.analyze({
    "ohlc": [[open, high, low, close, volume], ...],
    "current_price": 60125.5
})
# Returns: RSI, trend direction, support/resistance, momentum signals
```

#### **2. SentimentAgent** - Market Psychology
```python
# Processes news and sentiment data
analysis = await sentiment_agent.analyze({
    "latest_news": [{"title": "...", "sentiment": 0.8}, ...],
    "sentiment_score": 0.65
})
# Returns: Retail/institutional sentiment, fear/greed index
```

#### **3. MacroAgent** - Economic Analysis
```python
# Analyzes economic indicators
analysis = await macro_agent.analyze({
    "rbi_rate": 6.5,
    "inflation": 4.8,
    "gdp_growth": 6.2
})
# Returns: Economic outlook, policy impact, market direction bias
```

#### **4. RiskAgent** - Position Risk Management
```python
# Evaluates trade risk parameters
analysis = await risk_agent.analyze(context)
# Returns: Risk level assessment, position limits, stop loss requirements
```

#### **5. ExecutionAgent** - Trade Validation
```python
# Validates trade execution feasibility
analysis = await execution_agent.analyze({
    "signal": "BUY",
    "quantity": 10,
    "entry_price": 45000,
    "stop_loss": 44500
})
# Returns: Execution readiness, slippage estimates, broker fees
```

#### **6-9. Additional Agents**
- **PortfolioManagerAgent**: Aggregates all agent signals
- **ReviewAgent**: Analysis summaries and reporting
- **FundamentalAgent**: Company/stock analysis
- **LearningAgent**: Adaptive strategy optimization

## 📊 Analysis Tools

### **Multi-Timeframe Analyzer** - Confluence Detection

Analyzes market data across multiple timeframes (5m, 15m, 1h, daily) to identify trend confluence and trading signal strength.

```python
from engine_module.analysis import MultiTimeframeAnalyzer
from market_data import TechnicalIndicatorsService

# Initialize analyzer
analyzer = MultiTimeframeAnalyzer({
    'timeframes': ['5m', '15m', '1h', 'daily'],
    'required_alignment': 3  # Minimum timeframes that must agree
})

# Get indicators for all timeframes (from TechnicalIndicatorsService)
indicators_service = TechnicalIndicatorsService(redis_client)
all_indicators = indicators_service.get_all_timeframe_indicators("BANKNIFTY")

# Convert TechnicalIndicators objects to dict format
indicators_data = {}
for tf, indicators in all_indicators.items():
    indicators_data[tf] = {
        'close': indicators.current_price,
        'sma_20': indicators.sma_20,
        'ema_50': indicators.ema_50,
        'rsi': indicators.rsi_14,
        'macd': indicators.macd_value,
        'macd_signal': indicators.macd_signal,
        'adx': indicators.adx_14
    }

# Analyze for confluence
analysis = analyzer.analyze(indicators_data)

print(f"Dominant Trend: {analysis.dominant_trend.value}")
print(f"Confluence Score: {analysis.confluence_score:.1f}%")
print(f"Timeframes Aligned: {analysis.is_aligned}")
print(f"Bullish: {analysis.bullish_count}, Bearish: {analysis.bearish_count}")

# Get trading signal
signal = analyzer.get_trading_signal(analysis)
print(f"Signal: {signal['action']} (Confidence: {signal['confidence']}%)")
# Output: Signal: BUY (Confidence: 85%) - Bullish confluence (87.5%) across 4 timeframes
```

**Features:**
- **Trend Detection**: Determines bullish/bearish/neutral trend for each timeframe
- **Strength Calculation**: Calculates trend strength (0-100) based on ADX, RSI, MACD
- **Confluence Score**: Measures agreement across timeframes (0-100%)
- **Dominant Trend**: Identifies overall trend weighted by timeframe importance
- **Alignment Check**: Verifies if timeframes agree on direction
- **Trading Signals**: Generates BUY/SELL/HOLD signals with confidence scores

**Configuration:**
```python
config = {
    'timeframes': ['5m', '15m', '1h', 'daily'],
    'required_alignment': 3,  # Min timeframes that must agree
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'adx_trending': 25,
    'timeframe_weights': {
        '5m': 1,    # Lower weight (short-term noise)
        '15m': 2,
        '1h': 3,
        'daily': 4  # Higher weight (long-term trend)
    }
}
analyzer = MultiTimeframeAnalyzer(config)
```

### **Regime Detector** - Market State Identification

Detects current market regime (trending, ranging, high volatility, breakout) for strategy selection.

```python
from engine_module.analysis import RegimeDetector, MarketRegime

# Initialize detector
detector = RegimeDetector({
    'adx_trending': 25,
    'iv_high_percentile': 80,
    'volume_spike_threshold': 2.0
})

# Get market data with indicators
market_data = {
    'close': 45000,
    'sma_20': 44800,
    'ema_50': 44700,
    'adx': 30,
    'iv_percentile': 75,
    'volume_ratio': 1.8,
    'bollinger_upper': 45200,
    'bollinger_lower': 44500,
    'bollinger_percent_b': 0.85
}

# Detect regime
regime = detector.detect(market_data)
print(f"Market Regime: {regime.value}")

# Get suitable strategies for this regime
strategies = detector.get_suitable_strategies(regime)
print(f"Suitable Strategies: {strategies}")
# Output: ['iron_condor', 'butterfly', 'short_strangle'] for RANGING regime
```

**Detected Regimes:**
- **TRENDING_UP**: Strong upward trend (ADX > 25, price > MAs)
- **TRENDING_DOWN**: Strong downward trend (ADX > 25, price < MAs)
- **RANGING**: Sideways market (low ADX, price oscillating)
- **HIGH_VOLATILITY**: High IV regime (IV percentile > 80)
- **BREAKOUT_UP**: Upward breakout (volume spike + price near upper BB)
- **BREAKOUT_DOWN**: Downward breakout (volume spike + price near lower BB)

## 🎯 Orchestrator: The Brain

### Real-time signals & Redis integration (added 2026-01-09)

The engine now supports a loosely-coupled real-time signal integration using Redis pub/sub and a small Redis-backed state store for previous indicator values.

Key points:
- Technical indicators are published by the Market Data module to channel `indicators:{instrument}` as JSON messages. See `market_data/technical_indicators_service.py`.
- For CROSSES detection we persist the previous indicator value in Redis using `indicators_prev:{instrument}:{indicator}` (TTL default: 4 hours). This makes `CROSSES_ABOVE` / `CROSSES_BELOW` robust across restarts and multiple workers.
- New engine endpoints:
  - `GET /api/v1/signals/by-id/{signal_id}` — fetch full signal document
  - `POST /api/v1/signals/mark-executed` — mark a signal executed
- `RealtimeSignalProcessor` subscribes to `indicators:*` messages and triggers `SignalMonitor.check_signals(instrument)` on updates.

This design keeps producers (market data) and consumers (signal monitor/executor) loosely coupled and scalable.

## 🎯 Orchestrator: The Brain

### **TradingOrchestrator** - Decision Engine

```python
class TradingOrchestrator:
    async def run_cycle(self, context: Dict[str, Any]) -> AnalysisResult:
        # 1. Fetch market data (15-min OHLC, current ticks)
        market_data = await self._fetch_market_data(instrument)

        # 2. Fetch options chain data
        options_chain = await self._fetch_options_data(instrument)

        # 3. Run all agents in parallel
        agent_results = await self._run_agents_parallel(market_data, options_chain, context)

        # 4. Aggregate signals intelligently
        aggregated = self._aggregate_results(agent_results)

        # 5. Generate final decision with LLM
        if market_hours and self.llm_client:
            final_decision = await self._generate_llm_decision(aggregated, context)
        else:
            final_decision = self._generate_fallback_decision(aggregated, market_hours)

        return final_decision
```

### **15-Minute Analysis Cycle**

Every 15 minutes during market hours:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Fetch Data  │───▶│ Run Agents  │───▶│ Aggregate   │───▶│ LLM Decide  │
│ (OHLC +     │    │ (9 agents)  │    │ Signals     │    │ Strategy    │
│ Options)    │    │ Parallel    │    │ Consensus   │    │ BUY/SELL/  │
└─────────────┘    └─────────────┘    └─────────────┘    │ HOLD       │
                                                         └─────────────┘
```

## 📊 Signal Aggregation Logic

### **Consensus Algorithm**
```python
def _aggregate_results(self, agent_results) -> Dict[str, Any]:
    # Count BUY/SELL/HOLD signals
    buy_signals = sum(1 for r in results if r.decision == "BUY")
    sell_signals = sum(1 for r in results if r.decision == "SELL")

    # Calculate consensus direction
    if buy_signals > sell_signals and buy_signals > hold_signals:
        consensus = "BUY"
    elif sell_signals > buy_signals:
        consensus = "SELL"
    else:
        consensus = "HOLD"

    # Signal strength (0.0 to 1.0)
    strength = max(buy_signals, sell_signals, hold_signals) / len(results)

    # Risk assessment
    risk_level = "LOW"
    if any agent shows HIGH risk:
        risk_level = "HIGH"

    # Options strategy recommendation
    strategy = self._recommend_options_strategy(consensus, strength, risk_level, avg_confidence)

    return {
        "consensus_direction": consensus,
        "signal_strength": strength,
        "options_strategy": strategy,
        "risk_assessment": risk_level,
        "agent_breakdown": {...},
        "technical_signals": [...],
        "sentiment_signals": [...],
        "macro_signals": [...]
    }
```

### **Options Strategy Mapping**
```python
def _recommend_options_strategy(direction, strength, risk, confidence):
    if strength < 0.4 or confidence < 0.3:
        return "HOLD - Insufficient conviction"

    if risk == "HIGH":
        return "HOLD - Risk too high for options"

    if direction == "BUY":
        if strength > 0.7 and confidence > 0.7:
            return "BUY_CALL - Strong bullish momentum"
        elif strength > 0.5:
            return "BUY_CALL_SPREAD - Moderate bullish outlook"
        else:
            return "HOLD - Weak bullish signals"

    # Similar logic for SELL direction and neutral strategies
```

## 🚀 Usage Examples

### **Direct Redis Access (Recommended for Performance)**
```python
import redis
from engine_module.api import build_orchestrator
from genai_module.api import build_llm_client
from news_module.api import build_news_service

# Connect to Redis directly
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Build dependencies
llm = build_llm_client(legacy_manager)
news = build_news_service(mongo_collection)

# Build orchestrator with direct Redis access (bypasses API calls)
orchestrator = build_orchestrator(
    llm_client=llm,
    news_service=news,
    redis_client=r,  # Direct Redis access for market data & technicals
    instrument="BANKNIFTY"
)

# Run analysis cycle - data fetched directly from Redis
result = await orchestrator.run_cycle({
    'instrument': 'BANKNIFTY',
    'market_hours': True,
    'cycle_interval': '15min'
})

print(f"Decision: {result.decision}")
print(f"Confidence: {result.confidence:.1%}")
```

### **Legacy API-Based Usage**
```python
from engine_module.api import build_orchestrator
from genai_module.api import build_llm_client
from market_data.api import build_store, build_options_client

# Build dependencies
llm = build_llm_client(legacy_manager)
store = build_store(redis_client)
options = build_options_client(kite, fetcher)

# Build orchestrator with API calls
orchestrator = build_orchestrator(
    llm_client=llm,
    market_store=store,
    options_data=options,
    instrument="BANKNIFTY"
)

# Run analysis cycle
result = await orchestrator.run_cycle({
    'instrument': 'BANKNIFTY',
    'market_hours': True,
    'cycle_interval': '15min'
})
```

### **Agent-Only Analysis**
```python
# Use individual agents for specific analysis
technical_agent = TechnicalAgent()
ohlc_data = [[45000, 45200, 44900, 45150, 10000], ...]  # 15-min bars

result = await technical_agent.analyze({
    "ohlc": ohlc_data,
    "current_price": 45150
})

print(f"Technical Signal: {result.decision}")
print(f"RSI: {result.details.get('rsi')}")
print(f"Trend: {result.details.get('trend_direction')}")
```

## 🧪 Testing & Validation

### **Test Coverage: 22+ Tests**
```bash
# Run all engine module tests
pytest engine_module/tests/ -v

# Test categories:
# - Agent implementations (9 agents)
# - Orchestrator logic
# - API factory functions
# - Contract compliance
# - Integration scenarios
```

### **Agent Testing Example**
```python
# Test technical agent with sample data
def test_technical_agent_basic_buy():
    agent = TechnicalAgent()
    ohlc_data = [
        [45000, 45200, 44900, 45150, 10000],  # Recent bar
        [44900, 45100, 44800, 45050, 12000],  # Previous bars
        # ... more historical data
    ]

    result = await agent.analyze({"ohlc": ohlc_data})

    assert result.decision in ["BUY", "SELL", "HOLD"]
    assert "rsi" in result.details
    assert "trend_direction" in result.details
    assert 0.0 <= result.confidence <= 1.0
```

## 🔧 API Reference

### **Factory Functions**
```python
from engine_module.api import build_orchestrator

# Build complete orchestrator
orchestrator = build_orchestrator(
    llm_client=llm_client,        # GenAI LLM client
    market_store=market_store,    # Data store (Redis/in-memory)
    options_data=options_client,  # Options chain client
    agents=[agent1, agent2, ...] # List of analysis agents
)
```

### **Agent Classes**
```python
from engine_module.agents import (
    TechnicalAgent,      # Price action analysis
    SentimentAgent,      # News/market sentiment
    MacroAgent,         # Economic indicators
    RiskAgent,          # Position risk management
    ExecutionAgent,     # Trade validation
    PortfolioManagerAgent, # Signal aggregation
    # ... and more
)

# All agents implement:
# async def analyze(self, context: Dict[str, Any]) -> AnalysisResult
```

### **Core Contracts**
```python
from engine_module.contracts import AnalysisResult, Agent, Orchestrator

@dataclass
class AnalysisResult:
    decision: str        # "BUY", "SELL", "HOLD", or options strategy
    confidence: float    # 0.0 to 1.0
    details: Dict        # Agent-specific analysis data
```

## 📈 Performance Characteristics

### **15-Minute Cycle Performance**
- **Data Fetch**: ~100ms (OHLC + options data)
- **Agent Analysis**: ~500ms (9 agents in parallel)
- **Signal Aggregation**: ~50ms
- **LLM Decision**: ~2-3 seconds
- **Total Cycle Time**: ~3-4 seconds

### **Scalability**
- Agents run in parallel for optimal performance
- Caching reduces redundant data fetches
- Async design supports concurrent analysis cycles
- Memory efficient with configurable data retention

## 🎯 Integration Points

### **With Data Module**
```python
# Orchestrator fetches data via data_niftybank APIs
market_data = await self.market_store.get_ohlc("BANKNIFTY", "15min", limit=96)
options_data = await self.options_data.fetch_chain("BANKNIFTY")
```

### **With GenAI Module**
```python
# Uses LLM for final decision making
llm_request = LLMRequest(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}]
)
llm_response = await self.llm_client.request(llm_request)
```

### **With User Module**
```python
# Results feed into user module for trade execution
await user_module.execute_trade(user_id, result.decision, quantity, price)
```

### **With UI Shell**
```python
# Analysis results displayed in dashboard
await ui_provider.update_latest_decision(result)
```

## 🚦 Status & Roadmap

### **✅ Current Implementation**
- **Rich Agent Ecosystem**: 20+ agents across technical, sentiment, macro, research, options, portfolio, risk, and execution (see `engine_module/AGENTS.md`)
- **Orchestrator**: Complete 15-minute analysis pipeline
- **LLM Integration**: Sophisticated prompt engineering
- **Signal Aggregation**: Intelligent consensus algorithms
- **Options Strategies**: Comprehensive strategy mapping
- **Multi-Timeframe Analysis**: ✅ Confluence detection across timeframes
- **Regime Detection**: ✅ Market state identification for strategy selection
- **Testing**: 42+ comprehensive unit tests (agents + analysis tools)

### **🎯 Production Ready Features**
- **Async Architecture**: Non-blocking concurrent analysis
- **Error Handling**: Graceful fallbacks and recovery
- **Performance Monitoring**: Execution timing and metrics
- **Configurable Agents**: Easy to add/modify agents
- **Risk-Aware Decisions**: Integrated risk assessment

### **🔮 Future Enhancements**
- **Machine Learning Agents**: Predictive modeling integration
- **Real-time Adaptation**: Dynamic strategy adjustment
- **Backtesting Framework**: Historical performance analysis
- **Advanced Options Strategies**: Complex derivatives positioning (spreads, iron condors)

## 📚 Module Structure

```
engine_module/
├── src/engine_module/
│   ├── contracts.py          # AnalysisResult, Agent, Orchestrator
│   ├── orchestrator_stub.py  # TradingOrchestrator implementation
│   ├── api.py               # Factory functions
│   ├── agents/              # Agent implementations (20+ concrete agents; see AGENTS.md)
│   │   ├── technical_agent.py
│   │   ├── sentiment_agent.py
│   │   ├── macro_agent.py
│   │   ├── risk_agents.py
│   │   ├── execution_agent.py
│   │   └── ... (6 more agents)
│   ├── analysis/            # Analysis tools
│   │   ├── regime_detector.py      # Market regime detection
│   │   └── multi_timeframe.py      # Multi-timeframe confluence analysis
│   └── tools/               # P&L calculator, utilities
├── tests/                   # Comprehensive tests (22+ tests)
└── README.md               # This documentation
```

## 🎉 **The Trading Brain**

The engine module provides the complete **artificial intelligence layer** for algorithmic trading, featuring:

- **Multi-Agent Intelligence**: 9 specialized agents working together
- **LLM-Powered Decisions**: Advanced reasoning for complex strategies
- **15-Minute Analysis Cycles**: Real-time market adaptation
- **Options Trading Focus**: Specialized derivatives strategies
- **Risk-Aware Execution**: Integrated risk management
- **Production Performance**: Optimized for live trading

**Ready to make intelligent trading decisions! 🤖📊**

