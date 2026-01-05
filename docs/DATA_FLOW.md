# Data Flow and Signal Pipeline

## Overview

The GenAI Trading System processes real-time market data through a multi-stage pipeline that transforms raw ticks into actionable trading signals. This document outlines the complete data flow from market ingestion to order execution.

## Data Sources

### Primary Data Feeds

| Instrument | Data Source | Protocol | Update Frequency | Data Types |
|------------|-------------|----------|------------------|------------|
| **Bitcoin** | Binance WebSocket | WSS | Real-time | Trades, Order Book, Tickers |
| **Bank Nifty** | Zerodha Kite | WSS | Real-time | Quotes, Market Depth, Trades |
| **Nifty 50** | Zerodha Kite | WSS | Real-time | Quotes, Market Depth, Trades |

### Secondary Data Feeds

| Data Type | Source | Update Frequency | Purpose |
|-----------|--------|------------------|---------|
| **News** | Finnhub/Moneycontrol RSS | 5-10 min | Sentiment Analysis |
| **Macro** | RBI, Trading Economics | Daily | Economic Context |
| **Options** | Zerodha Kite | Real-time | Volatility, Open Interest |

## Data Ingestion Pipeline

### Stage 1: Raw Data Collection

**WebSocket Handlers:**
- **Binance**: `binance_futures_fetcher.py` / `binance_spot_fetcher.py`
- **Zerodha**: `data/ingestion_service.py`

**Data Normalization:**
```python
# Raw tick data structure (normalized)
tick_data = {
    "instrument": "BTC-USD",
    "timestamp": "2024-01-01T10:00:00Z",
    "last_price": 45000.50,
    "volume": 1234567,
    "bid_price": 45000.00,
    "bid_quantity": 100,
    "ask_price": 45001.00,
    "ask_quantity": 150,
    "ohlc": {
        "open": 44900,
        "high": 45100,
        "low": 44800,
        "close": 45000
    }
}
```

### Stage 2: OHLC Aggregation

**Timeframes Processed:**
- 1 minute (real-time updates)
- 5 minutes (technical analysis)
- 15 minutes (intermediate signals)
- 1 hour (trend analysis)
- Daily (fundamental context)

**Aggregation Logic:**
```python
# OHLC candle building
candle = {
    "instrument": "BTC-USD",
    "timestamp": "2024-01-01T10:00:00Z",
    "timeframe": "1min",
    "open": first_price_in_period,
    "high": max_price_in_period,
    "low": min_price_in_period,
    "close": last_price_in_period,
    "volume": sum_volume_in_period
}
```

### Stage 3: Data Storage

**Dual Storage Strategy:**

#### Redis Cache (Hot Data)
- **Purpose**: Fast access for agents and dashboard
- **TTL**: 24 hours for market data, 5 minutes for latest prices
- **Key Structure**:
  ```
  tick:{INSTRUMENT}:{TIMESTAMP}
  price:{INSTRUMENT}:latest
  ohlc:{INSTRUMENT}:{TIMEFRAME}:{TIMESTAMP}
  ```

#### MongoDB (Persistent Storage)
- **Purpose**: Historical analysis and backtesting
- **Collections**: `ohlc_history`, `agent_decisions`, `trades_executed`
- **Indexing**: `(timestamp, instrument)`, `(instrument, timeframe)`

## Agent Processing Pipeline

### Stage 4: Context Preparation

**Data Retrieval for Agents:**
```python
# Market context assembled for each agent
context = {
    "current_price": market_memory.get_current_price(instrument_key),
    "ohlc_1min": market_memory.get_recent_ohlc(instrument_key, "1min", 60),
    "ohlc_5min": market_memory.get_recent_ohlc(instrument_key, "5min", 100),
    "ohlc_15min": market_memory.get_recent_ohlc(instrument_key, "15min", 100),
    "ohlc_1h": market_memory.get_recent_ohlc(instrument_key, "1h", 60),
    "ohlc_daily": market_memory.get_recent_ohlc(instrument_key, "daily", 60),
    "recent_news": news_collector.get_recent_news(instrument, limit=10),
    "position_data": state_manager.get_position_summary()
}
```

### Stage 5: Parallel Agent Processing

**Agent Execution Order:**
1. **Technical Agent** (fastest, ~5-10s)
2. **Sentiment Agent** (news processing, ~10-15s)
3. **Fundamental Agent** (valuation analysis, ~10-15s)
4. **Macro Agent** (economic context, ~10-15s)
5. **Bull/Bear Researchers** (thesis building, ~15-20s)
6. **Risk Manager** (risk assessment, ~5-10s)
7. **Portfolio Manager** (synthesis, ~10-15s)

**Concurrency Control:**
- Max 2 agents running simultaneously
- LLM provider rate limiting (soft throttle: 0.8)
- Automatic fallback to backup providers

### Stage 6: Decision Synthesis

**Portfolio Manager Logic:**
```python
# Signal aggregation with confidence weighting
signals = {
    "technical": {"signal": "BUY", "confidence": 0.75},
    "fundamental": {"signal": "HOLD", "confidence": 0.60},
    "sentiment": {"signal": "BUY", "confidence": 0.70},
    "macro": {"signal": "BUY", "confidence": 0.65}
}

# Weighted decision calculation
weighted_signals = calculate_weighted_signals(signals)
final_decision = {
    "signal": "BUY",
    "confidence": 0.72,
    "position_size": "1.5%_of_portfolio"
}
```

## Signal Validation Pipeline

### Stage 7: Risk Validation

**Pre-Execution Checks:**
- **Position Limits**: Max 5% of account per trade
- **Daily Loss Limits**: Max 2% daily drawdown
- **Signal Confidence**: Minimum 0.6 confidence threshold
- **Market Hours**: Respect exchange trading hours
- **Circuit Breakers**: Volatility and volume filters

**Validation Logic:**
```python
def validate_signal(signal, context):
    checks = [
        validate_position_limits(signal),
        validate_daily_loss_limit(signal),
        validate_confidence_threshold(signal),
        validate_market_hours(signal),
        validate_circuit_breakers(signal)
    ]
    return all(checks)
```

### Stage 8: Order Execution

**Order Types:**
- **Market Orders**: Immediate execution at best available price
- **Limit Orders**: Execute at specified price or better
- **Stop Orders**: Triggered at stop price, executed as market/limit

**Execution Flow:**
```python
async def execute_trade(decision):
    # 1. Validate signal
    if not validate_signal(decision):
        return False

    # 2. Calculate position size
    quantity = calculate_position_size(decision)

    # 3. Place orders
    entry_order = await place_market_order(
        instrument=decision.instrument,
        side=decision.signal,
        quantity=quantity
    )

    # 4. Place risk management orders
    stop_order = await place_stop_order(
        instrument=decision.instrument,
        stop_price=decision.stop_loss,
        quantity=quantity
    )

    # 5. Record trade
    await record_trade_execution(entry_order, stop_order, decision)
```

## Monitoring and Alerting

### Stage 9: Performance Tracking

**Metrics Collected:**
- **Execution Metrics**: Fill rates, slippage, latency
- **Signal Quality**: Win rate, profit factor, Sharpe ratio
- **System Health**: Error rates, response times, API limits

**Real-time Monitoring:**
```python
# Key performance indicators
kpis = {
    "signal_accuracy": calculate_win_rate(),
    "avg_execution_time": measure_execution_latency(),
    "api_error_rate": track_api_errors(),
    "pnl_realized": calculate_realized_pnl()
}
```

### Stage 10: Learning Loop

**Performance Analysis:**
- **Trade Attribution**: Which agents contributed to wins/losses
- **Prompt Optimization**: Update agent prompts based on performance
- **Risk Parameter Tuning**: Adjust position sizes and stops
- **Strategy Evolution**: Identify and amplify successful patterns

**Learning Integration:**
```python
# Post-trade analysis
trade_analysis = {
    "winning_agents": identify_contributing_agents(trade),
    "losing_factors": identify_failure_reasons(trade),
    "prompt_updates": generate_prompt_improvements(trade),
    "risk_adjustments": calculate_risk_parameter_updates(trade)
}
```

## Error Handling and Resilience

### Circuit Breakers

**Automatic Halt Conditions:**
- **Volatility**: Price movement > 5% in 5 minutes
- **API Failures**: > 3 consecutive API errors
- **Drawdown**: Portfolio loss > 2% in a day
- **Liquidity**: Volume < 70% of average

**Recovery Procedures:**
- **Soft Halt**: Pause trading, continue monitoring
- **Hard Halt**: Close all positions, stop all agents
- **Auto Recovery**: Gradual resumption with reduced position sizes

### Data Quality Validation

**Data Integrity Checks:**
- **Staleness**: Alert if data > 5 minutes old
- **Anomalies**: Statistical outlier detection
- **Completeness**: Ensure all required fields present
- **Consistency**: Cross-validation between data sources

## Performance Characteristics

### Latency Targets

| Operation | Target Latency | Current Performance |
|-----------|----------------|-------------------|
| Data Ingestion | < 100ms | ~50ms |
| Agent Analysis | < 30s | ~15-20s |
| Signal Validation | < 1s | ~200ms |
| Order Execution | < 5s | ~2-3s |
| Dashboard Update | < 2s | ~500ms |

### Throughput Capacity

- **Ticks Processed**: 1000+ per second
- **Concurrent Agents**: 2 simultaneous
- **Active Instruments**: 3+ (containerized)
- **Orders per Minute**: 10-20 (rate limited)

## Data Retention Policy

### Storage Tiers

| Data Type | Redis TTL | MongoDB Retention | Purpose |
|-----------|-----------|-------------------|---------|
| **Tick Data** | 24 hours | 30 days | Real-time analysis |
| **OHLC (1m)** | 24 hours | 90 days | Technical analysis |
| **OHLC (5m+)** | 7 days | 1 year | Trend analysis |
| **Agent Decisions** | 24 hours | Indefinite | Performance tracking |
| **Trade Records** | N/A | Indefinite | Audit trail |

### Archival Strategy

- **Compression**: Older data compressed to reduce storage
- **Aggregation**: Raw ticks aggregated to higher timeframes
- **Backup**: Daily MongoDB backups with 30-day retention
- **Analytics**: Separate analytics database for reporting