# Current Issues & Known Limitations

This document tracks known issues, limitations, and areas that need improvement in the GenAI Trading System.

## Critical Issues

### 1. News Data Not Loaded into AgentState

**Status**: ⚠️ **Not Fixed**

**Description**: 
News items are collected and stored in MongoDB (`market_events` collection), but they are NOT loaded into `AgentState.latest_news` during state initialization. This means agents (Fundamental and Sentiment) receive empty news lists.

**Impact**:
- Fundamental Analysis Agent cannot analyze recent banking sector news
- Sentiment Analysis Agent cannot assess market sentiment from news headlines
- Agents default to "No recent news available" in their analysis

**Location**:
- `trading_orchestration/state_manager.py` - `initialize_state()` method
- Missing: Query MongoDB `market_events` collection for recent news items

**Solution**:
Add method to `StateManager`:
```python
def _load_latest_news(self, limit: int = 20) -> List[Dict[str, Any]]:
    """Load latest news items from MongoDB."""
    # Query market_events collection
    # Filter by event_type: "NEWS"
    # Sort by timestamp descending
    # Return top N items
```

Then call in `initialize_state()`:
```python
latest_news = self._load_latest_news(20)
state = AgentState(..., latest_news=latest_news)
```

**Priority**: High

---

### 2. Macro Economic Data Not Auto-Fetched

**Status**: ⚠️ **Not Fixed**

**Description**:
RBI repo rate, inflation (CPI), and NPA ratio must be manually entered via `MacroCollector.store_rbi_rate()`, `store_inflation_data()`, `store_npa_data()`. There is no automatic service to fetch this data from external APIs.

**Impact**:
- Macro Analysis Agent receives `None` values for RBI rate, inflation, NPA
- Analysis defaults to "Unknown" values
- System cannot react to macro economic changes automatically

**Location**:
- `data/macro_collector.py` - Only has storage methods, no fetching
- Missing: Automatic data collection service

**Solution**:
Create `data/macro_data_fetcher.py`:
- Fetch RBI repo rate from RBI website or financial APIs
- Fetch inflation data from government statistics APIs
- Fetch NPA ratio from RBI banking sector reports
- Run as background service in `TradingService`
- Update data periodically (daily/weekly as appropriate)

**Priority**: Medium

---

### 3. Buy/Sell Signal Thresholds Too High

**Status**: ⚠️ **Not Fixed**

**Description**:
Portfolio Manager requires `bullish_score > 0.65 AND bearish_score < 0.35` to generate BUY signal (and vice versa for SELL). Current scores are typically around 0.27/0.24, resulting in HOLD signals.

**Impact**:
- System rarely generates BUY/SELL signals
- Most decisions are HOLD
- May miss trading opportunities

**Location**:
- `agents/portfolio_manager.py` - Lines 88-98

**Current Logic**:
```python
if bullish_score > 0.65 and bearish_score < 0.35:
    signal = SignalType.BUY
elif bearish_score > 0.65 and bullish_score < 0.35:
    signal = SignalType.SELL
```

**Solution**:
Implement adaptive thresholds:
- Lower thresholds (e.g., 0.55/0.45) for normal conditions
- Higher thresholds (0.70/0.30) for high volatility
- Tiered signals: STRONG_BUY, BUY, WEAK_BUY, HOLD, WEAK_SELL, SELL, STRONG_SELL

**Priority**: Medium

---

### 4. Agent Reasoning Needs Improvement

**Status**: ⚠️ **Not Fixed**

**Description**:
Agents use LLMs but prompts lack structured reasoning chains. Analysis could be more thorough with step-by-step reasoning.

**Impact**:
- Agent outputs may lack depth
- Reasoning not always clear
- Confidence scores may not reflect true confidence

**Location**:
- All agent files in `agents/`
- Prompt templates in `config/prompts/`

**Solution**:
Enhance prompts with chain-of-thought reasoning:
1. Identify key data points
2. Analyze relationships and patterns
3. Assess probabilities and confidence
4. Generate structured output with justification

**Priority**: Low (functionality works, but can be improved)

---

## Minor Issues

### 5. Finnhub Code Still Present

**Status**: ⚠️ **Needs Cleanup**

**Description**:
Finnhub integration code still exists in codebase but is no longer used (system uses Zerodha only).

**Files**:
- `data/finnhub_feed.py`
- References in `services/trading_service.py`
- References in `monitoring/dashboard.py`
- References in `config/settings.py`
- Scripts: `scripts/check_finnhub_symbols.py`, `scripts/test_finnhub_websocket.py`, etc.

**Solution**: Remove all Finnhub code and references.

**Priority**: Low (doesn't affect functionality)

---

### 6. News Collection Not Integrated into Trading Service

**Status**: ⚠️ **Not Fixed**

**Description**:
`NewsCollector` exists but is not started automatically in `TradingService`. Must be started separately.

**Location**:
- `services/trading_service.py` - Missing NewsCollector initialization

**Solution**:
Add NewsCollector to TradingService initialization:
```python
if settings.news_api_key:
    self.news_collector = NewsCollector(self.market_memory)
    asyncio.create_task(self.news_collector.run_continuous())
```

**Priority**: Low (can be started manually)

---

## Data Quality Issues

### 7. Sentiment Calculation Too Simple

**Status**: ⚠️ **Enhancement Needed**

**Description**:
Sentiment calculation in `NewsCollector._calculate_sentiment()` uses simple keyword matching. Could be improved with LLM-based sentiment analysis.

**Location**:
- `data/news_collector.py` - `_calculate_sentiment()` method

**Priority**: Low (works but could be better)

---

## Summary

| Issue | Priority | Status | Effort |
|-------|----------|--------|--------|
| News data not loaded | High | Not Fixed | Medium |
| Macro data not auto-fetched | Medium | Not Fixed | High |
| Signal thresholds too high | Medium | Not Fixed | Low |
| Agent reasoning improvement | Low | Not Fixed | Medium |
| Finnhub code cleanup | Low | Not Fixed | Low |
| News collector integration | Low | Not Fixed | Low |
| Sentiment calculation | Low | Not Fixed | Medium |

## Recommended Fix Order

1. **Fix news data loading** (High priority, medium effort)
2. **Lower signal thresholds** (Medium priority, low effort)
3. **Create macro data fetcher** (Medium priority, high effort)
4. **Remove Finnhub code** (Low priority, low effort)
5. **Integrate news collector** (Low priority, low effort)
6. **Improve agent reasoning** (Low priority, medium effort)
7. **Enhance sentiment calculation** (Low priority, medium effort)

