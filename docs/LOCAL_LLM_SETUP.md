# Local LLM Setup Guide

## Why Local LLM?

### Current Issues
- Rate limits on free cloud providers (Groq, OpenRouter, Gemini)
- Cost concerns for high-frequency trading analysis
- Privacy/security for proprietary trading strategies
- Latency for real-time decisions

### Benefits of Local LLM
- ✅ No rate limits
- ✅ No API costs
- ✅ Data privacy
- ✅ Low latency (local inference)
- ✅ Full control

## Recommended Solutions

### Option 1: Ollama (Recommended for Quick Setup)

**Best For**: Development, testing, moderate throughput

**Pros**:
- Easiest setup (one command)
- Supports quantized models (Q4/Q5)
- Good model selection
- Cross-platform

**Cons**:
- Single GPU utilization
- Not optimized for high concurrency

**Setup**:
```bash
# Install Ollama
# Windows: Download from https://ollama.com
# Linux/Mac: curl -fsSL https://ollama.com/install.sh | sh

# Pull recommended model
ollama pull llama3.1:8b          # Fast, good reasoning
ollama pull mistral:7b            # Very fast
ollama pull phi3:3.8b            # Smallest, still capable

# Test
ollama run llama3.1:8b "Analyze this trading scenario..."
```

**Integration**:
- Already supported in `agents/base_agent.py`
- Set `LLM_PROVIDER=ollama` in `.env`
- Configure `OLLAMA_BASE_URL` (default: http://localhost:11434)

**Model Recommendations**:
- **Llama 3.1 8B Q4**: Best balance of speed/quality
- **Mistral 7B Q4**: Fastest, good for high-frequency
- **Phi-3 3.8B Q4**: Smallest, good for simple tasks

### Option 2: vLLM (Recommended for Production)

**Best For**: Production, high throughput, multiple GPUs

**Pros**:
- High throughput (PagedAttention)
- Multi-GPU support
- Production-ready
- Optimized inference

**Cons**:
- More complex setup
- Requires CUDA GPU
- Higher memory requirements

**Setup**:
```bash
# Install vLLM
pip install vllm

# Start server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --quantization awq \
    --tensor-parallel-size 1 \
    --port 8000
```

**Integration**:
- Use OpenAI-compatible API
- Set `LLM_PROVIDER=openai` and `OPENAI_BASE_URL=http://localhost:8000`

**Model Recommendations**:
- **Llama 3.1 8B AWQ**: Quantized, fast
- **Llama 3.1 70B AWQ**: Better quality, needs more GPU
- **Mistral 7B AWQ**: Fast inference

### Option 3: LM Studio (Recommended for GUI Users)

**Best For**: Non-technical users, experimentation

**Pros**:
- GUI interface
- Easy model management
- OpenAI-compatible API
- Cross-platform

**Cons**:
- Less control
- Not optimized for production

**Setup**:
1. Download LM Studio from https://lmstudio.ai
2. Install and open
3. Download model (Llama 3.1 8B Q4 recommended)
4. Start local server (port 1234)
5. Configure system to use `http://localhost:1234`

**Integration**:
- Same as Ollama (OpenAI-compatible API)

### Option 4: Text Generation Inference (Hugging Face)

**Best For**: Hugging Face ecosystem, Docker deployment

**Pros**:
- Docker-based deployment
- Production-ready
- Supports many models
- Good for containerized systems

**Cons**:
- More setup complexity
- Requires Docker

**Setup**:
```bash
# Run with Docker
docker run --gpus all \
    -p 8080:80 \
    -v $PWD/data:/data \
    ghcr.io/huggingface/text-generation-inference:latest \
    --model-id meta-llama/Llama-3.1-8B-Instruct \
    --quantize bitsandbytes
```

## Model Selection Guide

### For Trading Analysis

**Requirements**:
- Fast inference (< 2 seconds per call)
- Good reasoning (structured output)
- Function calling support
- Quantized models (Q4/Q5) for efficiency

### Recommended Models

1. **Llama 3.1 8B Q4** ⭐ Best Overall
   - Speed: ⭐⭐⭐⭐
   - Quality: ⭐⭐⭐⭐
   - Reasoning: ⭐⭐⭐⭐
   - **Use Case**: All agents

2. **Mistral 7B Q4** ⭐ Fastest
   - Speed: ⭐⭐⭐⭐⭐
   - Quality: ⭐⭐⭐
   - Reasoning: ⭐⭐⭐
   - **Use Case**: High-frequency analysis

3. **Phi-3 3.8B Q4** ⭐ Smallest
   - Speed: ⭐⭐⭐⭐⭐
   - Quality: ⭐⭐⭐
   - Reasoning: ⭐⭐⭐
   - **Use Case**: Simple tasks, low-resource systems

4. **Llama 3.1 70B Q4** ⭐ Best Quality
   - Speed: ⭐⭐
   - Quality: ⭐⭐⭐⭐⭐
   - Reasoning: ⭐⭐⭐⭐⭐
   - **Use Case**: Complex analysis, when quality > speed

### Hardware Requirements

**Minimum**:
- 8GB RAM
- CPU inference (slow but works)
- Model: Phi-3 3.8B or smaller

**Recommended**:
- 16GB RAM
- NVIDIA GPU (6GB+ VRAM)
- Model: Llama 3.1 8B Q4

**Optimal**:
- 32GB+ RAM
- NVIDIA GPU (12GB+ VRAM)
- Model: Llama 3.1 70B Q4 or multiple 8B models

## Integration Steps

### Step 1: Install Ollama (Easiest)

```bash
# Windows: Download installer from https://ollama.com/download
# Linux/Mac:
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3.1:8b

# Test
ollama run llama3.1:8b "What is Bank Nifty?"
```

### Step 2: Update .env

```bash
# Add to .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

### Step 3: Test Integration

```python
# Test script
from agents.llm_provider_manager import LLMProviderManager

manager = LLMProviderManager()
response = manager.call_llm(
    system_prompt="You are a trading analyst.",
    user_message="Analyze Bank Nifty trend."
)
print(response)
```

### Step 4: Monitor Performance

- Check inference time (should be < 2s)
- Monitor GPU/CPU usage
- Verify structured output quality

## Performance Optimization

### For Speed

1. **Use Quantized Models** (Q4/Q5)
   - 4x smaller, 2-3x faster
   - Minimal quality loss

2. **Batch Requests**
   - Process multiple agents in parallel
   - Use async/await

3. **Cache Responses**
   - Cache similar queries
   - Use Redis for caching

### For Quality

1. **Use Larger Models** (70B)
   - Better reasoning
   - More accurate structured output

2. **Fine-tune on Trading Data**
   - Fine-tune on historical analysis
   - Improve domain-specific reasoning

3. **Ensemble Models**
   - Use multiple models
   - Average predictions

## Do You Need ML?

### Short Answer: **No, for basic integration**

### What You Need

1. **Basic Python** ✅
   - API calls
   - JSON handling
   - Error handling

2. **System Administration** ✅
   - Installing Ollama/vLLM
   - Managing models
   - Monitoring resources

3. **Optional: ML Knowledge** (for advanced)
   - Fine-tuning models
   - Prompt engineering
   - Model optimization

### For This System

- **Current**: No ML needed - just API integration
- **Future**: ML helpful for:
  - Fine-tuning on trading data
  - Custom model training
  - Performance optimization

## Troubleshooting

### Slow Inference

- Use quantized models (Q4/Q5)
- Reduce model size (8B → 3.8B)
- Use GPU instead of CPU
- Enable batch processing

### Out of Memory

- Use smaller models
- Reduce batch size
- Use quantization
- Close other applications

### Poor Quality Output

- Use larger models (70B)
- Improve prompts
- Fine-tune on domain data
- Use ensemble methods

## Next Steps

1. **Choose Solution**: Ollama (easiest) or vLLM (production)
2. **Install & Test**: Follow setup guide above
3. **Update .env**: Configure provider settings
4. **Test Integration**: Run test script
5. **Monitor**: Check performance and quality
6. **Optimize**: Fine-tune based on results

