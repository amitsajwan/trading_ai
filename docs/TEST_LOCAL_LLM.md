# Testing Local LLM (Ollama)

Before running the full verification, test your local LLM to ensure it's working correctly.

## Quick Test

```bash
python scripts/test_local_llm.py
```

This script performs three tests:

1. **Connection Test**: Checks if Ollama is running and lists available models
2. **Simple Call Test**: Makes a basic LLM call to verify it responds
3. **Structured Output Test**: Tests JSON output (what agents use)

## Prerequisites

1. **Ollama must be running**:
   ```bash
   ollama serve
   ```

2. **At least one model must be pulled**:
   ```bash
   ollama pull llama3.1:8b
   ```

## Expected Output

### ✅ Success Example:
```
============================================================
Testing Ollama Connection
============================================================

1. Checking if Ollama is running at http://localhost:11434...
   ✅ Ollama is running!
   ✅ Found 1 model(s):
      - llama3.1:8b

============================================================
Testing Simple LLM Call
============================================================

2. Testing LLM call with model: llama3.1:8b
   Sending test prompt: 'Say hello in one sentence'
   ⏳ Waiting for response (this may take 10-30 seconds)...
   ✅ LLM responded!
   Response: Hello!

   ✅ Basic LLM call works!
```

## Troubleshooting

### ❌ "Cannot connect to Ollama"
- **Fix**: Start Ollama with `ollama serve`
- **Check**: Verify Ollama is running: `curl http://localhost:11434/api/tags`

### ❌ "No models found"
- **Fix**: Pull a model: `ollama pull llama3.1:8b`
- **Check**: List models: `ollama list`

### ❌ "LLM call timed out"
- **Possible causes**:
  - Ollama is slow (first call loads model into memory)
  - Model is too large for your system
  - System is under heavy load
- **Fix**: 
  - Wait 30-60 seconds for first call (normal)
  - Use a smaller model: `ollama pull llama3.2:3b`
  - Check system resources: `ollama ps`

### ❌ "Model not found"
- **Fix**: Pull the specific model: `ollama pull <model-name>`
- **Check**: Available models: `ollama list`

### ⚠️ "Structured output test failed"
- This is optional but recommended
- Agents need structured JSON output
- If this fails, agents may have issues parsing responses
- **Fix**: Try a different model or check model capabilities

## What Each Test Does

### Test 1: Connection
- Checks if Ollama API is accessible
- Lists available models
- **Time**: < 1 second

### Test 2: Simple Call
- Makes a basic chat completion call
- Verifies LLM responds with text
- **Time**: 10-30 seconds (first call), 2-5 seconds (subsequent)

### Test 3: Structured Output
- Tests JSON parsing (what agents need)
- Simulates agent-style prompts
- **Time**: 15-45 seconds (first call), 5-10 seconds (subsequent)

## Next Steps

Once all tests pass:
1. ✅ Run full verification: `python scripts/verify_all_components.py`
2. ✅ Start the trading system: `python scripts/start_all.py`

## Alternative: Manual Test

If you prefer to test manually:

```bash
# 1. Check Ollama is running
curl http://localhost:11434/api/tags

# 2. Test a simple call
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Say hello",
  "stream": false
}'
```

## Performance Notes

- **First call**: 30-60 seconds (model loading into memory)
- **Subsequent calls**: 2-10 seconds (model already in memory)
- **Model size matters**: Larger models = slower responses
- **System resources**: More RAM/CPU = faster responses

