#!/usr/bin/env python3
"""
Simple Local Runner - Test individual components
"""

import os
import sys
import subprocess
from pathlib import Path

# Load config
def load_config():
    config_file = Path("config.local.env")
    if config_file.exists():
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("Config loaded")
    else:
        print("No config file found, using defaults")

    # Set up PYTHONPATH
    current_dir = os.getcwd()
    sys.path.insert(0, current_dir)
    sys.path.insert(0, os.path.join(current_dir, 'market_data', 'src'))
    sys.path.insert(0, os.path.join(current_dir, 'news_module', 'src'))
    sys.path.insert(0, os.path.join(current_dir, 'engine_module', 'src'))

def test_market_data_api():
    """Test market data API"""
    print("Testing Market Data API...")
    current_dir = os.getcwd()
    pythonpath = f"{current_dir}:{current_dir}/market_data/src:{current_dir}/news_module/src:{current_dir}/engine_module/src"

    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import sys; sys.path.insert(0, '{current_dir}'); sys.path.insert(0, '{current_dir}/market_data/src'); from market_data.api_service import app; print('API imports OK')"],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("Market Data API: OK")
            return True
        else:
            print(f"Market Data API: FAILED - {result.stderr}")
            return False
    except Exception as e:
        print(f"Market Data API: ERROR - {e}")
        return False

def test_news_api():
    """Test news API"""
    print("Testing News API...")
    current_dir = os.getcwd()

    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import sys; sys.path.insert(0, '{current_dir}'); sys.path.insert(0, '{current_dir}/news_module/src'); from news_module.api_service import app; print('API imports OK')"],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("News API: OK")
            return True
        else:
            print(f"News API: FAILED - {result.stderr}")
            return False
    except Exception as e:
        print(f"News API: ERROR - {e}")
        return False

def test_engine_api():
    """Test engine API"""
    print("Testing Engine API...")
    current_dir = os.getcwd()

    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import sys; sys.path.insert(0, '{current_dir}'); sys.path.insert(0, '{current_dir}/engine_module/src'); from engine_module.api_service import app; print('API imports OK')"],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("Engine API: OK")
            return True
        else:
            print(f"Engine API: FAILED - {result.stderr}")
            return False
    except Exception as e:
        print(f"Engine API: ERROR - {e}")
        return False

def test_dashboard():
    """Test dashboard"""
    print("Testing Dashboard...")
    current_dir = os.getcwd()

    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import sys; sys.path.insert(0, '{current_dir}'); sys.path.insert(0, '{current_dir}/market_data/src'); sys.path.insert(0, '{current_dir}/news_module/src'); sys.path.insert(0, '{current_dir}/engine_module/src'); from dashboard.app import app; print('Dashboard imports OK')"],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("Dashboard: OK")
            return True
        else:
            print(f"Dashboard: FAILED - {result.stderr}")
            return False
    except Exception as e:
        print(f"Dashboard: ERROR - {e}")
        return False

def main():
    print("Testing Zerodha Trading System Components")
    print("=" * 50)

    load_config()

    print(f"Instrument: {os.getenv('INSTRUMENT_SYMBOL', 'Not set')}")
    print(f"Trading Symbol: {os.getenv('INSTRUMENT_TRADING_SYMBOL', 'Not set')}")
    print()

    # Test each component
    results = []

    results.append(("Market Data API", test_market_data_api()))
    results.append(("News API", test_news_api()))
    results.append(("Engine API", test_engine_api()))
    results.append(("Dashboard", test_dashboard()))

    print()
    print("Results:")
    print("=" * 50)
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{name}: {status}")

    total_pass = sum(1 for _, success in results if success)
    print(f"\nSummary: {total_pass}/{len(results)} components working")

if __name__ == "__main__":
    main()
