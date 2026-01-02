# Cloud LLM Setup (Fast & Free)

Cloud providers are **much faster** than local Ollama and perfect for verification/testing.

## Quick Setup

```bash
python scripts/setup_cloud_llm.py
```

This script will:
- Detect existing API keys
- Help you configure the fastest provider
- Set up automatic fallback

## Free Providers (Fastest to Slowest)

### 1. Groq ⚡ FASTEST (~1-2 seconds per call)
- **Speed**: Fastest free provider
- **Model**: `llama-3.1-8b-instant` (default)
- **Free Tier**: 30 requests/minute, 100K tokens/day
- **Get Key**: https://console.groq.com
- **Setup**: Add to `.env`:
  ```bash
  GROQ_API_KEY=your_key_here
  LLM_PROVIDER=groq
  GROQ_MODEL=llama-3.1-8b-instant
  ```

### 2. Google Gemini 🚀 Fast (~2-5 seconds per call)
- **Speed**: Very fast
- **Model**: `gemini-flash-latest` (default)
- **Free Tier**: 60 requests/minute, 15M tokens/day
- **Get Key**: https://aistudio.google.com/app/apikey
- **Setup**: Add to `.env`:
  ```bash
  GOOGLE_API_KEY=your_key_here
  LLM_PROVIDER=gemini
  ```

### 3. OpenRouter 📊 Medium (~3-8 seconds per call)
- **Speed**: Medium (depends on model)
- **Model**: `meta-llama/llama-3.2-3b-instruct:free` (default)
- **Free Tier**: Multiple free models available
- **Get Key**: https://openrouter.ai
- **Setup**: Add to `.env`:
  ```bash
  OPENROUTER_API_KEY=your_key_here
  LLM_PROVIDER=openrouter
  OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
  ```

## Multi-Provider Mode (Recommended)

Use multiple providers for automatic fallback:

```bash
LLM_PROVIDER=multi
GROQ_API_KEY=your_key
GOOGLE_API_KEY=your_key
OPENROUTER_API_KEY=your_key
```

The system will:
1. Try Groq first (fastest)
2. Fallback to Gemini if Groq fails
3. Fallback to OpenRouter if both fail
4. Use Ollama as last resort

## Speed Comparison

| Provider | Speed | First Call | Subsequent Calls |
|----------|-------|------------|------------------|
| **Groq** | ⚡⚡⚡ | 1-2s | 1-2s |
| **Gemini** | ⚡⚡ | 2-5s | 2-5s |
| **OpenRouter** | ⚡ | 3-8s | 3-8s |
| Ollama (local) | 🐌 | 30-60s | 5-15s |

## Manual Setup

### Option 1: Edit .env directly

```bash
# Fastest option - Groq
GROQ_API_KEY=your_groq_key_here
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.1-8b-instant

# Or multi-provider (auto-fallback)
LLM_PROVIDER=multi
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_google_key
```

### Option 2: Use environment variables

```bash
# Windows PowerShell
$env:GROQ_API_KEY="your_key"
$env:LLM_PROVIDER="groq"

# Linux/Mac
export GROQ_API_KEY="your_key"
export LLM_PROVIDER="groq"
```

## Verification

After setup, test your configuration:

```bash
# Test LLM
python scripts/test_local_llm.py

# Full verification
python scripts/verify_all_components.py
```

## Troubleshooting

### "No LLM provider selected"
- Check `.env` file has `LLM_PROVIDER` set
- Verify API keys are correct
- Run: `python scripts/setup_cloud_llm.py`

### "Provider failed"
- Check API key is valid
- Verify internet connection
- System will auto-fallback to next provider

### "Rate limit exceeded"
- Wait a few minutes
- System will auto-fallback to next provider
- Or use multi-provider mode for better reliability

## Why Cloud > Local?

| Feature | Cloud (Groq/Gemini) | Local (Ollama) |
|---------|---------------------|----------------|
| **Speed** | 1-5 seconds | 30-60 seconds |
| **Setup** | Just API key | Install + model download |
| **Reliability** | High | Depends on hardware |
| **Parallel Calls** | Handles well | Struggles |
| **First Call** | Fast | Very slow (model loading) |

## Recommended Configuration

For fastest verification and testing:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.1-8b-instant
```

This gives you:
- ⚡ 1-2 second response times
- ✅ Handles parallel calls well
- ✅ No local setup needed
- ✅ Free tier is generous

