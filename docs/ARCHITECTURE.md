# System Architecture

## Overview

The GenAI Trading System is a multi-agent LLM-powered trading platform supporting simultaneous trading across multiple instruments (Bitcoin, Bank Nifty, Nifty 50) with real-time data ingestion and autonomous decision making.

## Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Ingestion│    │   Agent System  │    │   Execution     │
│   (Real-time)   │───▶│   (LLM-powered) │───▶│   (Order Mgmt)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Redis Cache   │    │   MongoDB       │    │   Trading APIs  │
│   (Hot Data)    │    │   (Persistence) │    │   (Orders)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Data Flow

### 1. Market Data Ingestion

**Sources:**
- **Crypto (BTC)**: Binance WebSocket API
- **Indian Markets**: Zerodha Kite Connect WebSocket

**Processing:**
- Real-time tick data → OHLC aggregation (1m, 5m, 15m, 1h, daily)
- Order book data (top 5 levels)
- Volume analysis and order flow metrics

**Storage:**
- **Redis**: Hot data (24h TTL) for agent queries
- **MongoDB**: Historical data with instrument separation

### 2. Agent System (LangGraph Orchestration)

**Multi-Agent Architecture:**

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **Technical** | Chart analysis | OHLC, indicators | BUY/SELL signals |
| **Fundamental** | Asset valuation | News, macro data | Investment thesis |
| **Sentiment** | Market mood | News sentiment | Confidence scores |
| **Macro** | Economic context | RBI data, inflation | Risk regime |
| **Bull Researcher** | Optimistic case | All data | Bull thesis |
| **Bear Researcher** | Pessimistic case | All data | Bear thesis |
| **Risk Manager** | Risk assessment | Position data | Risk scores |
| **Portfolio Manager** | Final decision | All agent outputs | Trading decision |
| **Execution** | Order placement | Portfolio decision | API orders |
| **Learning** | Performance analysis | Trade results | Prompt refinement |

**Decision Flow:**
```
Raw Data → Individual Agents → Portfolio Manager → Risk Check → Execution
    ↓           ↓                    ↓              ↓            ↓
  Redis    Agent Decisions     Final Decision   Validation   API Orders
    ↓           ↓                    ↓              ↓            ↓
 MongoDB    MongoDB              MongoDB        Memory       Broker API
```

### 3. Execution Layer

**Order Types:**
- Market orders for entry/exit
- Stop-loss orders (trailing stops)
- Take-profit orders

**Risk Management:**
- Position size limits (5% of account max)
- Daily loss limits (2% max)
- Circuit breakers on volatility
- Automatic position closure

## Database Schema

### MongoDB Collections

```javascript
// OHLC History - Time-series market data
{
  instrument: "BTC-USD",
  timestamp: "2024-01-01T10:00:00Z",
  timeframe: "1min",
  open: 45000.00,
  high: 45100.00,
  low: 44900.00,
  close: 45050.00,
  volume: 1234567
}

// Agent Decisions - LLM analysis results
{
  timestamp: "2024-01-01T10:00:00Z",
  instrument: "BTC-USD",
  agent_decisions: {
    technical: { signal: "BUY", confidence: 0.75, reasoning: "..." },
    fundamental: { signal: "HOLD", confidence: 0.60, reasoning: "..." },
    // ... other agents
  }
}

// Trades Executed - Order history
{
  trade_id: "BTC_20240101_001",
  instrument: "BTC-USD",
  status: "OPEN",
  entry_timestamp: "2024-01-01T10:00:00Z",
  entry_price: 45000.00,
  quantity: 0.01,
  confidence: 0.75,
  agent_decisions: { /* full analysis */ }
}
```

### Redis Keys

```
# Latest prices (5min TTL)
price:BTCUSD:latest → "45000.50"
price:BTCUSD:latest_ts → "2024-01-01T10:00:00Z"

# Recent OHLC data (24h TTL)
ohlc:BTCUSD:1min:20240101T100000Z → {open, high, low, close, volume}

# Tick data (24h TTL)
tick:BTCUSD:20240101T100000Z → {price, volume, bid, ask, ...}
```

## Multi-Instrument Support

### Container Architecture

```
┌─────────────────────────────────────┐
│           Shared Services            │
│  ┌─────────────┐  ┌─────────────┐   │
│  │  MongoDB    │  │    Redis    │   │
│  │ (Port 27017)│  │  (Port 6379)│   │
│  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────┘
                    │
          ┌─────────┼─────────┐
          │         │         │
┌─────────▼──┐ ┌────▼───┐ ┌───▼────────┐
│ Trading Bot │ │Trading │ │ Trading    │
│ BTC:8001    │ │BankNifty│ │ Nifty:8003 │
│             │ │:8002    │ │             │
│ Backend BTC │ │Backend  │ │ Backend    │
└─────────────┘ │BankNifty│ │ Nifty      │
                └─────────┘ └────────────┘
```

### Instrument Isolation

- **Environment Variables**: Separate `.env.*` files per instrument
- **Database**: Shared MongoDB with `instrument` field separation
- **Cache**: Shared Redis with `instrument:` key prefixes
- **APIs**: Instrument-specific data sources and news feeds

## API Integration

### Data Sources

| Instrument | Price Data | News Feed | Update Frequency |
|------------|------------|-----------|------------------|
| Bitcoin | Binance WebSocket | Finnhub | Real-time |
| Bank Nifty | Zerodha Kite | EODHD | Real-time |
| Nifty 50 | Zerodha Kite | EODHD | Real-time |

### LLM Providers

**Supported Providers:**
- OpenAI GPT-4
- Anthropic Claude
- Google Gemini
- Groq (Llama models)
- Local Ollama
- Together AI
- OpenRouter

**Fallback System:**
- Primary + 2 backup providers
- Automatic failover on failures
- Weighted selection by performance

## Monitoring & Alerting

### Health Checks

- **Database**: Connection validation every 10s
- **APIs**: Key validation and rate limit monitoring
- **Agents**: Response time and error tracking
- **Positions**: P&L monitoring and auto-closure

### Alert Types

- **Circuit Breakers**: Volatility, drawdown, API failures
- **Performance**: Win rate, Sharpe ratio tracking
- **System**: Memory usage, error rates
- **Trading**: Position limits, daily loss limits

## Security Considerations

### API Key Management

- Environment variables (not committed)
- Separate keys per instrument
- Rate limiting and usage monitoring
- Automatic key rotation support

### Trading Safeguards

- Paper trading mode (default)
- Position size limits
- Daily loss limits
- Manual override capabilities
- Audit logging for all decisions

## Performance Characteristics

### Latency Targets

- **Data Ingestion**: <100ms from exchange to cache
- **Agent Analysis**: <30s per decision cycle
- **Order Execution**: <5s from decision to order
- **Dashboard Updates**: <2s refresh rate

### Scalability

- **Concurrent Instruments**: 3+ simultaneous (containerized)
- **Agent Parallelization**: Async processing with concurrency limits
- **Database**: Indexed queries, connection pooling
- **Cache**: Redis clustering ready