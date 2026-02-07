#!/usr/bin/env python3
"""Start remaining services manually"""

import subprocess
import sys
import time

print('Starting remaining services...')

# Start engine service
print('Starting engine service...')
engine = subprocess.Popen([sys.executable, '-m', 'engine_module.api_service'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Wait a bit
time.sleep(2)

# Start gateway
print('Starting gateway...')
gateway = subprocess.Popen([sys.executable, '-c', '''
import uvicorn
import sys
sys.path.insert(0, "redis_ws_gateway/src")
from redis_ws_gateway.gateway import app
uvicorn.run(app, host="0.0.0.0", port=8889)
'''], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

print(f'Engine PID: {engine.pid}')
print(f'Gateway PID: {gateway.pid}')
print('Services should be starting...')

# Test services
import requests

time.sleep(5)

services = [
    ('Engine', 'http://localhost:8006/health'),
    ('Gateway', 'http://localhost:8889/health')
]

for name, url in services:
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f'{name}: OK')
        else:
            print(f'{name}: FAIL ({response.status_code})')
    except Exception as e:
        print(f'{name}: FAIL ({str(e)[:50]})')