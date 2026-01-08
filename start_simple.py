#!/usr/bin/env python3
"""
Simple Local Startup - Start services one by one
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

def load_config():
    """Load configuration"""
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

def start_service(name, command, port=None):
    """Start a service and return the process"""
    print(f"Starting {name}...")
    try:
        env = os.environ.copy()
        process = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait a moment for startup
        time.sleep(3)

        # Test if it's responding (if port is provided)
        if port:
            import requests
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=5)
                if response.status_code == 200:
                    print(f"{name}: RUNNING on port {port}")
                    return process
                else:
                    print(f"{name}: STARTED but health check failed")
                    return process
            except:
                print(f"{name}: STARTED (health check not available)")
                return process
        else:
            print(f"{name}: STARTED")
            return process

    except Exception as e:
        print(f"{name}: FAILED - {e}")
        return None

def main():
    print("Starting Zerodha Trading System (Simple Local)")
    print("=" * 50)

    load_config()

    print(f"Instrument: {os.getenv('INSTRUMENT_SYMBOL', 'Not set')}")
    print(f"Trading Symbol: {os.getenv('INSTRUMENT_TRADING_SYMBOL', 'Not set')}")
    print()

    processes = []

    try:
        # Start APIs one by one
        current_dir = os.getcwd()

        # Market Data API
        cmd = [
            sys.executable, "-c",
            f"import sys; sys.path.insert(0, '{current_dir}'); sys.path.insert(0, '{current_dir}/market_data/src'); "
            "from market_data.api_service import app; "
            "import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8004)"
        ]
        process = start_service("Market Data API", cmd, 8004)
        if process:
            processes.append(("Market Data API", process))

        # News API
        cmd = [
            sys.executable, "-c",
            f"import sys; sys.path.insert(0, '{current_dir}'); sys.path.insert(0, '{current_dir}/news_module/src'); "
            "from news_module.api_service import app; "
            "import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8005)"
        ]
        process = start_service("News API", cmd, 8005)
        if process:
            processes.append(("News API", process))

        # Engine API
        cmd = [
            sys.executable, "-c",
            f"import sys; sys.path.insert(0, '{current_dir}'); sys.path.insert(0, '{current_dir}/engine_module/src'); "
            "from engine_module.api_service import app; "
            "import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8006)"
        ]
        process = start_service("Engine API", cmd, 8006)
        if process:
            processes.append(("Engine API", process))

        # Dashboard
        cmd = [
            sys.executable, "-c",
            f"import sys; sys.path.insert(0, '{current_dir}'); "
            f"sys.path.insert(0, '{current_dir}/market_data/src'); "
            f"sys.path.insert(0, '{current_dir}/news_module/src'); "
            f"sys.path.insert(0, '{current_dir}/engine_module/src'); "
            "from dashboard.app import app; "
            "import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8888)"
        ]
        process = start_service("Dashboard", cmd, 8888)
        if process:
            processes.append(("Dashboard", process))

        print("\n" + "=" * 50)
        print("SERVICES STARTED!")
        print("=" * 50)
        print("Available Services:")
        print("   Dashboard:     http://localhost:8888")
        print("   Market Data:   http://localhost:8004")
        print("   News API:      http://localhost:8005")
        print("   Engine API:    http://localhost:8006")
        print()
        print("Press Ctrl+C to stop all services...")
        print("=" * 50)

        # Keep running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        print("Cleaning up...")
        for name, process in processes:
            if process and process.poll() is None:
                print(f"Stopping {name}...")
                process.terminate()

        time.sleep(2)
        for name, process in processes:
            if process and process.poll() is None:
                process.kill()

        print("All services stopped.")

if __name__ == "__main__":
    main()
