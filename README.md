# GenAI-Powered Algo Trading System for Bank Nifty

A fully autonomous multi-agent LLM trading system for Bank Nifty using LangGraph orchestration, real-time data ingestion, and self-improving capabilities.

## Architecture Overview

```
Market Data → Data Ingestion → Redis (Memory) → LangGraph Agents → Portfolio Manager → Execution → MongoDB (Logs) → Learning Agent
```

### Multi-Agent System

The system consists of 10+ specialized agents:

1. **Technical Analysis Agent** - Chart patterns, momentum indicators, support/resistance
2. **Fundamental Analysis Agent** - Banking sector strength, RBI policy, credit quality
3. **Sentiment Analysis Agent** - Market sentiment from news and social media
4. **Macro Analysis Agent** - Macro regime detection, RBI cycle, liquidity conditions
5. **Bull Researcher Agent** - Constructs bullish thesis and stress-tests bear case
6. **Bear Researcher Agent** - Constructs bearish thesis and stress-tests bull case
7. **Risk Management Agents** (3 perspectives) - Aggressive, Conservative, Neutral risk assessment
8. **Portfolio Manager Agent** - Synthesizes all analyses and makes final decisions
9. **Execution Agent** - Order placement via Zerodha Kite API
10. **Learning Agent** - Post-trade analysis and prompt refinement

## Features

- **Zero Human Intervention** - Fully autonomous operation during market hours
- **Multi-Agent Reasoning** - Specialized agents with LLM-powered analysis
- **Real-time Data Ingestion** - WebSocket-based market data collection
- **Self-Improving** - Learning agent refines prompts based on trade outcomes
- **Risk Management** - Multiple risk perspectives with automatic circuit breakers
- **Paper Trading Mode** - Test strategies before going live
- **Monitoring Dashboard** - Real-time metrics and observability

## Setup

### Prerequisites

- Python 3.9+
- MongoDB (local or remote)
- Redis (local or remote)
- Zerodha Kite Connect API credentials
- OpenAI API key (or Azure OpenAI)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd zerodha
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

4. Set up MongoDB and Redis:
```bash
# MongoDB
mongod

# Redis
redis-server
```

5. Initialize MongoDB schema:
```bash
python mongodb_schema.py
```

6. Authenticate with Zerodha:
```bash
python auto_login.py
```

## Configuration

Key configuration in `.env`:

- `KITE_API_KEY` - Zerodha Kite API key
- `KITE_API_SECRET` - Zerodha Kite API secret
- `LLM_PROVIDER` - LLM provider (groq, openai, azure, ollama, huggingface, together, gemini)
- `GROQ_API_KEY` - Groq API key (or other LLM provider key)
- `MONGODB_URI` - MongoDB connection string
- `REDIS_HOST` - Redis host
- `PAPER_TRADING_MODE=true` - Start in paper trading mode

See `.env.example` for all configuration options.

## Usage

### Running the Trading System

#### Option 1: Unified Trading Service (Recommended)

Run the unified trading service that integrates all components:
```bash
python -m services.trading_service
```

This starts:
- Data ingestion (Zerodha WebSocket)
- Trading graph (60-second analysis cycle)
- Position monitoring (auto-exit on SL/target)
- All running in a single process

#### Option 2: Docker Deployment

```bash
# Start all services with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f trading-bot
```

#### Option 3: Separate Components

1. Start data ingestion:
```bash
python -m data.run_ingestion
```

2. Run the trading graph:
```bash
python -m trading_orchestration.main
```

### Monitoring Dashboard

Start the monitoring dashboard:
```bash
python -m monitoring.dashboard
```

Access at `http://localhost:8000`

Endpoints:
- `/metrics/trading` - Trading performance metrics
- `/metrics/agents` - Agent performance metrics
- `/health` - System health check

### Paper Trading

The system starts in paper trading mode by default. Trades are simulated without real money. Monitor performance before switching to live trading.

## Project Structure

```
zerodha/
├── agents/              # All agent implementations
│   ├── base_agent.py
│   ├── technical_agent.py
│   ├── fundamental_agent.py
│   ├── sentiment_agent.py
│   ├── macro_agent.py
│   ├── bull_researcher.py
│   ├── bear_researcher.py
│   ├── risk_agents.py
│   ├── portfolio_manager.py
│   ├── execution_agent.py
│   ├── learning_agent.py
│   └── state.py
├── data/                # Data ingestion and storage
│   ├── ingestion_service.py
│   ├── market_memory.py
│   ├── news_collector.py
│   └── macro_collector.py
├── config/              # Configuration and prompts
│   ├── settings.py
│   ├── prompt_manager.py
│   └── prompts/
├── trading_orchestration/  # LangGraph orchestration
│   ├── trading_graph.py
│   ├── state_manager.py
│   └── main.py
├── monitoring/           # Observability
│   ├── circuit_breakers.py
│   ├── dashboard.py
│   ├── alerts.py
│   ├── position_monitor.py  # Continuous position monitoring
│   ├── system_health.py     # System health checks
│   └── daily_reporter.py    # Automated daily reports
├── services/             # Unified services
│   ├── trading_service.py   # Main unified trading service
│   └── learning_scheduler.py # Weekly learning agent scheduler
├── utils/               # Utilities
│   ├── paper_trading.py
│   └── backtest_engine.py   # Enhanced with metrics & visualization
└── tests/               # Test suites
    └── test_integration_full.py  # Full integration tests
```

## Safety Features

- **Circuit Breakers** - Automatic trading halt on:
  - Daily loss limit exceeded
  - Consecutive losses (5+)
  - Data feed down
  - API rate limits
  - High volatility (VIX > 25)
  - Over-leveraged positions

- **Paper Trading** - Test strategies before live trading
- **Position Limits** - Max position size, leverage, concurrent trades
- **Stop Losses** - Automatic stop-loss on all trades
- **Position Monitoring** - Continuous monitoring with auto-exit on SL/target
- **Bracket Orders** - Automatic SL and target management via Zerodha
- **Daily Reporting** - Automated daily P&L and metrics reports
- **Learning Agent** - Weekly analysis and prompt optimization

## Performance Metrics

Track:
- Sharpe ratio (target: > 1.0)
- Win rate (target: > 55%)
- Max drawdown (limit: < 15%)
- Agent accuracy scores
- System latency

## Development

### Running Tests

```bash
pytest tests/
```

### Adding New Agents

1. Create agent class inheriting from `BaseAgent`
2. Implement `process()` method
3. Add to `TradingGraph` in `trading_orchestration/trading_graph.py`
4. Add system prompt in `config/prompts/`

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[docs/DATA_FLOW.md](docs/DATA_FLOW.md)** - Complete data flow documentation
- **[docs/SETUP.md](docs/SETUP.md)** - Detailed setup instructions
- **[docs/CURRENT_ISSUES.md](docs/CURRENT_ISSUES.md)** - Known issues and limitations
- **[docs/AGENTS.md](docs/AGENTS.md)** - Agent documentation
- **[docs/API.md](docs/API.md)** - API reference

See [docs/README.md](docs/README.md) for documentation index.

## License

[Your License Here]

## Disclaimer

This system is for educational purposes. Trading involves risk. Always test thoroughly in paper trading mode before using real money. Past performance does not guarantee future results.
