#!/usr/bin/env python3
"""Test imports manually"""

import sys
import os

# Add paths manually
current_dir = os.getcwd()
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'market_data', 'src'))
sys.path.insert(0, os.path.join(current_dir, 'news_module', 'src'))
sys.path.insert(0, os.path.join(current_dir, 'engine_module', 'src'))

print("Python path:")
for p in sys.path[:5]:
    print(f"  {p}")

print("\nTesting imports...")

try:
    from market_data.api_service import app
    print("Market Data API: OK")
except Exception as e:
    print(f"Market Data API: FAILED - {e}")

try:
    from news_module.api_service import app
    print("News API: OK")
except Exception as e:
    print(f"News API: FAILED - {e}")

try:
    from engine_module.api_service import app
    print("Engine API: OK")
except Exception as e:
    print(f"Engine API: FAILED - {e}")

try:
    from dashboard.app import app
    print("Dashboard: OK")
except Exception as e:
    print(f"Dashboard: FAILED - {e}")
