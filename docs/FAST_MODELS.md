# Fast Models for Quick Testing

For faster verification and testing, use smaller models that respond quickly.

## Recommended Fast Models

### ⚡ Fastest (1-2 seconds per call)
```bash
ollama pull tinyllama        # ~1.1B parameters - Fastest
ollama pull llama3.2:1b      # ~1B parameters - Very fast
```

### 🚀 Fast (2-5 seconds per call)
```bash
ollama pull llama3.2:3b      # ~3B parameters - Good balance
ollama pull phi3:mini        # ~3.8B parameters - Fast and capable
```

### 📊 Medium (5-15 seconds per call)
```bash
ollama pull llama3.1:8b      # ~8B parameters - Better quality, slower
```

## Usage

### Automatic (Uses Fastest Available)
```bash
python scripts/test_local_llm.py
```
The script automatically detects and uses the fastest available model.

### Specify a Model
```bash
python scripts/test_local_llm.py --model tinyllama
python scripts/test_local_llm.py --model llama3.2:3b
```

### Force Fastest
```bash
python scripts/test_local_llm.py --fast
```

## Model Comparison

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|--------|----------|
| `tinyllama` | 1.1B | ⚡⚡⚡ | ⭐⭐ | Quick testing |
| `llama3.2:1b` | 1B | ⚡⚡⚡ | ⭐⭐ | Quick testing |
| `llama3.2:3b` | 3B | ⚡⚡ | ⭐⭐⭐ | Good balance |
| `phi3:mini` | 3.8B | ⚡⚡ | ⭐⭐⭐ | Fast + capable |
| `llama3.1:8b` | 8B | ⚡ | ⭐⭐⭐⭐ | Production quality |

## Quick Setup

1. **Pull a fast model**:
   ```bash
   ollama pull tinyllama
   ```

2. **Test it**:
   ```bash
   python scripts/test_local_llm.py --model tinyllama
   ```

3. **If it works, proceed with full verification**:
   ```bash
   python scripts/verify_all_components.py
   ```

## Notes

- **First call**: Always slower (model loading) - 30-60s for 8B, 5-10s for 3B, 1-2s for tiny
- **Subsequent calls**: Much faster (model in memory)
- **Quality vs Speed**: Smaller models are faster but may have lower quality responses
- **For production**: Use `llama3.1:8b` or larger for better quality
- **For testing**: Use `tinyllama` or `llama3.2:3b` for quick feedback

## Troubleshooting

### Model not found
```bash
# List available models
ollama list

# Pull the model
ollama pull <model-name>
```

### Still slow?
- Check system resources: `ollama ps`
- Use smaller model: `tinyllama` or `llama3.2:1b`
- Check if model is loaded: `ollama ps` (should show model in memory)

