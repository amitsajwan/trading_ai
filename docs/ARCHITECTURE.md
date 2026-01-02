# System Architecture

## Overview

The GenAI Trading System is a fully autonomous multi-agent trading system for Bank Nifty built on LangGraph orchestration. The system uses specialized LLM-powered agents to analyze market conditions and make trading decisions with minimal human intervention.

**Key Design Principles**:
- **Multi-Agent Architecture**: Specialized agents for different aspects of analysis
- **Real-Time Data Processing**: WebSocket-based data ingestion with Redis caching
- **Risk-First Approach**: Multiple risk perspectives and circuit breakers
- **Self-Improving**: Learning agent analyzes outcomes and refines strategies
- **Production-Ready**: Paper trading mode, monitoring, and comprehensive logging

## System Components

### Core Components

1. **Data Ingestion Layer**
   - Zerodha Kite WebSocket for real-time market data
   - News collection from NewsAPI
   - Macro data collection (manual currently)

2. **Storage Layer**
   - Redis: Hot data cache (24-hour window)
   - MongoDB: Persistent storage for historical data and trades

3. **Agent Layer**
   - 10+ specialized agents for market analysis
   - LangGraph orchestration for agent coordination

4. **Decision Layer**
   - Portfolio Manager synthesizes all analyses
   - Risk management with multiple perspectives
   - Execution agent for order placement

5. **Monitoring Layer**
   - Real-time dashboard (FastAPI)
   - System health checks
   - Trade performance tracking

## Data Flow

1. **Market Data Ingestion**
   - Zerodha Kite WebSocket receives real-time ticks
   - Data is stored in Redis (hot data, 24-hour window)
   - Historical data persisted to MongoDB
   - OHLC candles aggregated from ticks

2. **State Initialization**
   - StateManager loads data from Redis and MongoDB
   - Creates AgentState with current market context
   - Includes OHLC data, sentiment, macro context

3. **Agent Processing**
   - Analysis agents run in parallel (technical, fundamental, sentiment, macro)
   - Bull/Bear researchers debate the analyses
   - Risk agents calculate position sizing from multiple perspectives

4. **Decision Making**
   - Portfolio Manager synthesizes all agent outputs
   - Generates final trading signal (BUY/SELL/HOLD)
   - Determines position size and stop-loss levels

5. **Execution**
   - Execution Agent places orders via Zerodha Kite API
   - Trades logged to MongoDB with full audit trail
   - Position monitoring for auto-exit on SL/target

6. **Learning** (Future)
   - Learning Agent analyzes completed trades
   - Identifies which agents were most predictive
   - Refines prompts for continuous improvement

## Agent Details

### Technical Analysis Agent
- Calculates RSI, MACD, ATR
- Identifies support/resistance levels
- Detects chart patterns
- Output: Trend direction, pattern confidence, volatility assessment

### Fundamental Analysis Agent
- Analyzes banking sector strength
- Assesses RBI policy impact
- Evaluates credit quality trends
- Output: Bullish/bearish probability, key risk factors

### Sentiment Analysis Agent
- Aggregates sentiment from news
- Detects retail vs institutional divergence
- Output: Sentiment scores, divergence alerts

### Macro Analysis Agent
- Monitors RBI rate cycle
- Tracks inflation and NPA trends
- Assesses liquidity conditions
- Output: Macro regime, sector headwind/tailwind score

### Bull/Bear Researchers
- Construct competing theses
- Stress-test opposing views
- Assign probability-weighted conviction scores
- Output: Thesis narrative, conviction scores, key drivers

### Risk Management Agents
- Three perspectives: Aggressive, Conservative, Neutral
- Calculate position size based on risk tolerance
- Determine stop-loss and leverage
- Output: Position size, stop-loss price, leverage recommendation

### Portfolio Manager
- Synthesizes all agent outputs with weighted scoring
- Applies decision logic (thresholds: 65% bullish/bearish - see [CURRENT_ISSUES.md](CURRENT_ISSUES.md))
- Checks portfolio constraints
- Output: Final signal, position size, entry/exit prices
- **Note**: Thresholds may be too high, resulting in mostly HOLD signals

### Execution Agent
- Places orders via Zerodha Kite API
- Tracks fill status
- Supports paper trading mode
- Output: Order ID, fill price, execution timestamp

### Learning Agent
- Analyzes trade outcomes
- Identifies agent performance
- Generates improvement suggestions
- Updates prompts dynamically

## State Management

`AgentState` is the shared context passed between all agents. It contains:
- Market context (price, OHLC data, sentiment)
- Agent outputs (accumulated analyses)
- Portfolio decisions (signals, position sizing)
- Execution details (order IDs, fills)
- Audit trail (explanations from each agent)

## Safety Mechanisms

### Circuit Breakers
- Daily loss limit: 2% of capital
- Consecutive losses: 5 trades
- Data feed health monitoring
- API rate limit tracking
- Volatility checks (VIX > 25)
- Leverage limits

### Risk Controls
- Max position size: 5% of account
- Max leverage: 1:2 (intraday)
- Max concurrent trades: 3
- Automatic stop-losses on all trades

## Deployment

### Local Development
- Docker containers for MongoDB and Redis
- Python virtual environment
- Environment variables in `.env`

### Production
- AWS EC2 for main trading loop
- AWS RDS for MongoDB
- AWS ElastiCache for Redis
- CloudWatch for monitoring

## Monitoring

- Real-time dashboard (FastAPI)
- Trading performance metrics
- Agent accuracy scores
- System health checks
- Slack/Email alerts

