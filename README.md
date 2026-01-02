# GenAI Trading System

A fully autonomous multi-agent LLM trading system supporting **multiple instruments** (Bitcoin, Bank Nifty, Nifty 50) with LangGraph orchestration, real-time data ingestion, and self-improving capabilities.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the sample configuration and edit:

```bash
cp .env.example .env  # If .env.example exists
# OR create .env with required settings (see Configuration below)
```

### 3. Setup LLM Provider

**Option A: Local LLM (Recommended - FREE)**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1:8b

# Start Ollama
ollama serve
```

**Option B: Cloud Provider**
Add one of these API keys to `.env`:
- `GROQ_API_KEY` - [Get free key](https://console.groq.com)
- `GOOGLE_API_KEY` - [Get free key](https://aistudio.google.com/app/apikey)
- `OPENROUTER_API_KEY` - [Get free key](https://openrouter.ai)

### 4. Start Services

```bash
# Start MongoDB and Redis
mongod &
redis-server &

# Run the trading system
python scripts/start_all.py
```

### 5. Access Dashboard

Open http://localhost:8888

## Configuration

All configuration is in a single `.env` file:

1. **Copy the template file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and fill in your actual credentials:**
   ```bash
   # LLM Configuration
   LLM_PROVIDER=ollama          # ollama, groq, gemini, openai, together
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.1:8b

   # Instrument Configuration
   INSTRUMENT_SYMBOL=BTC-USD    # BTC-USD, NIFTY BANK, NIFTY 50
   INSTRUMENT_NAME=Bitcoin      # Bitcoin, Bank Nifty, Nifty 50
   DATA_SOURCE=CRYPTO           # CRYPTO, ZERODHA
   MARKET_24_7=true             # true for crypto, false for stocks

   # Database
   MONGODB_URI=mongodb://localhost:27017/
   REDIS_HOST=localhost

   # Trading (start in paper mode!)
   PAPER_TRADING_MODE=true
   ```

**Note:** `.env.example` is a template file that can be safely committed to version control. Your actual `.env` file (with real credentials) is ignored by git and should never be committed.

See [docs/SETUP.md](docs/SETUP.md) for complete configuration options.

## Supported Instruments

| Instrument | Symbol | Data Source | Market Hours |
|------------|--------|-------------|--------------|
| Bitcoin | BTC-USD | Binance WebSocket | 24/7 |
| Bank Nifty | NIFTY BANK | Zerodha Kite | 9:15-15:30 IST |
| Nifty 50 | NIFTY 50 | Zerodha Kite | 9:15-15:30 IST |

Switch instruments:
```bash
python scripts/configure_instrument.py BTC      # Bitcoin
python scripts/configure_instrument.py BANKNIFTY  # Bank Nifty
python scripts/configure_instrument.py NIFTY     # Nifty 50
```

## Architecture

```
Market Data → Data Ingestion → Redis (Memory) → LangGraph Agents → Portfolio Manager → Execution
                                                       ↓
                                              MongoDB (Logs) → Learning Agent
```

### Multi-Agent System

| Agent | Role |
|-------|------|
| **Technical** | Chart patterns, RSI, MACD, support/resistance |
| **Fundamental** | Asset fundamentals, market health |
| **Sentiment** | News sentiment, market mood |
| **Macro** | Economic conditions, risk regime |
| **Bull Researcher** | Constructs bullish thesis |
| **Bear Researcher** | Constructs bearish thesis |
| **Risk Management** | Multi-perspective risk assessment |
| **Portfolio Manager** | Final decision synthesis |
| **Execution** | Order placement |
| **Learning** | Post-trade analysis, prompt refinement |

## Project Structure

```
├── agents/              # All agent implementations
├── config/              # Configuration and prompts
│   ├── settings.py      # Environment configuration
│   └── prompts/         # Agent prompt templates
├── data/                # Data ingestion and storage
├── docs/                # Documentation
├── monitoring/          # Dashboard, alerts, health checks
├── scripts/             # Utility scripts
├── services/            # Unified trading service
├── tests/               # Test suites
├── trading_orchestration/  # LangGraph orchestration
└── utils/               # Utilities (backtesting, paper trading)
```

## Diagnostics

Check system health:
```bash
python scripts/diagnose_llm_system.py
```

This checks:
- LLM provider availability (Ollama, cloud APIs)
- Environment configuration
- Database connections (MongoDB, Redis)
- Instrument configuration

## Safety Features

- **Paper Trading Mode** - Test without real money (default: enabled)
- **Circuit Breakers** - Auto-halt on losses, volatility, API issues
- **Position Limits** - Max position size, leverage controls
- **Stop Losses** - Automatic on all trades
- **Daily Reporting** - Automated P&L reports

## Documentation

| Document | Description |
|----------|-------------|
| [docs/SETUP.md](docs/SETUP.md) | Complete setup instructions |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/AGENTS.md](docs/AGENTS.md) | Agent documentation |
| [docs/DATA_FLOW.md](docs/DATA_FLOW.md) | Data pipeline |
| [docs/API.md](docs/API.md) | API reference |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment |

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
