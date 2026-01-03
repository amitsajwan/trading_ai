# Documentation Index

Welcome to the GenAI Trading System documentation.

## Core Documentation

| Document | Description |
|----------|-------------|
| [SETUP.md](SETUP.md) | Installation, configuration, and quick start |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and design |
| [AGENTS.md](AGENTS.md) | Agent documentation and responsibilities |
| [DATA_FLOW.md](DATA_FLOW.md) | Data pipeline and signal flow |
| [API.md](API.md) | REST API reference |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment guide |

## Configuration Guides

| Document | Description |
|----------|-------------|
| [INSTRUMENT_CONFIGURATION.md](INSTRUMENT_CONFIGURATION.md) | How to configure different instruments (BTC, Bank Nifty) |
| [CRYPTO_DATA_FEED.md](CRYPTO_DATA_FEED.md) | Crypto data feed setup (Binance WebSocket) |

## Reference

| Document | Description |
|----------|-------------|
| [CURRENT_ISSUES.md](CURRENT_ISSUES.md) | Known issues and limitations |
| [CHANGELOG.md](CHANGELOG.md) | Version history and changes |

## Quick Links

- **[Main README](../README.md)** - Project overview and quick start
- **[Diagnostic Script](../scripts/diagnose_llm_system.py)** - Check system health

## Archived Documents (Removed)

A set of historical or draft documents were archived and later **removed** from the top-level docs directory on 2026-01-03 to reduce clutter. The compressed backups were permanently deleted on 2026-01-03 and are no longer available in the repository; contact maintainers to request restores.

If you need a specific archived document, extract the zip or contact the repository maintainers to restore it to `docs/`.


## Getting Started

1. **New Users**: Start with [SETUP.md](SETUP.md)
2. **Understanding the System**: Read [ARCHITECTURE.md](ARCHITECTURE.md)
3. **Configuring Instruments**: See [INSTRUMENT_CONFIGURATION.md](INSTRUMENT_CONFIGURATION.md)
4. **Production Deployment**: Follow [DEPLOYMENT.md](DEPLOYMENT.md)

## LLM Configuration

The system supports multiple LLM providers with automatic fallback:

### Local LLM (Ollama) - Recommended
```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3.1:8b

# Start
ollama serve
```

### Cloud Providers (Free Tiers Available)

| Provider | Free Tier | Get API Key |
|----------|-----------|-------------|
| **Groq** | 100K tokens/day | [console.groq.com](https://console.groq.com) |
| **Google Gemini** | 1500 req/day | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **OpenRouter** | Limited free | [openrouter.ai](https://openrouter.ai) |
| **Together AI** | $25 credits | [api.together.xyz](https://api.together.xyz) |

Add API key to `.env`:
```bash
GROQ_API_KEY=your_key_here
# OR
GOOGLE_API_KEY=your_key_here
```

The system automatically falls back between providers if one hits rate limits.

## Troubleshooting

Run diagnostics:
```bash
python scripts/diagnose_llm_system.py
```

This checks:
- ✅ Environment configuration
- ✅ LLM provider availability
- ✅ Database connections
- ✅ Instrument configuration
