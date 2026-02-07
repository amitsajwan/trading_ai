#!/usr/bin/env python3
"""Simple script to start Market Data API"""

import os
import sys

# Load environment variables
with open('local.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

# Override provider to zerodha
os.environ['TRADING_PROVIDER'] = 'zerodha'

# Add paths
sys.path.insert(0, 'market_data/src')
sys.path.insert(0, 'news_module/src')
sys.path.insert(0, 'engine_module/src')
sys.path.insert(0, 'genai_module/src')

print("Starting Market Data API...")

from market_data.api_service import app
import uvicorn

uvicorn.run(app, host='0.0.0.0', port=8004)