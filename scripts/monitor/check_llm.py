"""ARCHIVED: The original check script was archived on 2026-01-03; the compressed backup was permanently deleted on 2026-01-03 per repository cleanup."""

print("This check script's original content was archived and the compressed backup was permanently deleted on 2026-01-03. Contact maintainers to request restoration.")

try:
    from core_kernel.config.settings import settings
    provider = settings.llm_provider.lower() if hasattr(settings, 'llm_provider') else 'ollama'
    
    # First, always check Ollama (local LLM is preferred)
    try:
        import httpx
        base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        response = httpx.get(f'{base_url}/api/tags', timeout=3)
        if response.status_code == 200:
            models = response.json().get('models', [])
            if models:
                print('OLLAMA_OK', len(models))
                sys.exit(0)
            else:
                print('OLLAMA_NO_MODELS')
                # Don't exit - check cloud providers as fallback
        else:
            print('OLLAMA_ERROR', response.status_code)
    except ImportError:
        print('OLLAMA_HTTPX_MISSING')
    except Exception as e:
        print('OLLAMA_ERROR', str(e)[:50])
    
    # If Ollama not available, check configured cloud provider
    if provider != 'ollama':
        api_keys = {
            'groq': 'GROQ_API_KEY',
            'gemini': 'GOOGLE_API_KEY',
            'google': 'GOOGLE_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'together': 'TOGETHER_API_KEY',
            'openrouter': 'OPENROUTER_API_KEY',
            'huggingface': 'HUGGINGFACE_API_KEY',
        }
        key_name = api_keys.get(provider, '')
        if key_name and os.getenv(key_name):
            print('CLOUD_OK', provider)
            sys.exit(0)
        elif provider not in ['ollama'] and provider not in api_keys:
            # Unknown provider, but Ollama check already failed
            print('UNKNOWN_PROVIDER', provider)
            sys.exit(1)
    
    # If we get here, Ollama failed and no cloud provider configured
    sys.exit(1)
except Exception as e:
    print('ERROR', str(e)[:50])
    sys.exit(1)


