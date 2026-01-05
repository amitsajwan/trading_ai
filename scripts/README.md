# Scripts Directory

Utility scripts for the trading system.

## LLM Provider Management

### `test_api_keys.py`
Test all configured LLM API keys and providers.

```bash
python scripts/test_api_keys.py
```

**Features:**
- Tests all 6 providers: Groq, OpenAI, Google, Cohere, AI21, HuggingFace
- Measures response times and success rates
- Provides recommendations for optimal configuration

### `configure_llm_provider.py`
Configure optimal LLM provider settings for performance.

```bash
python scripts/configure_llm_provider.py
```

**Features:**
- Sets up single provider mode for reduced API load
- Configures Groq as primary provider (fastest response times)
- Updates `.env` file with optimal settings
- Maintains fallback providers for reliability

## Single Provider Mode

The system now supports **single provider mode** to optimize performance:

### Configuration
```bash
# In .env file
SINGLE_PROVIDER=true
PRIMARY_PROVIDER=groq
LLM_SELECTION_STRATEGY=single
```

### Benefits
- **Reduced Load**: Uses one primary provider instead of distributing across multiple
- **Token Optimization**: Maximizes available tokens on the best provider
- **Faster Responses**: Groq provides 0.69s average response time
- **Cost Efficiency**: Free tier with 100K daily tokens
- **Automatic Fallback**: Falls back to other providers if primary fails

### Performance Results
- **Groq**: 0.69s (primary - free, 100K tokens/day)
- **AI21**: 1.39s (fastest paid alternative)
- **Cohere**: 1.53s (good paid option)
- **HuggingFace**: 1.77s (free but limited)
- **OpenAI**: 1.93s (reliable but slower)

## API Key Management

### Required Keys (from user)
```
HUGGINGFACE_API_KEY=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
GOOGLE_API_KEY=AIzaSyCEYoOsbt-FXzyV3Kh9i_fwmhvF3EsZSME
GROQ_API_KEY=GROQ_API_KEY_REDACTED
COHERE_API_KEY=xXWGFBOCljq4vp5YNKJz7XTHAcPCv3e7lPDNsFHj
OPENAI_API_KEY=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
AI21_API_KEY=e7616a6d-78bd-47dc-b076-539bacd710d9
```

### Token Limits & Usage
- **Groq**: 100K tokens/day (free)
- **OpenAI**: 10K tokens (paid)
- **AI21**: 10K tokens (paid)
- **Cohere**: 1K tokens (paid)
- **HuggingFace**: 1K tokens (free)

## Usage in Code

```python
from genai_module.core.llm_provider_manager import LLMProviderManager

# Initialize with single provider mode
manager = LLMProviderManager()

# Make LLM calls (automatically uses primary provider)
response = manager.call_llm(
    system_prompt="You are a trading assistant",
    user_message="Analyze this market data",
    max_tokens=1000
)
```

## Monitoring & Health Checks

The system includes automatic health monitoring:
- Provider availability checks
- Rate limit monitoring
- Token usage tracking
- Automatic failover when primary provider fails

## Troubleshooting

### Provider Not Working
1. Run `python scripts/test_api_keys.py` to check all providers
2. Verify API keys in `.env` file
3. Check provider status in logs

### Slow Responses
1. Ensure `SINGLE_PROVIDER=true` is set
2. Verify `PRIMARY_PROVIDER=groq` for fastest responses
3. Check network connectivity

### Rate Limits
1. Monitor token usage in logs
2. System automatically switches providers when limits reached
3. Consider upgrading to paid plans for higher limits