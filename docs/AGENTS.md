# Agent Documentation

This document provides detailed documentation for each agent in the GenAI Trading System.

## Agent Architecture

All agents inherit from `BaseAgent` (`agents/base_agent.py`) which provides:
- LLM client initialization and management
- Structured output parsing
- State update utilities
- Error handling

Agents process `AgentState` objects, update them with their analysis, and pass them to the next stage in the pipeline.

## Agent Pipeline

```
START
  │
  ├─► Technical Analysis Agent
  ├─► Fundamental Analysis Agent
  ├─► Sentiment Analysis Agent
  └─► Macro Analysis Agent
       │
       ├─► Bull Researcher Agent
       └─► Bear Researcher Agent
            │
            ├─► Aggressive Risk Agent
            ├─► Conservative Risk Agent
            └─► Neutral Risk Agent
                 │
                 └─► Portfolio Manager Agent
                      │
                      └─► Execution Agent
                           │
                           └─► END
```

## Analysis Agents

### Technical Analysis Agent

**File**: `agents/technical_agent.py`

**Purpose**: Analyze price action, technical indicators, and chart patterns.

**Input Data**:
- OHLC candles (1min, 5min, 15min, hourly, daily)
- Current price

**Processing**:
1. Calculates technical indicators programmatically:
   - RSI (Relative Strength Index)
   - MACD (Moving Average Convergence Divergence)
   - ATR (Average True Range)
   - Support/Resistance levels
   - Trend direction and strength
2. Uses LLM for:
   - Pattern recognition (head & shoulders, triangles, etc.)
   - Synthesis of indicator signals
   - Confidence assessment

**Output** (`state.technical_analysis`):
```python
{
    "rsi": float,                    # RSI value (0-100)
    "rsi_status": str,                # "OVERBOUGHT" | "OVERSOLD" | "NEUTRAL"
    "macd": float,                    # MACD line value
    "macd_status": str,               # "BULLISH" | "BEARISH" | "NEUTRAL"
    "atr": float,                     # ATR value
    "trend_direction": str,           # "UP" | "DOWN" | "SIDEWAYS"
    "trend_strength": float,          # 0-100
    "support_levels": List[float],    # Support price levels
    "resistance_levels": List[float], # Resistance price levels
    "pattern": str,                    # Detected chart pattern
    "confidence_score": float         # 0-1
}
```

**Key Features**:
- Programmatic calculation ensures accuracy
- LLM used only for pattern recognition and synthesis
- Multiple timeframe analysis

---

### Fundamental Analysis Agent

**File**: `agents/fundamental_agent.py`

**Purpose**: Analyze banking sector fundamentals, RBI policy impact, and credit quality trends.

**Input Data**:
- Latest news articles (banking sector, RBI)
- RBI repo rate
- NPA ratio

**Processing**:
1. Analyzes news headlines for sector trends
2. Assesses RBI policy impact on banking sector
3. Evaluates credit quality trends from NPA data
4. Calculates bullish/bearish probabilities

**Output** (`state.fundamental_analysis`):
```python
{
    "sector_strength": str,           # "STRONG" | "MODERATE" | "WEAK"
    "credit_quality_trend": str,       # "IMPROVING" | "STABLE" | "DETERIORATING"
    "rbi_policy_impact": str,         # "POSITIVE" | "NEUTRAL" | "NEGATIVE"
    "bullish_probability": float,     # 0-1
    "bearish_probability": float,     # 0-1
    "key_risk_factors": List[str],    # Key risks identified
    "key_catalysts": List[str],       # Key catalysts identified
    "confidence_score": float         # 0-1
}
```

**Current Issue**: News items not loaded into state (see [CURRENT_ISSUES.md](CURRENT_ISSUES.md))

---

### Sentiment Analysis Agent

**File**: `agents/sentiment_agent.py`

**Purpose**: Analyze market sentiment from news, detect retail vs institutional divergence.

**Input Data**:
- Latest news articles
- Aggregate sentiment score

**Processing**:
1. Analyzes news headlines for sentiment
2. Distinguishes retail vs institutional sentiment
3. Detects sentiment divergence
4. Assesses options flow signals (if available)

**Output** (`state.sentiment_analysis`):
```python
{
    "retail_sentiment": float,        # -1 to +1
    "institutional_sentiment": float, # -1 to +1
    "sentiment_divergence": str,      # "NONE" | "RETAIL_BULLISH" | "INSTITUTIONAL_BULLISH" | "EXTREME_FEAR" | "EXTREME_GREED"
    "options_flow_signal": str,       # "BULLISH" | "BEARISH" | "NEUTRAL"
    "fear_greed_index": float,        # 0-100
    "confidence_score": float         # 0-1
}
```

**Current Issue**: News items not loaded into state (see [CURRENT_ISSUES.md](CURRENT_ISSUES.md))

---

### Macro Analysis Agent

**File**: `agents/macro_agent.py`

**Purpose**: Analyze macro economic conditions, RBI policy cycle, and banking sector health.

**Input Data**:
- RBI repo rate
- Inflation rate (CPI)
- NPA ratio

**Processing**:
1. Determines macro regime (GROWTH/INFLATION/STRESS/MIXED)
2. Assesses RBI policy cycle (TIGHTENING/EASING/NEUTRAL)
3. Calculates rate cut/hike probabilities
4. Evaluates NPA concern levels
5. Calculates sector headwind/tailwind score

**Output** (`state.macro_analysis`):
```python
{
    "macro_regime": str,              # "GROWTH" | "INFLATION" | "STRESS" | "MIXED"
    "rbi_cycle": str,                 # "TIGHTENING" | "EASING" | "NEUTRAL"
    "rate_cut_probability": float,    # 0-1
    "rate_hike_probability": float,   # 0-1
    "npa_concern_level": str,        # "LOW" | "MEDIUM" | "HIGH"
    "liquidity_condition": str,       # "EASY" | "NORMAL" | "TIGHT"
    "sector_headwind_score": float,   # -1 to +1 (negative = headwind, positive = tailwind)
    "confidence_score": float         # 0-1
}
```

**Current Issue**: Macro data not auto-fetched (see [CURRENT_ISSUES.md](CURRENT_ISSUES.md))

---

## Research Agents

### Bull Researcher Agent

**File**: `agents/bull_researcher.py`

**Purpose**: Construct bullish thesis and stress-test bear case.

**Input Data**: All analysis agent outputs

**Processing**:
1. Synthesizes bullish arguments from all agents
2. Constructs coherent bullish thesis
3. Stress-tests against bear case
4. Assigns conviction score

**Output** (`state.bull_thesis`, `state.bull_confidence`):
```python
{
    "thesis": str,                    # Bullish thesis narrative
    "conviction_score": float,        # 0-1
    "upside_probability": float,     # 0-1
    "key_drivers": List[str]         # Key bullish drivers
}
```

---

### Bear Researcher Agent

**File**: `agents/bear_researcher.py`

**Purpose**: Construct bearish thesis and stress-test bull case.

**Input Data**: All analysis agent outputs

**Processing**:
1. Synthesizes bearish arguments from all agents
2. Constructs coherent bearish thesis
3. Stress-tests against bull case
4. Assigns conviction score

**Output** (`state.bear_thesis`, `state.bear_confidence`):
```python
{
    "thesis": str,                    # Bearish thesis narrative
    "conviction_score": float,        # 0-1
    "downside_probability": float,    # 0-1
    "key_drivers": List[str]         # Key bearish drivers
}
```

---

## Risk Management Agents

### Aggressive Risk Agent

**File**: `agents/risk_agents.py` - `AggressiveRiskAgent`

**Purpose**: Calculate position sizing for aggressive risk tolerance.

**Input Data**:
- Current price
- Volatility (ATR)
- Account capital
- Current positions

**Processing**:
1. Calculates position size (higher leverage)
2. Sets wider stop-loss (higher risk tolerance)
3. Recommends higher leverage

**Output** (`state.aggressive_risk_recommendation`):
```python
{
    "position_size": int,             # Number of lots/units
    "stop_loss_pct": float,          # Stop-loss percentage
    "stop_loss_price": float,        # Stop-loss price level
    "leverage": float,               # Recommended leverage
    "risk_amount": float,            # Risk amount in currency
    "confidence_score": float        # 0-1
}
```

---

### Conservative Risk Agent

**File**: `agents/risk_agents.py` - `ConservativeRiskAgent`

**Purpose**: Calculate position sizing for conservative risk tolerance.

**Processing**: Similar to Aggressive but with:
- Lower position size
- Tighter stop-loss
- Lower/no leverage

**Output** (`state.conservative_risk_recommendation`): Same structure as Aggressive

---

### Neutral Risk Agent

**File**: `agents/risk_agents.py` - `NeutralRiskAgent`

**Purpose**: Calculate position sizing for neutral risk tolerance (default).

**Processing**: Balanced approach between aggressive and conservative.

**Output** (`state.neutral_risk_recommendation`): Same structure as Aggressive

---

## Decision Agents

### Portfolio Manager Agent

**File**: `agents/portfolio_manager.py`

**Purpose**: Synthesize all agent outputs and make final trading decision.

**Input Data**: All agent outputs

**Processing**:
1. Calculates weighted bullish/bearish scores:
   - Technical: 30% weight
   - Fundamental: 25% weight
   - Sentiment: 15% weight
   - Macro: 15% weight
   - Bull/Bear debate: 15% weight
2. Applies decision logic (thresholds)
3. Selects risk recommendation (default: neutral)
4. Generates final signal

**Output** (`state.final_signal`, `state.position_size`, etc.):
```python
{
    "signal": str,                   # "BUY" | "SELL" | "HOLD"
    "bullish_score": float,          # 0-1
    "bearish_score": float,          # 0-1
    "position_size": int,            # Number of lots/units
    "entry_price": float,            # Entry price
    "stop_loss": float,              # Stop-loss price
    "take_profit": float,            # Take-profit price
    "risk_recommendation_used": str  # "neutral" | "aggressive" | "conservative"
}
```

**Current Issue**: Thresholds too high (see [CURRENT_ISSUES.md](CURRENT_ISSUES.md))

---

### Execution Agent

**File**: `agents/execution_agent.py`

**Purpose**: Execute trades via Zerodha Kite API.

**Input Data**: Final signal from Portfolio Manager

**Processing**:
1. Validates signal (BUY/SELL only)
2. Places order via Zerodha Kite API (or paper trading)
3. Tracks fill status
4. Logs trade to MongoDB

**Output** (`state.order_id`, `state.filled_price`, etc.):
```python
{
    "order_id": str,                 # Zerodha order ID
    "filled_price": float,           # Fill price
    "filled_quantity": int,         # Filled quantity
    "execution_timestamp": datetime  # Execution time
}
```

**Modes**:
- Paper Trading: Simulates orders (default)
- Live Trading: Real orders via Zerodha API

---

## Learning Agent

**File**: `agents/learning_agent.py`

**Purpose**: Analyze completed trades and improve system performance.

**Processing**:
1. Analyzes trade outcomes
2. Identifies which agents were most predictive
3. Generates improvement suggestions
4. Updates prompts dynamically (future)

**Status**: Implemented but not yet integrated into main loop

---

## Agent State Updates

Each agent updates `AgentState` with:
1. **Analysis Output**: Stored in state (e.g., `state.technical_analysis`)
2. **Explanation**: Added to `state.agent_explanations` list
3. **Confidence**: Included in output dictionary

## Error Handling

All agents include error handling:
- Catches exceptions
- Returns default/neutral outputs
- Logs errors
- Continues pipeline execution

## Adding New Agents

To add a new agent:

1. Create agent class inheriting from `BaseAgent`
2. Implement `process(state: AgentState) -> AgentState` method
3. Add to `TradingGraph` in `trading_orchestration/trading_graph.py`
4. Add system prompt in `config/prompts/`
5. Update `AgentState` model if needed

Example:
```python
class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__("my_agent", "Your system prompt here")
    
    def process(self, state: AgentState) -> AgentState:
        # Your logic here
        analysis = self._call_llm_structured(prompt, response_format)
        self.update_state(state, analysis, "Explanation")
        return state
```

