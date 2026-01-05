# Documentation Index

Welcome to the GenAI Trading System documentation.

## Core Documentation

| Document | Description |
|----------|-------------|
| [SETUP.md](SETUP.md) | Installation, configuration, and quick start |
| [INSTRUMENT_CONFIGURATION.md](INSTRUMENT_CONFIGURATION.md) | **Docker multi-instrument setup** |
| [DEPLOYMENT.md](DEPLOYMENT.md) | **Docker production deployment** |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and design |
| [AGENTS.md](AGENTS.md) | Agent documentation and responsibilities |
| [DATA_FLOW.md](DATA_FLOW.md) | Data pipeline and signal flow |
| [API.md](API.md) | REST API reference |

## Configuration Guides

| Document | Description |
|----------|-------------|
| [INSTRUMENT_CONFIGURATION.md](INSTRUMENT_CONFIGURATION.md) | How to configure different instruments (BTC, Bank Nifty) |

## Quick Reference

| Document | Description |
|----------|-------------|
| [ESSENTIALS.md](ESSENTIALS.md) | Quick start essentials |

## Quick Links

- **[Main README](../README.md)** - Project overview and quick start
- **[Diagnostic Script](../scripts/diagnose_llm_system.py)** - Check system health

## Archived Documents

Historical implementation and fix documentation has been archived in the `archived/` folder. These contain specific development notes, bug fixes, and implementation details that are no longer current but preserved for reference.

If you need a specific archived document, check the `docs/archived/` folder.

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
