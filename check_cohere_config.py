#!/usr/bin/env python3
"""Check Cohere configuration."""

import os
from dotenv import load_dotenv

load_dotenv()

# Check what Cohere keys are loaded
cohere_keys = []
for i in range(1, 10):
    key_name = f'COHERE_API_KEY_{i}' if i > 1 else 'COHERE_API_KEY'
    key = os.getenv(key_name)
    if key:
        cohere_keys.append((key_name, key[:20] + '...'))
    else:
        break

print('Cohere API keys loaded:')
for name, preview in cohere_keys:
    print(f'  {name}: {preview}')

print(f'\nTotal Cohere keys: {len(cohere_keys)}')
print(f'Cohere model: {os.getenv("COHERE_MODEL", "default")}')



