# Engine Module Data Reference

## Complete Data Publishing and Consumption Specification

This document is the authoritative reference for all data structures, APIs, and data flows used by the Engine Module. It serves as the single source of truth for integrating with the trading engine and understanding how agents consume data.

**Version:** 1.0.0
**Last Updated:** January 19, 2026
**Contact:** Engine Module Team

---

## 📊 Data Consumed by Engine Module

### Core Market Data (from Market Data Module)

#### Real-time Price Data
**Source:** Redis keys published by Market Data module
**Purpose:** Current market prices and trading volume

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `price:{instrument}:latest` | String (Float) | 24h | Last traded price | TechnicalAgent, VolumeAgent, MomentumAgent |
| `price:{instrument}:latest_ts` | String (ISO 8601) | 24h | Timestamp of last price update | All agents requiring timestamps |
| `volume:{instrument}:latest` | String (Integer) | 24h | Current trading volume | VolumeAgent, MomentumAgent |

#### OHLC Time-Series Data
**Source:** Redis keys published by Market Data module
**Purpose:** Candlestick data for technical analysis

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `ohlc:{instrument}:{timeframe}:{timestamp}` | JSON String | 24h | Individual OHLC bar | TechnicalAgent, VolumeAgent |
| `ohlc:sorted:{instrument}:{timeframe}` | Redis ZSET | Persistent | Time-sorted OHLC bars | TechnicalAgent |

**Supported Timeframes:** `1min`, `5min`, `15min`, `1h`, `daily`

**OHLC Bar Schema:**
```json
{
  "instrument": "BANKNIFTY",
  "timeframe": "1min",
  "open": 45200,
  "high": 45300,
  "low": 45150,
  "close": 45250,
  "volume": 1000,
  "start_at": "2024-01-19T10:30:00"
}
```

#### Market Depth Data
**Source:** Redis keys published by Market Data module
**Purpose:** Order book information

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `depth:{instrument}:buy` | JSON Array | Persistent | Bid orders (price, quantity) | OptionsAnalysisAgent |
| `depth:{instrument}:sell` | JSON Array | Persistent | Ask orders (price, quantity) | OptionsAnalysisAgent |

### Technical Indicators
**Source:** Redis keys published by Market Data module
**Purpose:** Pre-calculated technical analysis indicators

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `indicators:{instrument}:{indicator_name}` | String (Float) | 5min | Individual indicator values | All technical agents |
| `indicators:{instrument}:{timeframe}:{indicator_name}` | String (Float) | 5min | Multi-timeframe indicators | Advanced technical agents |

**Available Indicators:**
- **RSI:** `rsi_14`, `rsi_9`
- **MACD:** `macd_value`, `macd_signal`, `macd_histogram`
- **Bollinger Bands:** `bollinger_upper`, `bollinger_middle`, `bollinger_lower`
- **ADX:** `adx_14`, `di_plus`, `di_minus`
- **ATR:** `atr_14`, `atr_20`
- **Volume:** `volume_sma_20`, `volume_rsi_14`
- **Oscillators:** `cci_20`, `mfi_14`, `roc_12`
- **Support/Resistance:** `pivot_point`, `pivot_r1`, `pivot_r2`
- **Price Action:** `high_20`, `low_20`, `range_20`
- **Derived:** `trend_direction`, `trend_strength`, `signal_strength`

### Options Chain Data
**Source:** Redis keys published by Market Data module
**Purpose:** Complete options chain with Greeks calculations

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `options:{instrument}:chain` | JSON String | 5min | Full options chain with Greeks | OptionsAnalysisAgent |

**Options Chain Schema:**
```json
{
  "instrument": "BANKNIFTY",
  "expiry": "2024-01-30",
  "strikes": [
    {
      "strike": 45250,
      "CE": {
        "last_price": 125.5,
        "volume": 1000,
        "oi": 50000,
        "iv": 22.5,
        "delta": 0.65,
        "gamma": 0.02,
        "theta": -15.3,
        "vega": 8.7,
        "rho": 12.4
      },
      "PE": {
        "last_price": 85.2,
        "iv": 21.8,
        "delta": -0.35
      }
    }
  ],
  "pcr": 1.15,
  "max_pain": 45250
}
```

---

## 📰 News and Sentiment Data

### News Data
**Source:** Redis keys published by News Module
**Purpose:** News articles and sentiment analysis

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `news:{instrument}:latest` | JSON Array | 1h | Latest news articles for instrument | SentimentAgent |
| `news:{instrument}:sentiment` | String (Float) | 1h | Aggregate sentiment score (-1.0 to 1.0) | SentimentAgent |

**News Item Schema:**
```json
{
  "title": "Bank Nifty hits new high on strong earnings",
  "content": "Full article content...",
  "source": "Economic Times",
  "published_at": "2024-01-19T10:30:00",
  "sentiment_score": 0.8,
  "url": "https://...",
  "instruments": ["BANKNIFTY"],
  "tags": ["earnings", "bullish"]
}
```

---

## 📈 Fundamental Data

### Company Fundamentals
**Source:** Redis keys (to be populated by external fundamental data feeds)
**Purpose:** Valuation metrics and financial ratios

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `fundamentals:{instrument}` | JSON Object | 24h | Complete fundamental data | FundamentalAgent |

**Fundamental Data Schema:**
```json
{
  "earnings_surprise": 0.15,
  "revenue_growth": 0.25,
  "pe_ratio": 18.5,
  "pb_ratio": 2.8,
  "roe": 0.18,
  "debt_equity": 0.4,
  "eps": 45.20,
  "book_value": 285.50,
  "dividend_yield": 0.025,
  "market_cap": 2500000000000,
  "sector": "Financial Services",
  "last_updated": "2024-01-19T09:00:00"
}
```

---

## 🌍 Macroeconomic Data

### Economic Indicators
**Source:** Redis keys (to be populated by macroeconomic data feeds)
**Purpose:** Economic indicators affecting market sentiment

| Redis Key | Type | TTL | Description | Used By |
|-----------|------|-----|-------------|---------|
| `macro:rbi_rate` | String (Float) | 24h | Current RBI repo rate | MacroAgent |
| `macro:inflation_rate` | String (Float) | 24h | Latest inflation rate | MacroAgent |
| `macro:npa_ratio` | String (Float) | 24h | Banking NPA ratio | MacroAgent |
| `macro:gdp_growth` | String (Float) | 24h | GDP growth rate | MacroAgent |
| `macro:usd_inr` | String (Float) | 24h | USD-INR exchange rate | MacroAgent |

---

## 🤖 Agent Data Requirements

### Agent Context Schema

All agents receive a unified context dictionary with the following possible keys:

```python
{
    # Core trading context
    "instrument": "BANKNIFTY",  # Trading instrument
    "current_price": 45250.75,  # Current market price
    "timestamp": "2024-01-19T10:30:15.123456",  # Current timestamp

    # Technical data (from technical_data_provider)
    "technical_indicators": {
        "rsi_14": 68.5,
        "macd_value": 125.75,
        "bollinger_upper": 45350.25,
        "trend_direction": "UP",
        "trend_strength": 75.2
    },

    # OHLC data (from market_data_provider)
    "ohlc": [
        {
            "instrument": "BANKNIFTY",
            "timeframe": "1min",
            "open": 45200,
            "high": 45300,
            "low": 45150,
            "close": 45250,
            "volume": 1000,
            "start_at": "2024-01-19T10:30:00"
        }
    ],

    # News and sentiment (from news_data_provider)
    "latest_news": [...],  # Array of news items
    "sentiment_score": 0.3,  # Aggregate sentiment

    # Fundamental data (from fundamental_data_provider)
    "earnings_surprise": 0.15,
    "pe_ratio": 18.5,
    "roe": 0.18,

    # Macro data (from macro_data_provider)
    "rbi_rate": 6.5,
    "inflation_rate": 4.2,
    "npa_ratio": 0.35,

    # Options data (from options_data_provider)
    "calls": [...],  # Call options chain
    "puts": [...],   # Put options chain
    "pcr": 1.15,     # Put-call ratio
    "max_pain": 45250,

    # Position data (from position_provider)
    "positions": [...],  # Current positions
    "has_long_position": False,
    "has_short_position": False
}
```

### Agent-Specific Requirements

| Agent | Required Context Keys | Optional Context Keys |
|-------|----------------------|----------------------|
| **TechnicalAgent** | `ohlc` | `current_price` |
| **VolumeAgent** | `ohlc` | `current_price` |
| **MomentumAgent** | `technical_indicators`, `current_price` | `has_long_position`, `has_short_position` |
| **SentimentAgent** | `latest_news`, `sentiment_score` | - |
| **FundamentalAgent** | `earnings_surprise`, `pe_ratio`, etc. | - |
| **MacroAgent** | `rbi_rate`, `inflation_rate`, etc. | - |
| **OptionsAnalysisAgent** | `calls`, `puts`, `underlying_price`, `pcr` | `consensus_direction` |
| **BearResearcher** | `technical_indicators`, `current_price` | - |
| **BullResearcher** | `technical_indicators`, `current_price` | - |

---

## 🔄 Data Flow Architecture

### Orchestrator Data Pipeline

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Market Data    │───▶│   Redis Cache   │───▶│   Data Providers │
│   Collectors     │    │   (TTL-based)   │    │   (Engine Module)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐             │
│   News Module    │───▶│   Data Providers │◀────────────┘
│   Collectors     │    │   (Engine Module)│
└─────────────────┘    └─────────────────┘
           │
           ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Orchestrator   │───▶│ Agent Context   │───▶│   Analysis      │
│  (Enhanced)     │    │ Preparation     │    │   Agents        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Provider Classes

| Provider | Class | Data Source | Used For |
|----------|-------|-------------|----------|
| **MarketDataProvider** | `RedisMarketDataProvider` | `ohlc:*` keys | OHLC data for technical analysis |
| **TechnicalDataProvider** | `RedisTechnicalDataProvider` | `indicators:*` keys | Pre-calculated indicators |
| **NewsDataProvider** | `RedisNewsDataProvider` | `news:*` keys | News and sentiment data |
| **FundamentalDataProvider** | `RedisFundamentalDataProvider` | `fundamentals:*` keys | Company fundamentals |
| **MacroDataProvider** | `RedisMacroDataProvider` | `macro:*` keys | Economic indicators |
| **OptionsDataProvider** | `RedisOptionsDataProvider` | `options:*` keys | Options chain data |

### Data Freshness Requirements

| Data Type | Max Age | Update Frequency | Criticality |
|-----------|---------|------------------|-------------|
| **Price Data** | 2 seconds | Sub-second | Critical |
| **OHLC (1min)** | 1 minute | Real-time | High |
| **Technical Indicators** | 5 minutes | On-demand | High |
| **Options Chain** | 5 minutes | Market hours | Medium |
| **News** | 1 hour | Hourly | Low |
| **Fundamentals** | 24 hours | Daily | Low |
| **Macro Data** | 24 hours | Daily | Low |

---

## ⚡ Performance Characteristics

### Latency Targets

| Operation | Target | Typical | Notes |
|-----------|--------|---------|-------|
| **Redis GET (single key)** | < 1ms | < 0.5ms | Direct Redis access |
| **OHLC data fetch (100 bars)** | < 50ms | < 20ms | JSON parsing + sorting |
| **Technical indicators fetch** | < 10ms | < 5ms | Multiple key gets |
| **Agent context preparation** | < 100ms | < 50ms | Data aggregation |
| **Single agent analysis** | < 500ms | < 200ms | LLM calls excluded |

### Data Volume Estimates

| Data Type | Size per Instrument | Update Frequency | Daily Volume |
|-----------|---------------------|------------------|--------------|
| **OHLC bars (1min)** | ~1KB per bar | 375 bars/day | ~375KB/day |
| **Technical indicators** | ~2KB | Every 5min | ~576KB/day |
| **Options chain** | ~50KB | Every 5min | ~14MB/day |
| **News items** | ~5KB per article | 10-50/day | ~250KB/day |

---

## 🚨 Error Handling

### Data Unavailability

**Fallback Strategies:**
- **Technical indicators unavailable:** Agents use simplified calculations
- **OHLC data unavailable:** TechnicalAgent falls back to price-only analysis
- **News data unavailable:** SentimentAgent uses neutral sentiment (0.0)
- **Fundamental data unavailable:** FundamentalAgent returns HOLD
- **Macro data unavailable:** MacroAgent uses neutral regime

### Data Validation

**Validation Rules:**
- **Price data:** Must be positive floats within ±50% of previous price
- **OHLC bars:** High ≥ Low, Open/Close within range, volume ≥ 0
- **Technical indicators:** Within reasonable bounds (RSI: 0-100, etc.)
- **News sentiment:** -1.0 to 1.0 range
- **Timestamps:** Valid ISO 8601 format, not in future

---

## 🔧 Configuration

### Environment Variables

```bash
# Redis Connection
REDIS_HOST=localhost
REDIS_PORT=6379

# Data Provider Configuration
ENGINE_DATA_CACHE_TTL=300          # 5 minutes for computed data
ENGINE_NEWS_CACHE_TTL=3600         # 1 hour for news data
ENGINE_FUNDAMENTAL_CACHE_TTL=86400 # 24 hours for fundamentals
```

### Data Provider Initialization

```python
from engine_module.redis_providers import (
    build_redis_market_data_provider,
    build_redis_technical_data_provider,
    build_redis_news_data_provider,
    build_redis_fundamental_data_provider,
    build_redis_macro_data_provider,
    build_redis_options_data_provider
)

# Initialize providers
market_provider = build_redis_market_data_provider(redis_client)
technical_provider = build_redis_technical_data_provider(redis_client)
news_provider = build_redis_news_data_provider(redis_client)
fundamental_provider = build_redis_fundamental_data_provider(redis_client)
macro_provider = build_redis_macro_data_provider(redis_client)
options_provider = build_redis_options_data_provider(redis_client)
```

---

## 📞 Integration Examples

### Python - Data Provider Usage

```python
import redis
from engine_module.redis_providers import build_redis_technical_data_provider

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Create providers
technical_provider = build_redis_technical_data_provider(redis_client)

# Get technical indicators
indicators = await technical_provider.get_indicators("BANKNIFTY")
print(f"RSI: {indicators.get('rsi')}, Trend: {indicators.get('trend_direction')}")
```

### Orchestrator Integration

```python
from engine_module.api import build_orchestrator
from engine_module.enhanced_orchestrator import TradingContext

# Create context
context = TradingContext(
    instrument="BANKNIFTY",
    mode="LIVE",
    run_id="20240119_001"
)

# Build orchestrator with all data providers
orchestrator = build_orchestrator(
    llm_client=llm_client,
    redis_client=redis_client,
    agents=[technical_agent, sentiment_agent, options_agent],
    context=context
)

# Run analysis cycle
result = await orchestrator.run_cycle({
    "instrument": "BANKNIFTY",
    "current_price": 45250.0
})
```

---

## 📋 Data Quality Monitoring

### Health Checks

**Critical Metrics:**
- **Redis connectivity:** Must be available
- **Data freshness:** No data older than specified TTL
- **Data completeness:** All required fields present
- **Agent success rate:** >95% of agents should complete analysis

### Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| **Redis disconnected** | Critical | Halt trading, alert ops |
| **Price data >5s old** | High | Degrade to HOLD decisions |
| **OHLC data >10min old** | Medium | Use stale data with warnings |
| **Agent failure rate >10%** | Medium | Log errors, continue with remaining agents |

---

## 🔄 Data Lifecycle

### Data Ingestion Pipeline

1. **Raw Data Collection:** Market data collectors fetch from exchanges/APIs
2. **Processing & Calculation:** Technical indicators calculated by market_data module
3. **Caching:** Data stored in Redis with appropriate TTL
4. **Consumption:** Engine module providers fetch from Redis
5. **Analysis:** Agents process data and generate signals
6. **Persistence:** Decisions and signals stored in MongoDB

### Data Retention Policy

| Data Type | Redis TTL | MongoDB Retention | Archive Policy |
|-----------|-----------|-------------------|----------------|
| **Real-time prices** | 24 hours | 30 days | Compressed archive |
| **OHLC bars** | 24 hours | 1 year | Time-series DB |
| **Technical indicators** | 5 minutes | 7 days | Analytics DB |
| **News articles** | 1 hour | 90 days | Search index |
| **Trading decisions** | N/A | 1 year | Audit trail |
| **Signals** | N/A | 1 year | Performance analysis |

---

**This is the complete and authoritative reference for Engine Module data structures and flows. For implementation questions or data access requests, please contact the Engine Module team.**