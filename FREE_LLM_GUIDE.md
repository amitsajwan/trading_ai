# FREE LLM Providers Guide

## 🎉 Completely FREE Options

### 1. **Ollama** ⭐ RECOMMENDED (100% FREE)

**Best for:** Local development, no rate limits, completely free

**Setup:**
```bash
# 1. Install Ollama
# Windows: Download from https://ollama.com/download
# Mac/Linux: curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a model (choose one)
ollama pull llama3.2:3b        # Small, fast (2GB RAM)
ollama pull llama3.1:8b         # Balanced (4GB RAM)
ollama pull mistral:7b          # Good quality (4GB RAM)
ollama pull qwen2.5:7b         # Alternative (4GB RAM)

# 3. Configure
python scripts/setup_free_llm.py 1
```

**Pros:**
- ✅ 100% FREE forever
- ✅ No rate limits
- ✅ No API keys needed
- ✅ Runs locally (privacy)
- ✅ Works offline

**Cons:**
- ❌ Requires local GPU/RAM (4-8GB recommended)
- ❌ Slower than cloud APIs

**Models:**
- `llama3.2:3b` - Fastest, smallest
- `llama3.1:8b` - Balanced
- `mistral:7b` - Good quality
- `qwen2.5:7b` - Alternative

---

### 2. **Hugging Face Inference API** (FREE Tier)

**Best for:** Cloud-based, easy setup

**Setup:**
```bash
# 1. Get free API key: https://huggingface.co/settings/tokens
# 2. Configure
python scripts/setup_free_llm.py 2
```

**Free Tier Limits:**
- ✅ 1000 requests/day
- ✅ No credit card needed
- ✅ Multiple models available

**Models:**
- `meta-llama/Llama-3.2-3B-Instruct`
- `mistralai/Mistral-7B-Instruct-v0.2`
- `microsoft/Phi-3-mini-4k-instruct`

**Get API Key:** https://huggingface.co/settings/tokens

---

### 3. **Together AI** (FREE Tier)

**Best for:** High-quality models, generous free tier

**Setup:**
```bash
# 1. Sign up: https://api.together.xyz/
# 2. Get API key
# 3. Configure
python scripts/setup_free_llm.py 3
```

**Free Tier:**
- ✅ $25 free credits
- ✅ No credit card needed initially
- ✅ Access to Llama-3-70B, Mistral, etc.

**Get API Key:** https://api.together.xyz/

---

### 4. **Google Gemini** (FREE Tier)

**Best for:** Google's models, good quality

**Setup:**
```bash
# 1. Get API key: https://aistudio.google.com/app/apikey
# 2. Configure
python scripts/setup_free_llm.py 4
```

**Free Tier Limits:**
- ✅ 60 requests/minute
- ✅ 1,500 requests/day
- ✅ No credit card needed

**Models:**
- `gemini-pro` - Standard
- `gemini-pro-vision` - With vision

**Get API Key:** https://aistudio.google.com/app/apikey

---

## Quick Comparison

| Provider | Cost | Rate Limits | Setup Difficulty | Quality |
|----------|------|-------------|------------------|---------|
| **Ollama** | FREE | None | Medium | Good |
| Hugging Face | FREE | 1000/day | Easy | Good |
| Together AI | FREE | $25 credits | Easy | Excellent |
| Google Gemini | FREE | 1500/day | Easy | Excellent |

## Recommendation

**For immediate use:** **Ollama** (if you have 4-8GB RAM)
- Completely free
- No rate limits
- Privacy (runs locally)

**For cloud:** **Together AI** or **Google Gemini**
- Better quality
- Easy setup
- Generous free tiers

## After Setup

Restart your trading service:
```bash
# Stop current services
Get-Process python | Stop-Process -Force

# Start again
python scripts/start_all.py
```

## Troubleshooting

**Ollama not starting?**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama service
ollama serve
```

**Rate limits?**
- Switch to Ollama (no limits)
- Or wait for daily reset
- Or upgrade to paid tier

