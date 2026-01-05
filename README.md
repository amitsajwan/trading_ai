# Trading AI System - Modular Architecture

A fully autonomous multi-agent LLM trading system built with **independent domain modules** for maximum maintainability and scalability. Supports real-time market data, intelligent agent orchestration, and risk-managed trade execution.

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

## 🚀 Quick Start

### System Startup Modes

The system supports **3 operational modes** with different data sources and trading capabilities:

#### **Mode 1: Mock Data + Paper Trading** (Current/Default)
```bash
# Install dependencies
pip install -r requirements.txt

# Start data services (Redis + MongoDB)
docker-compose -f docker-compose.data.yml up -d

# Configure mock LLM provider (free)
python scripts/configure_llm_provider.py

# Start dashboard with mock data
python dashboard_pro.py
```
**Features:**
- ✅ Mock market data (BANKNIFTY prices, technical indicators)
- ✅ Paper trading simulation (no real money)
- ✅ Real AI analysis (but with mock market data)
- ✅ Full dashboard functionality
- ✅ Free LLM providers (Groq/OpenAI)

#### **Mode 2: Real Data + Paper Trading** (Recommended for Testing)
```bash
# Same setup as Mode 1, plus:

# Configure Zerodha API for real market data
# Add to .env:
ZERODHA_API_KEY=your_zerodha_api_key
ZERODHA_API_SECRET=your_zerodha_api_secret

# Start with real data
python dashboard_pro.py
```
**Features:**
- ✅ **Real live market data** from Zerodha
- ✅ Real-time price feeds, order book, technical indicators
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
| **data_niftybank** | Market data & options | Redis storage, Kite API, offline testing |
| **genai_module** | LLM client & prompts | Multi-provider support, prompt management |
| **engine_module** | Trading analysis | 9 specialized agents, 15-min cycles |
| **user_module** | Account management | Risk profiles, P&L tracking, trade execution |
| **ui_shell** | Dashboard interface | Data providers, user actions |
| **core_kernel** | Service container | Dependency injection, lifecycle management |

### Module Usage Examples

```python
# Import and use modules independently
from data_niftybank.api import build_store, build_options_client
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
- LLM API access (Groq/OpenAI/Google)

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

The system supports multiple LLM providers with automatic failover. Currently configured for **single provider mode** for optimal performance.

**Available Providers:**
- **Groq** (Recommended - Fastest, Free tier)
- **OpenAI** (GPT-4, Paid)
- **Google** (Gemini, Paid)
- **Anthropic** (Claude, Paid)
- **Local Ollama** (Free, Private)

**Quick Setup (Groq - Free):**
```bash
python scripts/configure_llm_provider.py
```
This configures Groq as the primary provider with automatic optimization.

**Manual Configuration:**
```bash
# Add to .env file:
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key

# Configure single provider mode:
SINGLE_PROVIDER=true
PRIMARY_PROVIDER=groq
```

**Dashboard Provider Display:**
- Currently shows **2 providers** in dashboard (Groq + OpenAI) due to mock metrics
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

### Module Documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and data flow
- **[MODULE_REFACTORING_SUMMARY.md](MODULE_REFACTORING_SUMMARY.md)** - Implementation status
- **[data_niftybank/README.md](data_niftybank/README.md)** - Market data module
- **[engine_module/README.md](engine_module/README.md)** - Trading intelligence
- **[user_module/README.md](user_module/README.md)** - User management
- **[ui_shell/README.md](ui_shell/README.md)** - Dashboard interface
- **[genai_module/README.md](genai_module/README.md)** - LLM integration
- **[core_kernel/README.md](core_kernel/README.md)** - Service infrastructure

### Examples & Demos
- **[examples/](examples/)** - Working code examples
- **[scripts/](scripts/)** - Utility scripts and tools

## 🎯 Key Features

- **Modular Architecture**: 6 independent domain modules
- **Multi-Agent Intelligence**: 9 specialized trading agents
- **Risk Management**: Pre-trade validation and position sizing
- **Real-time Analysis**: 15-minute trading cycles
- **LLM Integration**: Multiple provider support with fallbacks
- **Offline Testing**: Complete test suite without external dependencies
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
**Cause:** Dashboard uses mock LLM metrics (hardcoded to show Groq + OpenAI)
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

## Requirements

- Python 3.9+
- MongoDB
- Redis
- LLM Provider (Ollama local OR cloud API key)

## License

[Your License Here]

## Disclaimer

This system is for educational purposes. Trading involves risk. Always test thoroughly in paper trading mode before using real money. Past performance does not guarantee future results.
