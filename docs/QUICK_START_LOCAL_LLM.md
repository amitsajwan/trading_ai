# Quick Start: Local LLM Setup

## Why Local LLM?

Your system is currently hitting rate limits on cloud providers:
- ❌ Groq: Rate limited (100K tokens/day)
- ❌ OpenRouter: Rate limited (50 requests/day free tier)
- ⚠️ Gemini: Working but may hit quotas

**Solution**: Run LLM locally with **Ollama** - no rate limits, free, fast!

## 5-Minute Setup

### Step 1: Install Ollama

**Windows**:
1. Download: https://ollama.com/download/windows
2. Run installer
3. Restart terminal

**Linux/Mac**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Pull Model

```bash
# Recommended: Llama 3.1 8B (best balance)
ollama pull llama3.1:8b

# Or faster: Mistral 7B
ollama pull mistral:7b

# Or smallest: Phi-3
ollama pull phi3:3.8b
```

### Step 3: Update .env

Add to your `.env` file:
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

### Step 4: Test

```bash
# Start Ollama (if not running)
ollama serve

# Test in another terminal
python -c "from agents.llm_provider_manager import LLMProviderManager; m = LLMProviderManager(); print(m.call_llm('You are a trader.', 'Analyze Bank Nifty'))"
```

### Step 5: Restart System

```bash
python scripts/stop_all.py
python scripts/start_all.py
```

## Automated Setup

Or use the setup script:
```bash
python scripts/setup_local_llm.py
```

## Model Comparison

| Model | Size | Speed | Quality | RAM Needed |
|-------|------|-------|---------|------------|
| **llama3.1:8b** ⭐ | 4.7GB | Fast | Excellent | 8GB+ |
| mistral:7b | 4.1GB | Very Fast | Good | 8GB+ |
| phi3:3.8b | 2.3GB | Fastest | Good | 4GB+ |
| llama3.1:70b | 40GB | Slow | Best | 64GB+ |

**Recommendation**: Start with `llama3.1:8b` - best balance.

## Performance

- **Inference Time**: 1-3 seconds per call (on CPU), <1s (on GPU)
- **Rate Limits**: None (local)
- **Cost**: Free
- **Privacy**: 100% (data never leaves your machine)

## Troubleshooting

### Ollama not starting?
```bash
# Check if running
curl http://localhost:11434/api/tags

# Start manually
ollama serve
```

### Slow inference?
- Use GPU: `ollama run llama3.1:8b` (auto-detects GPU)
- Use smaller model: `phi3:3.8b`
- Use quantized model (Q4/Q5)

### Out of memory?
- Use smaller model: `phi3:3.8b`
- Close other applications
- Reduce batch size

## Next Steps

1. ✅ Setup complete - system will use local LLM
2. Monitor performance in logs
3. Adjust model size based on needs
4. Consider GPU for faster inference

## Benefits

- ✅ **No Rate Limits**: Unlimited calls
- ✅ **Free**: No API costs
- ✅ **Fast**: Local inference (<1s on GPU)
- ✅ **Private**: Data stays local
- ✅ **Reliable**: No external dependencies

Your system will now work reliably without hitting rate limits!

