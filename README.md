# Trading AI System - Advanced Conditional Execution

A fully autonomous multi-agent LLM trading system with **sophisticated conditional execution** capabilities. Features intelligent position-aware agents, real-time technical condition monitoring, and risk-managed automated trading. Supports live market data integration and advanced paper trading simulation.

## 🚀 Key Features

### ✅ Advanced Conditional Execution
- **Technical Condition Monitoring**: Orders execute based on RSI, volume, MACD, ADX, and moving averages
- **Position-Aware Agents**: Intelligent feedback for closing positions and adding to positions
- **Real-Time Risk Management**: Dynamic stop-loss and take-profit based on technical levels
- **Multi-Agent Consensus**: Combined signals from Momentum, Trend, Mean Reversion, and Volume agents

### ✅ Professional Trading Interface
- **Trading Cockpit**: Complete control panel with signal management
- **Live Condition Monitoring**: Real-time technical indicator status
- **Automated Execution**: "Execute When Ready" functionality
- **Performance Analytics**: Win rates, P&L tracking, Sharpe ratios

### ✅ Modular Architecture
- **Independent Domain Modules**: Data, Engine, User, GenAI, Core, UI
- **Scalable Design**: Easy to extend with new agents and strategies
- **Production Ready**: Comprehensive error handling and logging

## 🏗️ Architecture Overview

This system follows a **modular architecture** with 6 independent domain modules:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  UI Shell   │    │   Engine    │    │   User     │
│ (Dashboard) │◄──►│ (Analysis)  │◄──►│ (Trading)  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Data Module │    │ GenAI       │    │ Core       │
│ (Market)    │    │ (LLM)       │    │ (Services) │
└─────────────┘    └─────────────┘    └─────────────┘
```

## ⏰ Time Synchronization Architecture

### Centralized Virtual Time System
All Docker components synchronize via Redis-backed virtual time for historical replay and backtesting:

```
Redis (Source of Truth)
  ├─ system:virtual_time:enabled = 1
  └─ system:virtual_time:current = 2026-01-06T10:00:00+05:30
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
  Dashboard    Orchestrator   HistReplay    MarketData
  (app.py)     (run_orch.py)  (replayer)    (live_data)
       │              │              │              │
  TimeService    TimeService    Sets Time     Uses Time
  .now()         .now()         in Redis      from Redis
```

### Time Service API
- `get_system_time()` / `now()` - Read current time (virtual or real)
- `set_virtual_time(datetime)` - Set virtual time in Redis for replay
- `clear_virtual_time()` - Clear virtual time, return to real-time
- `is_virtual_time()` - Check if virtual time is active

### Market Hours Integration
- **Market Hours**: Monday-Friday, 9:15 AM - 3:30 PM IST
- **Automatic Blocking**: Orchestrator checks `is_market_open()` before each cycle
- **Virtual Time Support**: Market hours checks use virtual time when enabled
- **Agent Pause**: All agents and LLM calls stop when market is closed
- **Timezone Handling**: Internal UTC, Storage IST, Display IST (+05:30)

**Benefits**:
- ✅ All components synchronized on same virtual time
- ✅ Historical replay works across entire system
- ✅ Market hours respected in all modes
- ✅ No API costs when market closed
- ✅ Consistent time across Docker containers

## 🤖 Advanced Conditional Execution System

### Intelligent Multi-Agent Trading
The system employs **4 specialized AI agents** working in concert:

#### **Momentum Agent**
- **Entry**: RSI > 70 + Volume 50% above average
- **Exit**: RSI < 50 or 2% trailing stop
- **Strategy**: Captures momentum breakouts with volume confirmation

#### **Trend Agent**
- **Entry**: Price breaks above/below 20SMA + ADX > 25
- **Exit**: Price closes above/below SMA
- **Strategy**: Follows established trends with strength confirmation

#### **Mean Reversion Agent**
- **Entry**: Price touches Bollinger Bands + RSI extremes
- **Exit**: Price reaches band middle (partial exit)
- **Strategy**: Profits from overbought/oversold conditions

#### **Volume Agent**
- **Entry**: Volume spikes 3x average + price action
- **Exit**: Volume exhaustion + profit targets
- **Strategy**: Identifies institutional activity and liquidity events

### Conditional Execution Features
- **Technical Triggers**: Orders execute only when RSI, volume, MACD, ADX conditions are met
- **Position Awareness**: Agents consider current positions for intelligent feedback
- **Risk Management**: Dynamic stops based on technical levels, not fixed prices
- **Real-Time Monitoring**: Live condition checking every 15 seconds
- **Consensus System**: Multiple agent agreement required for high-confidence signals

### Trading Cockpit Interface
- **Signal Management**: Execute, modify, or reject signals with full context
- **Live Conditions**: Real-time display of technical indicator status
- **Position Tracking**: P&L monitoring with automated exit management
- **Performance Analytics**: Win rates, Sharpe ratios, drawdown analysis
- **Risk Controls**: Portfolio limits, position sizing, emergency stops

### Dashboard Navigation
The system provides **6 comprehensive dashboard tabs**:

#### **System Overview**
- Overall system health and database status
- Market open/closed status and trading hours
- System performance metrics and uptime

#### **Trading Cockpit**
- Manual trading cycle execution
- Risk management controls and portfolio limits
- Quick action buttons for system management

#### **Pending Signals**
- Live signal display with technical conditions
- Execute Now vs Execute When Ready options
- Real-time condition status and monitoring
- Manual signal approval and modification

#### **Active Positions**
- Live P&L tracking for open positions
- Automated exit management based on technical levels
- Position modification and scaling options

#### **Performance**
- Comprehensive trading statistics and analytics
- Win rate analysis and Sharpe ratio tracking
- Agent performance breakdown and comparison

#### **Full Dashboard**
- Complete market data with technical indicators
- Agent decision summaries and consensus signals
- Recent trade history and position tracking
- Advanced system status and health monitoring

## 🚀 Quick Start

### System Startup Modes

The system supports **3 operational modes** with different data sources and trading capabilities:

#### **Mode 1: Mock Data + Conditional Paper Trading** (Enhanced/Default)
```bash
# Install dependencies
pip install -r requirements.txt

# Start data services (Redis + MongoDB)
docker-compose -f docker-compose.data.yml up -d

# Configure mock LLM provider (free)
python scripts/configure_llm_provider.py

# Start enhanced dashboard with conditional execution
python dashboard_pro.py
```
**Features:**
- ✅ **Advanced Conditional Execution**: Orders execute based on technical conditions
- ✅ **Position-Aware Agents**: Smart feedback for position management
- ✅ **Real-Time Technical Monitoring**: Live RSI, volume, MACD, ADX tracking
- ✅ **Mock Market Data**: BANKNIFTY with realistic technical indicators
- ✅ **Paper Trading Simulation**: No real money risk
- ✅ **Full AI Analysis**: Multi-agent decision making
- ✅ **Professional Dashboard**: Trading cockpit with signal management
- ✅ **Production LLM Providers**: Groq/Cohere/AI21 with multi-key load balancing

### Running locally with provider selection (mock or Zerodha)

You can switch between **mock/simulator** and **Zerodha** providers without changing code. The `providers` factory picks the provider based on CLI or env vars.

- CLI (preferred for single-run):
  - python start_local.py --provider mock
  - python start_local.py --provider zerodha

- Env (session or CI):
  - USE_MOCK_KITE=1 (forces mock)
  - TRADING_PROVIDER=mock|zerodha

- Start collectors in mock mode (exercise collector code paths, not generator):
  - PowerShell:
    - $env:USE_MOCK_KITE = '1'
    - python -m market_data.collectors.ltp_collector
    - python -m market_data.collectors.depth_collector
  - Bash:
    - USE_MOCK_KITE=1 python -m market_data.collectors.ltp_collector & USE_MOCK_KITE=1 python -m market_data.collectors.depth_collector &

- Docker Compose mock override (starts services in mock mode):
  - docker compose -f docker-compose.yml -f docker-compose.mock.yml up -d

- Quick smoke tools and verification:
  - Emit a single tick: python scripts/emit_mock_tick.py
  - Run verification: python verify_market_data.py
  - Start a full mock runbook (Windows): .\scripts\start_mock.ps1
### Historical replay mode (time-travel simulation)

You can run the system using historical market data and replay it as if it were "now". The replayer sets a system virtual time so the rest of the system (strategies, dashboard, health checks) sees historical ticks as live events.

- Start local with historical replay (bar-level):
  - python start_local.py --provider historical --historical-source synthetic --historical-speed 1.0

- Start tick-level replay (more realistic, preserves per-tick timestamps):
  - python start_local.py --provider historical --historical-source /path/to/data.csv --historical-ticks --historical-from 2024-01-15 --historical-speed 1.0

Notes:
- `--historical-source` accepts `synthetic`, a path to a JSON/CSV file, or `zerodha` (when you have archived API access).
- `--historical-from` (YYYY-MM-DD) limits the start of the replay (tick-level replayer supports `from_date`).
- `--historical-speed` (float) controls playback speed: `1.0` = real-time, `2.0` = 2x.
- Replayer will set `system:virtual_time:enabled` and `system:virtual_time:current` keys in Redis during replay.
Notes:
- Precedence: `--provider` CLI > `TRADING_PROVIDER` env var > `USE_MOCK_KITE=1` > auto (try Zerodha creds, fallback to mock).
- `USE_MOCK_KITE=1` **overrides** credentials to prevent accidental live calls during testing.

#### **Mode 2: Live Bank Nifty + Paper Trading** (Recommended for Live Testing)
```bash
# Install dependencies
pip install -r requirements.txt

# Set up Zerodha API credentials in .env file
echo "KITE_API_KEY=anbel41tccg186z0" > .env
echo "KITE_API_SECRET=hvfug2sn5h1xe1ky3qbuj1gsntd9kk86" >> .env

# Authenticate with Kite (opens browser for login)
python data_niftybank/src/data_niftybank/tools/kite_auth.py

# Start with live data integration
python dashboard_pro.py
```
**Features:**
- ✅ **Live Bank Nifty Data**: Real-time price feeds from Zerodha Kite API
- ✅ **WebSocket Streaming**: Live tick data and order book updates
- ✅ **Real Options Data**: Live options chains and Greeks calculations
- ✅ **Paper Trading**: Risk-free testing with live market conditions
- ✅ **Advanced Conditional Execution**: Technical triggers with live data
- ✅ **Position-Aware Agents**: Smart feedback using real market positions
- ✅ **Live Risk Management**: Real-time P&L and exposure monitoring
- ✅ **Automatic Fallback**: Falls back to simulated data if live connection fails
- ✅ Paper trading with real market conditions
- ✅ AI analysis on live data
- ⚠️ Requires Zerodha API credentials

#### **Mode 3: Real Data + Real Trading** (Production)
```bash
# Same as Mode 2, plus:

# Enable real trading in user module
# Configure risk limits and trading permissions

# Start automatic trading service
python automatic_trading_service.py
```
**Features:**
- ✅ Real market data
- ✅ **Real money trading** with risk management
- ✅ Automatic trade execution based on AI signals
- ✅ Live P&L tracking
- ⚠️ **Requires real trading account and capital**
- ⚠️ **High risk - use only with proper risk management**

### Local Development (Mode 1)
```bash
# Quick setup for development
pip install -r requirements.txt
docker-compose -f docker-compose.data.yml up -d
python scripts/configure_llm_provider.py
python dashboard_pro.py
```

## 📦 Module Overview

### Core Modules

| Module | Purpose | Key Features |
|--------|---------|--------------|
| **market_data** | Universal market data | Instrument-agnostic, Redis storage, Kite API, offline testing |
| **genai_module** | LLM client & prompts | Multi-provider support, prompt management |
| **engine_module** | Trading analysis | 9 specialized agents, 15-min cycles |
| **user_module** | Account management | Risk profiles, P&L tracking, trade execution |
| **ui_shell** | Dashboard interface | Data providers, user actions |
| **core_kernel** | Service container | Dependency injection, lifecycle management |

### Module Usage Examples

```python
# Import and use modules independently
from market_data.api import build_store, build_options_client
from genai_module.api import build_llm_client
from engine_module.api import build_orchestrator

# Build components with dependency injection
store = build_store(redis_client=redis)
llm = build_llm_client(legacy_manager=llm_manager)
orchestrator = build_orchestrator(llm_client=llm, market_store=store)

# Run analysis cycle
result = await orchestrator.run_cycle({"instrument": "BANKNIFTY"})
print(f"Decision: {result.decision} (confidence: {result.confidence:.1%})")
```

## 🤖 Trading Intelligence

The system features **9 specialized agents** working in parallel:

- **Technical Agent**: Chart patterns, indicators, trend analysis
- **Sentiment Agent**: News analysis, market psychology
- **Macro Agent**: Economic indicators, policy impact
- **Risk Agent**: Position sizing, loss limits
- **Execution Agent**: Order validation, slippage analysis
- **Portfolio Manager**: Signal aggregation, final decisions
- **Review Agent**: Performance analysis, reporting
- **Fundamental Agent**: Company valuation, earnings analysis
- **Learning Agent**: Strategy optimization, adaptation

## 🧪 Testing & Quality

```bash
# Run all tests (126 unit tests)
pytest

# Run specific module tests
pytest data_niftybank/tests/ -v
pytest engine_module/tests/ -v

# Run integration tests
pytest -m integration
```

## 🔧 Development

### Prerequisites
- Python 3.9+
- Redis (for data storage)
- MongoDB (for persistence)
- LLM API access (Groq/Cohere/AI21)

### Environment Setup
```bash
# Clone repository
git clone <repo>
cd zerodha

# Install dependencies
pip install -r requirements.txt

# Start external services
docker-compose -f docker-compose.data.yml up -d

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run tests
pytest

# Start development
python dashboard_pro.py
```

## ⚙️ Configuration

### LLM Provider Setup (Optimized)
The system is pre-configured for optimal performance using **single provider mode**:

```bash
# Run configuration script (recommended)
python scripts/configure_llm_provider.py

# Or manually set in .env:
SINGLE_PROVIDER=true
PRIMARY_PROVIDER=groq
LLM_SELECTION_STRATEGY=single
GROQ_API_KEY=GROQ_API_KEY_REDACTED
```

### Environment Variables
```bash
# Database (auto-started with docker-compose)
MONGODB_URI=mongodb://localhost:27017/
REDIS_HOST=localhost
REDIS_PORT=6379

# Optional: Zerodha API for live data
ZERODHA_API_KEY=your_zerodha_key
ZERODHA_API_SECRET=your_zerodha_secret
```

### Test LLM Providers
```bash
# Test all configured API keys
python scripts/test_api_keys.py
```

### LLM Provider Setup

The system uses **3 production-grade LLM providers** with multi-key load balancing for high throughput and reliability.

**Configured Providers:**
- **Groq** (Primary - llama-3.1-70b-versatile, Fastest, Free tier)
- **Cohere** (Secondary - command-r-plus, Enterprise-grade)
- **AI21** (Tertiary - jamba-instruct, Advanced reasoning)

**Quick Setup:**
```bash
python scripts/configure_llm_provider.py
```
This configures the 3 production providers with automatic load balancing.

**Manual Configuration:**
```bash
# Add to .env file (supports multiple keys per provider):
GROQ_API_KEY=your_groq_key
GROQ_API_KEY_2=your_second_groq_key
COHERE_API_KEY=your_cohere_key
COHERE_API_KEY_2=your_second_cohere_key
AI21_API_KEY=your_ai21_key
AI21_API_KEY_2=your_second_ai21_key

# Multi-key load balancing automatically distributes requests
```

**Dashboard Provider Display:**
- Currently shows **3 providers** in dashboard (Groq + Cohere + AI21)
- Real metrics would show all configured providers
- Provider status shows actual usage, rate limits, and error states

**Local LLM (Free & Private):**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
ollama serve  # Runs on localhost:11434
```

### External Services
```bash
# Start Redis + MongoDB
docker-compose -f docker-compose.data.yml up -d

# Check services are running
docker-compose -f docker-compose.data.yml ps
```

## 📖 Documentation

**Quick Access**: See **[DOCS_INDEX.md](DOCS_INDEX.md)** for complete documentation guide.

### Core Documentation (7 files, 82KB total)

| Document | Purpose | Size |
|----------|---------|------|
| **[README.md](README.md)** (this file) | System overview, installation, quick start | 21KB |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System design, modules, data flow | 15KB |
| **[FEATURES.md](FEATURES.md)** | Signal-to-trade, indicators, multi-agent, virtual time | 12KB |
| **[TESTING.md](TESTING.md)** | Test suite, virtual time testing, troubleshooting | 9KB |
| **[TRADING_COCKPIT.md](TRADING_COCKPIT.md)** | Dashboard UI guide, controls, API endpoints | 10KB |
| **[ZERODHA_DATA_STRUCTURES.md](ZERODHA_DATA_STRUCTURES.md)** | Kite API data formats | 11KB |
| **[ZERODHA_HISTORICAL_INTEGRATION.md](ZERODHA_HISTORICAL_INTEGRATION.md)** | Historical data integration | 4KB |

### Module-Specific Docs
- **[data_niftybank/README.md](data_niftybank/README.md)** - Market data module
- **[engine_module/README.md](engine_module/README.md)** - Trading intelligence
- **[user_module/README.md](user_module/README.md)** - User management
- **[ui_shell/README.md](ui_shell/README.md)** - Dashboard interface
- **[genai_module/README.md](genai_module/README.md)** - LLM integration
- **[core_kernel/README.md](core_kernel/README.md)** - Service infrastructure

### Feature Guides
- **Real-time Signals**: [FEATURES.md#real-time-signal-to-trade](FEATURES.md#real-time-signal-to-trade)
- **Technical Indicators**: [FEATURES.md#technical-indicators-integration](FEATURES.md#technical-indicators-integration)
- **Historical Replay**: [FEATURES.md#historical-mode--replay](FEATURES.md#historical-mode--replay)
- **Multi-Agent System**: [FEATURES.md#multi-agent-system](FEATURES.md#multi-agent-system)
- **Virtual Time**: [FEATURES.md#virtual-time-synchronization](FEATURES.md#virtual-time-synchronization)

## 🎯 Key Features

### Advanced Conditional Execution
- **Technical Condition Monitoring**: Orders execute based on RSI, volume, MACD, ADX, Bollinger Bands
- **Position-Aware Agents**: Intelligent feedback for closing positions and scaling trades
- **Real-Time Risk Management**: Dynamic stops based on technical levels, not fixed prices
- **Multi-Agent Consensus**: Combined signals from 4 specialized trading agents

### Professional Trading Interface
- **Trading Cockpit**: Complete control panel with signal management and execution
- **Live Condition Monitoring**: Real-time technical indicator status and alerts
- **Automated Execution**: "Execute When Ready" functionality with condition waiting
- **Performance Analytics**: Win rates, P&L tracking, Sharpe ratios, drawdown analysis

### Core System Capabilities
- **Modular Architecture**: 6 independent domain modules for maximum maintainability
- **Multi-Agent Intelligence**: 4 specialized trading agents (Momentum, Trend, Mean Reversion, Volume)
- **Risk Management**: Pre-trade validation, position sizing, portfolio limits
- **Real-time Analysis**: 15-minute trading cycles with continuous monitoring
- **LLM Integration**: Multiple provider support with intelligent fallbacks
- **Live Market Data**: Real-time Bank Nifty data from Zerodha Kite API
- **Paper Trading**: Full simulation with realistic market conditions
- **Production Ready**: Docker deployment with proper service isolation

## 📈 Architecture Benefits

- **Maintainability**: Clear separation of concerns
- **Scalability**: Independent module deployment
- **Testability**: Comprehensive unit and integration tests
- **Extensibility**: Easy to add new agents or data sources
- **Reliability**: Fault isolation between modules

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Run tests** (`pytest`)
4. **Commit** your changes (`git commit -m 'Add amazing feature'`)
5. **Push** to the branch (`git push origin feature/amazing-feature`)
6. **Open** a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔧 Troubleshooting

### Dashboard Shows "HOLD" with Low Confidence
**Cause:** System is using mock analysis data (no recent real analysis)
**Solution:**
```bash
# Run real AI analysis
python insert_realistic_analysis.py
# Then refresh dashboard
```

### Only 2 LLM Providers Shown in Dashboard
**Cause:** Dashboard uses mock LLM metrics (hardcoded to show Groq + Cohere + AI21)
**Real Behavior:** Would show all configured providers with actual usage stats
**Check Config:**
```bash
python scripts/test_api_keys.py  # Shows all configured providers
```

### Cannot Connect to Real Market Data
**Cause:** Missing Zerodha API credentials
**Solution:**
```bash
# Add to .env:
ZERODHA_API_KEY=your_key
ZERODHA_API_SECRET=your_secret
```

### Import Errors When Running Scripts
**Cause:** Python path issues with modular structure
**Solution:** Scripts automatically add paths, but for manual imports:
```python
import sys
sys.path.insert(0, 'data_niftybank/src')
sys.path.insert(0, 'engine_module/src')
# ... etc
```

## ⚠️ Disclaimer

This software is for educational and research purposes only. Not intended for actual trading without proper testing and risk assessment. Trading involves substantial risk of loss and is not suitable for every investor.

**Mode 1 (Mock + Paper)**: Safe for learning and development
**Mode 2 (Real Data + Paper)**: Good for strategy testing
**Mode 3 (Real Trading)**: Use only with comprehensive risk management

---

**Built with ❤️ for algorithmic trading research and education**

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

## 🎯 **Current Status: Live Zerodha Integration Complete**

**✅ INTEGRATED**: The system now uses the `data_niftybank` module for live Zerodha data
**✅ AUTHENTICATION**: Set up with provided Kite API credentials
**✅ LIVE DATA**: BANKNIFTY prices updating from Zerodha LTP API every 30 seconds
**✅ LIVE UI**: Dashboard displays real-time prices, not hardcoded values
**✅ FALLBACK**: Automatically uses simulated data when live connection unavailable
**✅ PRODUCTION READY**: Full paper trading with conditional execution

**To enable live data:** Run `python data_niftybank/src/data_niftybank/tools/kite_auth.py` and authenticate via browser.

## Requirements

- Python 3.9+
- MongoDB (for trade history and agent decisions)
- Redis (for virtual time synchronization and market data)
- Docker & Docker Compose (for containerized deployment)
- LLM Provider (Groq/Cohere/AI21 API keys)
- Python packages: `pytz` (timezone handling), `fastapi`, `pymongo`, `redis`

## License

[Your License Here]

## Disclaimer

This system is for educational purposes. Trading involves risk. Always test thoroughly in paper trading mode before using real money. Past performance does not guarantee future results.

