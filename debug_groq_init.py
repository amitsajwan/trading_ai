#!/usr/bin/env python3
"""Debug Groq provider initialization."""

import sys
import os
sys.path.insert(0, './genai_module/src')

from dotenv import load_dotenv
load_dotenv()

from genai_module.core.llm_provider_manager import LLMProviderManager

class TestSettings:
    pass

settings = TestSettings()
# Don't set individual keys - let the method read from environment

print('Creating manager...')
manager = LLMProviderManager(settings=settings)
print('Manager created')

print(f'Providers: {list(manager.providers.keys())}')

# Test the _get_multiple_api_keys method
groq_keys = manager._get_multiple_api_keys("GROQ_API_KEY")
print(f'_get_multiple_api_keys returned: {len(groq_keys)} keys')

if 'groq' in manager.providers:
    print('Groq provider found')
    print(f'Groq status: {manager.providers["groq"].status}')
    if hasattr(manager, '_groq_keys'):
        print(f'Groq keys: {len(manager._groq_keys)}')
    else:
        print('No _groq_keys attribute')
else:
    print('Groq provider NOT found')

