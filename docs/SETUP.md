# Setup Guide

This guide covers installation, configuration, and getting started with the GenAI Trading System.

## Prerequisites

- **Python 3.9+**
- **MongoDB** (local or Docker)
- **Redis** (local or Docker)
- **LLM Provider** (Ollama local OR cloud API key)

## Installation

### 1. Clone and Setup Environment

```bash
git clone <repository-url>
cd zerodha
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the appropriate environment file for your instrument:

```bash
# For Bitcoin trading
cp .env.btc .env

# For Bank Nifty trading
cp .env.banknifty .env

# For Nifty 50 trading
cp .env.nifty .env
```

Edit `.env` and add your API keys:

```bash
# LLM Provider (choose one)
GROQ_API_KEY=your_groq_key_here
# OR
OPENAI_API_KEY=your_openai_key_here
# OR
GOOGLE_API_KEY=your_google_key_here

# Trading APIs
KITE_API_KEY=your_zerodha_key
KITE_API_SECRET=your_zerodha_secret
# OR for crypto
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret

# News APIs
NEWS_API_KEY=your_news_api_key
```

### 3. Setup Credentials

For Zerodha trading:
```bash
cp credentials.example.json credentials.json
# Edit credentials.json with your Zerodha login details
# OR run auto-login
python auto_login.py
```

## Database Setup

### Option A: Local Installation

```bash
# MongoDB
mongod --dbpath /path/to/data

# Redis (in another terminal)
redis-server
```

### Option B: Docker (Recommended)

```bash
# Start databases
docker run -d --name mongodb -p 27017:27017 mongo:7
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

## LLM Setup

### Option A: Local Ollama (Free)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1:8b

# Start Ollama
ollama serve
```

Set in `.env`:
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

### Option B: Cloud Provider

Add API key to `.env`:
```bash
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

## Testing Setup

```bash
# Run tests
python -m pytest tests/ -v

# Check system health
python scripts/diagnose_llm_system.py
```

## Starting the System

### Single Instrument Mode

```bash
# Start with specific instrument
python scripts/start_all.py --instrument BTC
python scripts/start_all.py --instrument BANKNIFTY
python scripts/start_all.py --instrument NIFTY
```

### Multi-Instrument Mode (Docker)

```bash
# Start all instruments simultaneously
manage_trading.bat start all

# Start individual systems
manage_trading.bat start btc
manage_trading.bat start banknifty
manage_trading.bat start nifty
```

## Dashboard Access

- **Single Mode**: http://localhost:8888
- **Multi Mode**:
  - BTC: http://localhost:8001
  - Bank Nifty: http://localhost:8002
  - Nifty 50: http://localhost:8003

## Troubleshooting

### Common Issues

1. **LLM Not Working**
   ```bash
   python scripts/diagnose_llm_system.py
   ```

2. **Database Connection Failed**
   ```bash
   # Check MongoDB
   mongosh --eval "db.adminCommand('ping')"

   # Check Redis
   redis-cli ping
   ```

3. **API Keys Invalid**
   - Verify keys in `.env` file
   - Check API key permissions
   - Test with minimal script

4. **Paper Trading Mode**
   - System starts in paper mode by default
   - Set `PAPER_TRADING_MODE=false` for live trading (⚠️ Use with caution)

## Configuration Validation

Run the diagnostic script to verify everything is configured correctly:

```bash
python scripts/diagnose_llm_system.py
```

This checks:
- Environment variables
- API key validity
- Database connections
- LLM provider availability
- Instrument configuration