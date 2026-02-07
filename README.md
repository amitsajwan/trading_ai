# 🤖 Zerodha AI Trading System

**Intelligent Algorithmic Trading Platform with Multi-Agent Architecture**

[![Status](https://img.shields.io/badge/Status-Active-success)](https://github.com/your-repo)
[![Python](https://img.shields.io/badge/Python-3.8+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A comprehensive AI-powered algorithmic trading platform featuring multi-agent intelligence, real-time signal processing, and advanced backtesting capabilities. Built for Indian markets with Zerodha Kite integration.

## 🎯 Core Features

### 🤖 Multi-Agent Intelligence System
- **Bull/Bear Research Agents**: Market sentiment analysis
- **Technical Agent**: 14+ indicators with RSI, MACD, ADX
- **Options Strategy Agent**: Iron Condor, spreads with real market data
- **Risk Management Agent**: Position sizing and portfolio heat monitoring

### 📊 Real-Time Signal Processing
- **Signal-to-Trade**: Automated order generation from AI signals
- **WebSocket Integration**: Real-time market data via Redis
- **Virtual Time System**: Deterministic testing with market hours simulation

### 🕐 Historical Trading & Backtesting
- **Zerodha Historical API**: Real market data for accurate testing
- **Synthetic Data Generation**: Volume and gap simulation
- **Multi-Speed Playback**: 1x to 100x speed for fast-forward testing
- **Run Isolation**: Each backtest session has unique run_id and mode tagging
- **Automatic Data Cleanup**: 7-day retention with run-based filtering

### 🏗️ Microservices Architecture
- **6 Independent Modules**: Engine, Market Data, Dashboard, Risk, News, User
- **Redis Pub/Sub**: Event-driven communication
- **MongoDB Persistence**: Signal and decision storage
- **Docker Containerization**: Production-ready deployment

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MongoDB 4.4+
- Redis 6.0+
- Zerodha Kite API credentials

### Optional Dependencies
Some features require additional packages that are not installed by default:

- **chromadb**: Required for BullResearcher and BearResearcher agents (AI memory features)
- **data_niftybank**: Required for historical data replay functionality  
- **risk_module**: Required for advanced risk management features (portfolio heat, position sizing)

These modules will gracefully degrade if not available, with warnings logged but core functionality preserved.

### Installation

```bash
# Clone repository
git clone <repository-url>
cd zerodha

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your Zerodha credentials
```

### Live Trading Mode

```bash
# Start live trading with real market data
export TRADING_MODE=live
python start_local.py --provider zerodha

# Access dashboard at http://localhost:3000
# API available at http://localhost:8000
```

### Backtesting Mode

```bash
# Run backtests with historical data (run isolation enabled)
export TRADING_MODE=backtest
python start_local.py --provider historical --historical-source zerodha \
    --historical-from 2026-01-23 --historical-speed 1

# Each backtest run gets unique run_id and mode tagging
# Previous runs are automatically isolated and don't interfere
# Access results via API: http://localhost:8006/api/v1/decision/latest
```

### Demo Mode

```bash
# Test with synthetic data (no API credentials needed)
python start_local.py --provider mock
```

## 🏛️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DASHBOARD     │    │     ENGINE      │    │   MARKET DATA   │
│   (React/TS)    │◄──►│  (Multi-Agent)  │◄──►│   (Zerodha)    │
│                 │    │                 │    │                 │
│ • Trading UI    │    │ • Signal Agents │    │ • Real-time     │
│ • Charts        │    │ • Options Strat │    │ • Historical    │
│ • Controls      │    │ • Risk Mgmt     │    │ • Synthetic     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   CORE KERNEL   │
                    │                 │
                    │ • Redis Pub/Sub │
                    │ • MongoDB Store │
                    │ • Time Service  │
                    │ • Mode Manager  │
                    └─────────────────┘
```

### Module Structure

- **`engine_module/`**: AI agents and trading logic
- **`market_data/`**: Zerodha integration and data collection
- **`dashboard/`**: React/TypeScript trading interface
- **`core_kernel/`**: Shared services and contracts
- **`risk_module/`**: Position sizing and risk management
- **`news_module/`**: Market news and sentiment analysis
- **`user_module/`**: User management and preferences

## 📚 Documentation

### Getting Started
- **[Architecture Overview](docs/architecture/ARCHITECTURE.md)** - System design and data flow
- **[Features Guide](docs/business/FEATURES.md)** - Complete feature documentation
- **[Development Setup](docs/development/START_LOCAL_GUIDE.md)** - Local development guide

### Trading Features
- **[Signal-to-Trade System](docs/SIGNAL_LIFECYCLE.md)** - How signals become trades
- **[Multi-Agent Intelligence](docs/agents/AGENTS_ECOSYSTEM_DOCUMENTATION.md)** - Agent architecture
- **[Historical Replay](docs/business/FEATURES.md#historical-mode--replay)** - Backtesting guide

### Technical Reference
- **[API Documentation](docs/business/API_INDEX.md)** - REST API reference
- **[Zerodha Integration](docs/data/ZERODHA_DATA_STRUCTURES.md)** - Kite API usage
- **[Testing Guide](docs/development/TESTING.md)** - Test suite and procedures

### Development
- **[Debugging Checklist](docs/development/DEBUGGING_CHECKLIST.md)** - Troubleshooting guide
- **[Code Standards](docs/architecture/ARCHITECTURE.md#extension-points)** - Development guidelines

## 🧪 Testing

```bash
# Run full test suite
pytest tests/ -v

# Run specific module tests
pytest engine_module/tests/ -v
pytest market_data/tests/ -v

# Run integration tests
pytest tests/integration/ -v
```

## 🔧 Configuration

See `docs/README_CURRENT.md` for current environment variables, ports, and service entrypoints.
```bash
python scripts/data_migration.py cleanup-legacy --instruments BANKNIFTY26JANFUT
```
2. Backups are automatically created under `backups/`. When ready, delete with confirmation:
```bash
python scripts/data_migration.py cleanup-legacy --instruments BANKNIFTY26JANFUT --confirm
```
3. Re-validate with data validator:
```bash
python -c "from market_data.data_validator import DataValidator; import redis; rv=redis.Redis(); print(DataValidator(rv).validate_ohlc_data('BANKNIFTY26JANFUT','1min'))"
```

Always backup before deletion and verify consistency before and after cleanup.

### Docker Deployment

```bash
# Build and run all services
docker-compose -f docker-compose.yml up --build

# Run with historical data
docker-compose -f docker-compose.yml -f docker-compose.historical.yml up

# Run with live trading data
docker-compose -f docker-compose.yml -f docker-compose.live.yml up
```

### Hybrid Docker-Local Mode

For development, you can run market data in Docker while keeping other services local:

```bash
# Start Docker infrastructure (MongoDB, Redis, market-data-api)
docker-compose -f docker-compose.data.yml up -d
docker-compose up -d market-data-api

# Start other services locally with Docker market data
python start_local.py --provider zerodha --docker-market-data
```

### Full Docker Mode

Run everything in Docker for complete decoupling:

```bash
# Start all Docker services with live trading
docker-compose -f docker-compose.yml -f docker-compose.live.yml up -d

# Or with historical data
docker-compose -f docker-compose.yml -f docker-compose.historical.yml up -d

# Access URLs:
# - Market Data Dashboard: http://localhost:8008/ (status & visualization)
# - Trading Dashboard: http://localhost:8888/ (full trading interface)
# - Market Data API: http://localhost:8004/health
```

This provides complete decoupling where:
- **Market Data Dashboard** (port 8008): Standalone monitoring with visual verification
- **Trading Dashboard** (port 8888): Full trading interface with engine integration
- All services are containerized and can run independently

## 🔌 API Endpoints

### Engine Module API (Port 8006)
- **GET** `/api/v1/decision/latest` - Get latest trading decision (run-isolated)
- **POST** `/api/v1/orchestrator/run_cycle` - Trigger manual analysis cycle
- **GET** `/api/v1/signals/{instrument}` - Get signals for instrument (run-filtered)
- **POST** `/api/v1/options-strategy-agent` - Generate options strategies

**Note**: All API responses include `run_id` and `mode` for session isolation

### Dashboard API (Port 8000)
- **GET** `/api/positions` - Current positions and P&L
- **GET** `/api/signals` - Trading signals (WebSocket real-time)
- **POST** `/api/trade` - Execute trades

## 📊 Key Capabilities

### Real-Time Trading
- **14 Technical Indicators**: RSI, MACD, ADX, Bollinger Bands, etc.
- **Multi-Timeframe Analysis**: 1-min to daily charts
- **Options Strategies**: Iron Condor, Bull/Bear spreads
- **Risk Management**: Position sizing, stop-loss, take-profit

### Backtesting & Analysis
- **Historical Data**: 10+ years of Zerodha data
- **Performance Metrics**: Sharpe ratio, max drawdown, win rate
- **Strategy Optimization**: Parameter tuning and validation
- **Synthetic Data**: Volume simulation for gap periods

### AI & Intelligence
- **Sentiment Analysis**: News and social media processing
- **Pattern Recognition**: Chart pattern detection
- **Market Regime Classification**: Trend vs range detection
- **Adaptive Strategies**: Market condition adjustments

## 🐛 Troubleshooting

### Common Issues

**Connection Issues:**
```bash
# Check Redis connectivity
redis-cli ping

# Check MongoDB
mongosh --eval "db.runCommand({ping: 1})"
```

**Zerodha API Issues:**
```bash
# Verify credentials
python scripts/verify_zerodha_auth.py

# Check API limits
python scripts/check_api_limits.py
```

**Performance Issues:**
```bash
# Monitor system resources
python monitor_system.py

# Check Redis memory usage
redis-cli info memory
```

### Debug Mode

```bash
# Enable detailed logging
export LOG_LEVEL=DEBUG
export TRADING_MODE=live

# Run with verbose output
python start_local.py --provider zerodha -v
```

## 🤝 Contributing

### Development Workflow

1. **Fork and Branch**
   ```bash
   git checkout -b feature/new-agent
   ```

2. **Follow Standards**
   - Type hints for all functions
   - Comprehensive docstrings
   - Unit tests for new features
   - Update documentation

3. **Testing**
   ```bash
   # Run relevant tests
   pytest tests/ -k "new_feature"
   ```

4. **Code Review**
   - Self-review with checklist
   - Peer review required
   - CI/CD pipeline validation

### Adding New Agents

```python
# 1. Create agent class
from engine_module.contracts import Agent, AnalysisResult

class NewAgent(Agent):
    def __init__(self):
        self._agent_name = "NewAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Implementation
        pass
```

## 📈 Performance Benchmarks

### Live Trading
- **Signal Latency**: <100ms from tick to signal
- **Order Execution**: <500ms from signal to order
- **Throughput**: 1000+ signals/minute

### Backtesting
- **Data Processing**: 100,000+ candles/minute
- **Strategy Testing**: 1000+ parameter combinations/hour
- **Memory Usage**: <2GB for 1-year backtest

### System Resources
- **CPU**: 2-4 cores recommended
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB for historical data

## 📄 License

MIT License - see LICENSE file for details.

## 📞 Support & Community

### Getting Help

1. **Check Documentation**: Search docs first
2. **Run Diagnostics**: Use built-in health checks
3. **Check Logs**: Enable DEBUG logging
4. **Community**: Join discussions and contribute

### Reporting Issues

**Bug Reports:**
- Include full error logs
- Describe steps to reproduce
- Note system configuration
- Tag with appropriate labels

**Feature Requests:**
- Describe use case and value
- Include mockups if UI-related
- Reference similar implementations

---

**Built with ❤️ for Indian algorithmic traders**

*Real-time AI trading with institutional-grade reliability*

---

**Last Updated**: January 23, 2026
**Version**: 1.0.0
**Status**: 🟢 Production Ready