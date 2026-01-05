# Agent System Documentation

## Overview

The GenAI Trading System uses a multi-agent architecture powered by LangGraph orchestration. Each agent specializes in a specific aspect of market analysis, providing diverse perspectives that are synthesized by the Portfolio Manager for final trading decisions.

## Agent Architecture

### Core Design Principles

1. **Specialization**: Each agent focuses on one aspect of analysis
2. **Independence**: Agents operate without knowledge of others' outputs
3. **Diversity**: Multiple methodologies reduce single-point failures
4. **Synthesization**: Portfolio Manager combines all inputs for final decision

### Agent Communication Flow

```
Market Data → Individual Agents → Portfolio Manager → Risk Assessment → Execution
     ↓             ↓                     ↓              ↓            ↓
   Redis      Agent Decisions      Final Decision   Validation   API Orders
     ↓             ↓                     ↓              ↓            ↓
 MongoDB      MongoDB               MongoDB        Memory       Broker API
```

## Individual Agents

### 1. Technical Agent

**Role**: Chart analysis and technical indicators

**Input Data**:
- OHLC data (multiple timeframes: 1m, 5m, 15m, 1h, daily)
- Volume data and order flow
- Key levels (support/resistance)
- Trend indicators (moving averages, RSI, MACD)

**Analysis Framework**:
- **Trend Analysis**: Primary trend direction and strength
- **Momentum Indicators**: RSI, MACD, Stochastic
- **Volume Analysis**: Volume confirmation, order flow imbalance
- **Key Levels**: Support/resistance identification
- **Pattern Recognition**: Chart patterns and breakouts

**Output**:
```json
{
  "signal": "BUY|SELL|HOLD",
  "confidence": 0.75,
  "reasoning": "Strong uptrend with RSI divergence",
  "key_levels": [45000, 45500, 46000],
  "indicators": {
    "rsi": 65,
    "macd": "bullish",
    "volume": "confirming"
  }
}
```

### 2. Fundamental Agent

**Role**: Asset valuation and business analysis

**Input Data**:
- Company financials (revenue, earnings, debt)
- Industry analysis and competitive position
- Economic indicators and sector trends
- News and event impact analysis

**Analysis Framework**:
- **Valuation Metrics**: P/E, P/B, EV/EBITDA ratios
- **Growth Analysis**: Revenue/earnings growth trends
- **Balance Sheet**: Debt levels, cash position, assets
- **Competitive Position**: Market share, moat analysis
- **Macro Impact**: Interest rates, inflation effects

**Output**:
```json
{
  "signal": "BUY|SELL|HOLD",
  "confidence": 0.70,
  "valuation": {
    "pe_ratio": 18.5,
    "growth_rate": "12%",
    "fair_value": 48000
  },
  "reasoning": "Strong balance sheet with growth potential"
}
```

### 3. Sentiment Agent

**Role**: Market psychology and news sentiment

**Input Data**:
- Financial news from multiple sources
- Social media sentiment (if available)
- Options flow and positioning data
- Put/call ratios and volatility indicators

**Analysis Framework**:
- **News Sentiment**: Positive/negative/neutral classification
- **Impact Assessment**: High/medium/low impact categorization
- **Trend Analysis**: Sentiment shifts over time
- **Contrarian Signals**: Extreme sentiment as reversal indicators

**Output**:
```json
{
  "signal": "BUY|SELL|HOLD",
  "confidence": 0.65,
  "sentiment_score": 0.75,
  "key_news": [
    "Positive earnings beat",
    "Industry tailwinds"
  ],
  "reasoning": "Bullish sentiment with positive news flow"
}
```

### 4. Macro Agent

**Role**: Economic context and systemic risk

**Input Data**:
- Interest rates and monetary policy
- Inflation data and CPI readings
- GDP growth and employment figures
- Geopolitical events and risk factors

**Analysis Framework**:
- **Economic Cycle**: Expansion/contraction phases
- **Monetary Policy**: Fed/ECB stance and implications
- **Inflation Analysis**: Wage growth, commodity prices
- **Risk Assessment**: Systemic risk levels

**Output**:
```json
{
  "signal": "BUY|SELL|HOLD",
  "confidence": 0.60,
  "macro_regime": "bullish",
  "key_factors": [
    "Easing monetary policy",
    "GDP growth acceleration"
  ],
  "reasoning": "Favorable macro environment for risk assets"
}
```

### 5. Bull Researcher Agent

**Role**: Construct optimistic investment thesis

**Methodology**:
- Identifies strongest bullish arguments
- Quantifies upside potential and catalysts
- Assesses probability of positive outcomes
- Provides specific price targets and timelines

**Output**:
```json
{
  "bull_thesis": "Strong growth in AI sector driving BTC adoption",
  "upside_targets": [50000, 55000, 60000],
  "catalysts": ["Institutional adoption", "ETF approvals"],
  "probability": 0.65,
  "timeframe": "3-6 months"
}
```

### 6. Bear Researcher Agent

**Role**: Construct pessimistic investment thesis

**Methodology**:
- Identifies strongest bearish arguments
- Quantifies downside risk and headwinds
- Assesses probability of negative outcomes
- Provides specific downside targets

**Output**:
```json
{
  "bear_thesis": "Regulatory crackdown and institutional selling",
  "downside_targets": [35000, 30000, 25000],
  "risks": ["SEC regulations", "Mining capitulation"],
  "probability": 0.35,
  "timeframe": "1-3 months"
}
```

### 7. Risk Management Agent

**Role**: Multi-perspective risk assessment

**Risk Dimensions**:
- **Market Risk**: Volatility, correlation, beta
- **Liquidity Risk**: Trading volume, slippage potential
- **Position Risk**: Size, concentration, leverage
- **Timing Risk**: Entry/exit timing, holding periods

**Output**:
```json
{
  "risk_score": 0.25,
  "max_position_size": "2% of portfolio",
  "stop_loss": 42000,
  "risk_factors": ["High volatility", "Low liquidity"],
  "recommendations": ["Reduce position size", "Use trailing stop"]
}
```

### 8. Portfolio Manager Agent

**Role**: Synthesize all inputs for final decision

**Decision Framework**:
1. **Signal Aggregation**: Weighted average of agent signals
2. **Confidence Synthesis**: Combined confidence scoring
3. **Risk Integration**: Risk-adjusted position sizing
4. **Scenario Analysis**: Base/bull/bear case projections

**Output**:
```json
{
  "final_signal": "BUY",
  "confidence": 0.72,
  "position_size": "1.5% of portfolio",
  "entry_price": "market",
  "stop_loss": 42000,
  "take_profit": 50000,
  "reasoning": "Strong technical + fundamental alignment",
  "scenario_paths": {
    "base_case": { "target": 47000, "probability": 0.50 },
    "bull_case": { "target": 52000, "probability": 0.30 },
    "bear_case": { "target": 40000, "probability": 0.20 }
  }
}
```

### 9. Execution Agent

**Role**: Order placement and management

**Responsibilities**:
- Translate decisions into specific orders
- Handle order routing and execution
- Monitor fills and slippage
- Manage position lifecycle

### 10. Learning Agent

**Role**: Performance analysis and system improvement

**Functions**:
- **Trade Analysis**: Win/loss ratio, P&L attribution
- **Prompt Refinement**: Update agent prompts based on performance
- **Strategy Evolution**: Identify successful patterns
- **Risk Learning**: Update risk parameters from experience

## Agent Configuration

### LLM Provider Selection

Agents use a weighted selection system for LLM providers:

```python
# Provider weights based on performance
PROVIDER_WEIGHTS = {
    "groq": 0.4,      # Fast, cost-effective
    "openai": 0.3,    # High quality
    "google": 0.2,    # Good for analysis
    "ollama": 0.1     # Local fallback
}
```

### Concurrency Management

- **Max Concurrent**: 2 agents running simultaneously
- **Soft Throttle**: 0.8 factor to prevent API rate limits
- **Fallback**: Automatic provider switching on failures

### Response Validation

- **JSON Completeness**: Ensures complete structured outputs
- **Field Validation**: Required fields present and valid
- **Retry Logic**: Up to 2 retries on failures
- **Timeout Handling**: 30-second timeouts with fallbacks

## Performance Monitoring

### Agent Metrics

- **Response Time**: Average time per agent analysis
- **Success Rate**: Percentage of valid responses
- **Signal Accuracy**: Historical performance tracking
- **Confidence Calibration**: Actual vs. predicted outcomes

### System Health

- **LLM Availability**: Provider status monitoring
- **API Limits**: Rate limit tracking and management
- **Error Rates**: Per-agent failure monitoring
- **Performance Trends**: Accuracy improvements over time

## Customization

### Adding New Agents

1. **Create Agent Class**:
```python
class CustomAgent(BaseAgent):
    def __init__(self, market_memory, llm_provider):
        super().__init__(market_memory, llm_provider)
        self.name = "custom_agent"

    async def process(self, context):
        # Custom analysis logic
        return {
            "signal": "BUY",
            "confidence": 0.75,
            "reasoning": "Custom analysis"
        }
```

2. **Add to LangGraph**:
```python
# In trading_graph.py
custom_agent = CustomAgent(market_memory, llm_provider)
# Add to graph nodes and edges
```

3. **Configure Prompts**:
```python
# In config/prompts/custom_agent.txt
# Custom agent prompt template
```

### Modifying Agent Behavior

- **Prompt Engineering**: Update prompt templates in `config/prompts/`
- **Weight Adjustment**: Modify signal weights in Portfolio Manager
- **Risk Parameters**: Update risk thresholds in Risk Manager
- **Confidence Thresholds**: Adjust decision confidence requirements