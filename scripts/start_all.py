"""Start all system components with instrument selection."""

import sys
import os
import subprocess
import signal
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def get_python_path():
    """Get Python executable path (prefer .venv if exists)."""
    venv_path = Path(".venv")
    
    if venv_path.exists():
        if sys.platform == "win32":
            python_path = venv_path / "Scripts" / "python.exe"
        else:
            python_path = venv_path / "bin" / "python"
        
        if python_path.exists():
            return str(python_path)
    
    # Fallback to system Python
    return sys.executable

def configure_instrument(instrument: str):
    """Configure instrument before starting."""
    print(f"Configuring for {instrument}...")
    python_path = get_python_path()
    result = subprocess.run(
        [python_path, "scripts/configure_instrument.py", instrument],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        return False
    return True

def start_dashboard():
    """Start the monitoring dashboard."""
    python_path = get_python_path()
    print("Starting dashboard on http://localhost:8888...")
    # Use uvicorn to run FastAPI app properly
    # Don't capture output so errors are visible in terminal
    return subprocess.Popen(
        [python_path, "-m", "uvicorn", "monitoring.dashboard:app", "--host", "0.0.0.0", "--port", "8888"],
        cwd=Path(__file__).parent.parent
        # No stdout/stderr capture - let uvicorn output go to terminal
    )

def start_trading_service():
    """Start the trading service."""
    python_path = get_python_path()
    print("Starting trading service...")
    return subprocess.Popen(
        [python_path, "-m", "services.trading_service"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

def main():
    """Main entry point."""
    # Get instrument from command line or environment
    if len(sys.argv) > 1:
        instrument = sys.argv[1].upper()
    else:
        instrument = os.getenv("TRADING_INSTRUMENT", "BANKNIFTY").upper()
    
    valid_instruments = ["BTC", "BANKNIFTY", "NIFTY"]
    if instrument not in valid_instruments:
        print("=" * 70)
        print("Invalid instrument!")
        print("=" * 70)
        print("\nUsage: python scripts/start_all.py <INSTRUMENT>")
        print("\nValid instruments:")
        print("  BTC        - Bitcoin (Crypto)")
        print("  BANKNIFTY  - Bank Nifty (Indian Market)")
        print("  NIFTY      - Nifty 50 (Indian Market)")
        print("\nExample:")
        print("  python scripts/start_all.py BTC")
        print("  python scripts/start_all.py BANKNIFTY")
        sys.exit(1)
    
    print("=" * 70)
    print(f"Starting Trading System for {instrument}")
    print("=" * 70)
    
    # Configure instrument
    if not configure_instrument(instrument):
        print("ERROR: Failed to configure instrument")
        sys.exit(1)
    
    # Check if virtual environment exists
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("\n⚠️  Virtual environment not found!")
        print("Setting up virtual environment...")
        python_path = get_python_path()
        subprocess.run([python_path, "scripts/setup_venv.py"], check=True)
    
    processes = []
    
    try:
        # Start dashboard
        dashboard_process = start_dashboard()
        processes.append(("Dashboard", dashboard_process))
        
        # Wait for dashboard to start and verify
        import time
        import socket
        print("Waiting for dashboard to start...")
        time.sleep(4)  # Give uvicorn time to start
        
        # Verify dashboard is accessible
        dashboard_ready = False
        for attempt in range(5):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', 8888))
                sock.close()
                if result == 0:
                    dashboard_ready = True
                    print("SUCCESS: Dashboard is accessible at http://localhost:8888")
                    break
            except Exception:
                pass
            if attempt < 4:
                time.sleep(1)
        
        if not dashboard_ready:
            print("WARNING: Dashboard process started but port 8888 not responding")
            print("Check terminal output above for uvicorn errors")
            print("Try accessing: http://127.0.0.1:8888 or http://localhost:8888")
        
        # Start trading service
        trading_process = start_trading_service()
        processes.append(("Trading Service", trading_process))
        print("✅ Trading service started")
        
        print("\n" + "=" * 70)
        print("System Started Successfully!")
        print("=" * 70)
        print(f"Instrument: {instrument}")
        print("Dashboard: http://localhost:8888")
        print("\nPress Ctrl+C to stop all services")
        print("=" * 70)
        
        # Wait for processes
        try:
            for name, process in processes:
                process.wait()
        except KeyboardInterrupt:
            print("\n\nStopping all services...")
            for name, process in processes:
                print(f"Stopping {name}...")
                if sys.platform == "win32":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            print("SUCCESS: All services stopped")
    
    except Exception as e:
        print(f"ERROR: {e}")
        # Cleanup
        for name, process in processes:
            process.terminate()
        sys.exit(1)

if __name__ == "__main__":
    main()
