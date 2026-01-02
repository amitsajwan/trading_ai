# Current Issues & Known Limitations

This document tracks known issues, limitations, and areas that need improvement.

## Critical Issues

### 1. News Data Not Loaded into AgentState

**Status**: ⚠️ **Not Fixed**

**Description**: 
News items are collected and stored in MongoDB (`market_events` collection), but they are NOT loaded into `AgentState.latest_news` during state initialization.

**Impact**:
- Fundamental and Sentiment agents receive empty news lists
- Agents default to "No recent news available" in their analysis

**Solution**:
Add method to `StateManager` to load news from MongoDB:
```python
def _load_latest_news(self, limit: int = 20) -> List[Dict[str, Any]]:
    """Load latest news items from MongoDB."""
    # Query market_events collection
    # Filter by event_type: "NEWS"
    # Return top N items sorted by timestamp
```

**Priority**: High

---

### 2. Macro Economic Data Not Auto-Fetched

**Status**: ⚠️ **Not Fixed**

**Description**:
Macro data (interest rates, inflation) must be manually entered. No automatic fetching service exists.

**Impact**:
- Macro Analysis Agent receives `None` values
- Analysis defaults to "Unknown" values

**Solution**:
Create automatic data collection service that fetches:
- For stocks: RBI rates, CPI, NPA ratio from financial APIs
- For crypto: Fed rates, DXY, BTC dominance from crypto APIs

**Priority**: Medium

---

### 3. Buy/Sell Signal Thresholds Too High

**Status**: ⚠️ **Not Fixed**

**Description**:
Portfolio Manager requires `bullish_score > 0.65 AND bearish_score < 0.35` to generate BUY signal. Current scores typically around 0.27/0.24 result in mostly HOLD signals.

**Impact**:
- System rarely generates BUY/SELL signals
- Most decisions are HOLD
- May miss trading opportunities

**Location**: `agents/portfolio_manager.py`

**Solution**:
Implement adaptive thresholds:
- Lower thresholds (0.55/0.45) for normal conditions
- Higher thresholds (0.70/0.30) for high volatility

**Priority**: Medium

---

## Minor Issues

### 4. News Collection Not Integrated into Trading Service

**Status**: ⚠️ **Not Fixed**

**Description**:
`NewsCollector` exists but is not started automatically in `TradingService`. Must be started separately.

**Solution**:
Add NewsCollector to TradingService initialization when `NEWS_API_KEY` is configured.

**Priority**: Low

---

### 5. Sentiment Calculation Too Simple

**Status**: ⚠️ **Enhancement Needed**

**Description**:
Sentiment calculation uses simple keyword matching. Could be improved with LLM-based sentiment analysis.

**Location**: `data/news_collector.py`

**Priority**: Low

---

## Resolved Issues

### ✅ Prompts Hardcoded for Bank Nifty

**Status**: ✅ **Fixed**

**Description**: All agent prompts were hardcoded for "Bank Nifty" trading.

**Resolution**: Prompts now use `{instrument_name}` placeholder and are dynamically populated from settings.

---

### ✅ Missing .env Configuration

**Status**: ✅ **Fixed**

**Description**: No default .env file existed.

**Resolution**: Created proper .env file with BTC configuration. Added diagnostic script.

---

### ✅ Finnhub Code Cleanup

**Status**: ✅ **Fixed**

**Description**: Finnhub integration code was present but unused.

**Resolution**: All Finnhub code has been removed from the codebase.

---

## Summary

| Issue | Priority | Status | Effort |
|-------|----------|--------|--------|
| News data not loaded | High | Not Fixed | Medium |
| Macro data not auto-fetched | Medium | Not Fixed | High |
| Signal thresholds too high | Medium | Not Fixed | Low |
| News collector integration | Low | Not Fixed | Low |
| Sentiment calculation | Low | Not Fixed | Medium |

## Recommended Fix Order

1. **Lower signal thresholds** (Medium priority, low effort)
2. **Fix news data loading** (High priority, medium effort)
3. **Integrate news collector** (Low priority, low effort)
4. **Create macro data fetcher** (Medium priority, high effort)
5. **Enhance sentiment calculation** (Low priority, medium effort)
