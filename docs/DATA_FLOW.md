# Data Flow Documentation

This document describes the complete data flow through the GenAI Trading System, from market data ingestion to trade execution.

## Overview

The system follows a multi-stage data pipeline:

```
Market Data Sources → Data Ingestion → Storage (Redis/MongoDB) → State Manager → Agents → Portfolio Manager → Execution
```

## Data Sources

### 1. Market Data (Zerodha)

**Source**: Zerodha Kite Connect WebSocket API
**Component**: `data/ingestion_service.py` - `DataIngestionService`
**Data Type**: Real-time ticks, OHLC candles
**Update Frequency**: Real-time (WebSocket stream)

**Flow**:
1. WebSocket connection established to Zerodha Kite
2. Subscribe to Bank Nifty instrument token
3. Receive tick data in real-time
4. Aggregate ticks into 1-minute OHLC candles
5. Store in Redis (hot data, 24-hour TTL)
6. Persist to MongoDB (historical data)

**Storage**:
- **Redis**: `tick:BANKNIFTY:{timestamp}`, `ohlc:BANKNIFTY:{timeframe}:{timestamp}`, `price:BANKNIFTY:latest`
- **MongoDB**: `ohlc_history` collection

### 2. News Data

**Source**: NewsAPI (configurable)
**Component**: `data/news_collector.py` - `NewsCollector`
**Data Type**: News articles with sentiment scores
**Update Frequency**: Every 5 minutes (configurable)

**Flow**:
1. Fetch news articles from NewsAPI (query: "Bank Nifty OR banking sector OR RBI")
2. Calculate sentiment score for each article (keyword-based)
3. Store aggregate sentiment in Redis
4. Store individual articles in MongoDB

**Storage**:
- **Redis**: `sentiment:news:{timestamp}` (aggregate score)
- **MongoDB**: `market_events` collection (individual articles with `event_type: "NEWS"`)

**Current Issue**: News items are stored but NOT loaded into `AgentState.latest_news` during state initialization. See [CURRENT_ISSUES.md](CURRENT_ISSUES.md).

### 3. Macro Economic Data

**Source**: Manual entry or external APIs (not yet automated)
**Component**: `data/macro_collector.py` - `MacroCollector`
**Data Type**: RBI repo rate, inflation (CPI), NPA ratio
**Update Frequency**: Manual (when data is available)

**Flow**:
1. Data stored via `MacroCollector.store_rbi_rate()`, `store_inflation_data()`, `store_npa_data()`
2. Stored in MongoDB `strategy_parameters` collection
3. Retrieved via `get_latest_macro_context()`
4. Loaded into `AgentState` during initialization

**Storage**:
- **MongoDB**: `strategy_parameters` collection (`strategy_name: "macro_context"`)

**Current Issue**: No automatic fetching service. Data must be manually entered. See [CURRENT_ISSUES.md](CURRENT_ISSUES.md).

## Data Processing Pipeline

### Stage 1: State Initialization

**Component**: `trading_orchestration/state_manager.py` - `StateManager`

**Process**:
1. `initialize_state()` called at start of each trading cycle
2. Retrieves data from storage:
   - Current price from Redis (`price:BANKNIFTY:latest`)
   - OHLC data from Redis (last 60 1-min, 100 5-min, etc.)
   - Sentiment score from Redis (`sentiment:news:latest`)
   - Macro context from MongoDB (`strategy_parameters`)
3. Creates `AgentState` object with all data
4. **Missing**: News items not loaded (should query MongoDB `market_events`)

### Stage 2: Agent Processing

**Component**: `trading_orchestration/trading_graph.py` - `TradingGraph`

**Process**:
1. State passed to agents in parallel:
   - Technical Analysis Agent (uses OHLC data)
   - Fundamental Analysis Agent (uses news + macro data)
   - Sentiment Analysis Agent (uses news + sentiment score)
   - Macro Analysis Agent (uses macro data: RBI rate, inflation, NPA)
2. Each agent processes and updates state
3. Bull/Bear researchers synthesize agent outputs
4. Risk agents calculate position sizing
5. Portfolio Manager makes final decision

### Stage 3: Execution

**Component**: `agents/execution_agent.py` - `ExecutionAgent`

**Process**:
1. Receives final signal from Portfolio Manager
2. Places order via Zerodha Kite API (or paper trading)
3. Logs trade to MongoDB `trades` collection
4. Updates position monitoring

## Data Storage Architecture

### Redis (Hot Data)

**Purpose**: Fast access to recent data (24-hour window)
**TTL**: 24 hours for ticks/OHLC, 5 minutes for latest price

**Keys**:
- `tick:{instrument}:{timestamp}` - Individual ticks
- `ohlc:{instrument}:{timeframe}:{timestamp}` - OHLC candles
- `ohlc_sorted:{instrument}:{timeframe}` - Sorted set for time-series queries
- `price:{instrument}:latest` - Latest price (5-min TTL)
- `sentiment:{source}:{timestamp}` - Sentiment scores

### MongoDB (Persistent Storage)

**Collections**:
- `ohlc_history` - Historical OHLC data
- `market_events` - News articles and macro events
- `strategy_parameters` - Macro context (RBI rate, inflation, NPA)
- `trades` - Executed trades with full audit trail
- `agent_decisions` - Agent analysis outputs

## Data Flow Diagram

```
┌─────────────────┐
│  Zerodha Kite   │
│    WebSocket    │
└────────┬────────┘
         │ Real-time ticks
         ▼
┌─────────────────┐
│ DataIngestion   │
│    Service      │
└────────┬────────┘
         │
         ├──► Redis (hot data, 24h TTL)
         │
         └──► MongoDB (persistent)
         
┌─────────────────┐
│  NewsAPI        │
└────────┬────────┘
         │ Every 5 min
         ▼
┌─────────────────┐
│ NewsCollector   │
└────────┬────────┘
         │
         ├──► Redis (sentiment score)
         │
         └──► MongoDB (articles)

┌─────────────────┐
│  StateManager   │
└────────┬────────┘
         │ Loads data
         ▼
┌─────────────────┐
│   AgentState    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TradingGraph   │
│  (All Agents)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Portfolio Mgr   │
│  (Final Signal) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Execution Agent │
└────────┬────────┘
         │
         └──► MongoDB (trade log)
```

## Data Dependencies

### Agent Data Requirements

| Agent | Required Data | Source | Status |
|-------|--------------|--------|--------|
| Technical | OHLC candles (1min, 5min, 15min, hourly, daily) | Redis | ✅ Working |
| Fundamental | News articles, RBI rate, NPA ratio | MongoDB | ⚠️ News not loaded |
| Sentiment | News articles, aggregate sentiment | Redis/MongoDB | ⚠️ News not loaded |
| Macro | RBI rate, inflation, NPA ratio | MongoDB | ⚠️ Not auto-fetched |
| Bull/Bear | All agent outputs | AgentState | ✅ Working |
| Risk | Current price, volatility (ATR) | AgentState | ✅ Working |
| Portfolio Manager | All agent outputs | AgentState | ✅ Working |

## Current Data Gaps

1. **News Data Not Loaded**: News items stored in MongoDB but not loaded into `AgentState.latest_news`
2. **Macro Data Manual**: RBI rate, inflation, NPA must be manually entered
3. **No Auto-Refresh**: Macro data doesn't auto-update from external sources

See [CURRENT_ISSUES.md](CURRENT_ISSUES.md) for details and solutions.

## Performance Considerations

- **Redis**: Sub-millisecond access for hot data
- **MongoDB**: Persistent storage, queryable for historical analysis
- **Data Freshness**: Latest price updated every tick, OHLC aggregated every minute
- **Storage Efficiency**: Redis TTL prevents unbounded growth, MongoDB indexed for fast queries

