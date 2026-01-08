# Scripts Directory

Utility scripts for the trading system.

## LLM Provider Management

### `test_api_keys.py`
Test all configured LLM API keys and providers.

```bash
python scripts/test_api_keys.py
```

**Features:**
- Tests 3 production providers: Groq, Cohere, AI21 (with multi-key support)
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
- **Groq**: 0.69s (primary - llama-3.1-70b-versatile, free, 100K tokens/day)
- **AI21**: 1.39s (tertiary - jamba-instruct, fastest paid alternative)
- **Cohere**: 1.53s (secondary - command-r-plus, good paid option)

**Note:** System now uses only these 3 production providers with multi-key load balancing for optimal performance.

## API Key Management

### Required Keys (Production Providers)
```bash
# Primary provider (Groq) - supports up to 9 keys for load balancing
GROQ_API_KEY=GROQ_API_KEY_REDACTED
GROQ_API_KEY_2=your_second_groq_key  # Optional
# ... up to GROQ_API_KEY_9

# Secondary provider (Cohere) - supports up to 9 keys
COHERE_API_KEY=xXWGFBOCljq4vp5YNKJz7XTHAcPCv3e7lPDNsFHj
COHERE_API_KEY_2=your_second_cohere_key  # Optional
# ... up to COHERE_API_K (Production Providers)
- **Groq**: 100K tokens/day (free tier, llama-3.1-70b-versatile)
- **Cohere**: Variable limits (paid, command-r-plus)
- **AI21**: Variable limits (paid, jamba-instruct)

**Recommendation:** Configure multiple API keys per provider to increase effective rate limits through load balancing.
```

**Multi-Key Load Balancing:** The system automatically rotates through available keys using round-robin for high throughput.

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
