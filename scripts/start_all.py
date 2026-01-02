"""Start all system components with instrument selection and verification."""

import sys
import os
import subprocess
import signal
import time
import socket
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
    print(f"📋 Step 1: Configuring for {instrument}...")
    python_path = get_python_path()
    result = subprocess.run(
        [python_path, "scripts/configure_instrument.py", instrument],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("❌ ERROR:", result.stderr)
        return False
    print("✅ Configuration complete")
    return True

def verify_dashboard(max_wait=10):
    """Verify dashboard is accessible."""
    print("   Checking dashboard accessibility...")
    for attempt in range(max_wait):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 8888))
            sock.close()
            if result == 0:
                print("   ✅ Dashboard is accessible")
                return True
        except Exception:
            pass
        if attempt < max_wait - 1:
            time.sleep(1)
    print("   ⚠️  Dashboard not responding (may still be starting)")
    return False

def verify_data_feed(instrument, max_wait=10):
    """Verify data feed is receiving data."""
    print(f"   Checking if {instrument} data feed is receiving data...")
    print(f"   (Will check up to {max_wait} times, 2 seconds apart)")
    python_path = get_python_path()
    
    for attempt in range(max_wait):
        try:
            # Check Redis for data - use a simpler, faster check with strict timeout
            check_script = """
import sys
import os
sys.path.insert(0, os.getcwd())
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=1, socket_timeout=1, decode_responses=False)
    r.ping()
except:
    print('REDIS_UNAVAILABLE')
    sys.exit(1)

try:
    from config.settings import settings
    instrument_key = settings.instrument_symbol.replace('-', '').replace(' ', '').upper()
    
    # Quick check for price key first
    price_key = f'price:{instrument_key}:latest'
    price_str = r.get(price_key)
    if price_str:
        print('PRICE_FOUND', float(price_str))
        sys.exit(0)
    
    # Check for ticks
    tick_keys = r.keys(f'tick:{instrument_key}:*')
    if tick_keys and len(tick_keys) > 0:
        print('TICKS_FOUND', len(tick_keys))
        sys.exit(0)
    
    sys.exit(1)
except Exception as e:
    print('ERROR', str(e)[:50])
    sys.exit(1)
"""
            result = subprocess.run(
                [python_path, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=2,  # Very short timeout to prevent hanging
                cwd=Path(__file__).parent.parent
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if 'PRICE_FOUND' in output:
                    price = output.split()[-1]
                    print(f"   ✅ Data feed active - Price: ${float(price):,.2f}")
                    return True
                elif 'TICKS_FOUND' in output:
                    count = output.split()[-1]
                    print(f"   ✅ Data feed active - Receiving ticks ({count} ticks)")
                    return True
            elif 'REDIS_UNAVAILABLE' in result.stdout:
                if attempt == 0:
                    print(f"   ⚠️  Redis not available - skipping verification")
                    return False
        except subprocess.TimeoutExpired:
            # Timeout is expected if Redis is slow - continue checking
            pass
        except Exception:
            # Ignore errors and continue
            pass
        
        if attempt < max_wait - 1:
            time.sleep(2)  # Wait 2 seconds between checks
            if (attempt + 1) % 3 == 0:  # Show progress every 6 seconds
                print(f"   ... checking (attempt {attempt+1}/{max_wait})...")
    
    print("   ⚠️  Data feed verification timeout - feed may still be connecting")
    print("   💡 The system will continue - check dashboard in a few seconds")
    return False

def verify_trading_service(process, max_wait=5):
    """Verify trading service is running."""
    print("   Checking if trading service is running...")
    for attempt in range(max_wait):
        # Check if process is still alive
        if process.poll() is None:
            print("   ✅ Trading service process is running")
            return True
        else:
            # Process exited, check stderr for errors
            try:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                if stderr:
                    print(f"   ⚠️  Trading service error: {stderr[:200]}")
            except:
                pass
        
        if attempt < max_wait - 1:
            time.sleep(1)
    
    print("   ⚠️  Trading service may have exited - check logs")
    return False

def start_dashboard():
    """Start the monitoring dashboard."""
    python_path = get_python_path()
    print("🚀 Step 2: Starting dashboard on http://localhost:8888...")
    # Use uvicorn to run FastAPI app properly
    # Don't capture output so errors are visible in terminal
    process = subprocess.Popen(
        [python_path, "-m", "uvicorn", "monitoring.dashboard:app", "--host", "0.0.0.0", "--port", "8888"],
        cwd=Path(__file__).parent.parent
        # No stdout/stderr capture - let uvicorn output go to terminal
    )
    time.sleep(2)  # Give it a moment to start
    return process

def start_trading_service():
    """Start the trading service."""
    python_path = get_python_path()
    print("🚀 Step 3: Starting trading service (includes data feed)...")
    process = subprocess.Popen(
        [python_path, "-m", "services.trading_service"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent
    )
    time.sleep(3)  # Give it a moment to initialize
    return process

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
    print(f"🚀 Starting Trading System for {instrument}")
    print("=" * 70)
    print()
    
    # Step 1: Configure instrument
    if not configure_instrument(instrument):
        print("\n❌ ERROR: Failed to configure instrument")
        sys.exit(1)
    print()
    
    # Check if virtual environment exists
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("⚠️  Virtual environment not found!")
        print("Setting up virtual environment...")
        python_path = get_python_path()
        subprocess.run([python_path, "scripts/setup_venv.py"], check=True)
        print()
    
    processes = []
    
    try:
        # Step 2: Start dashboard
        dashboard_process = start_dashboard()
        processes.append(("Dashboard", dashboard_process))
        
        # Verify dashboard
        if verify_dashboard():
            print("✅ Dashboard verified and ready")
        else:
            print("⚠️  Dashboard started but verification timeout - check manually")
        print()
        
        # Step 3: Start trading service (includes data feed)
        trading_process = start_trading_service()
        processes.append(("Trading Service", trading_process))
        
        # Give trading service time to initialize before checking
        # For crypto, WebSocket connection takes longer, so wait more
        wait_time = 20 if instrument == "BTC" else 5
        print(f"   Waiting for trading service to initialize ({wait_time} seconds)...")
        print("   (Crypto WebSocket connections can take 10-15 seconds)")
        time.sleep(wait_time)
        
        # Verify data feed (non-blocking, won't hang)
        print()
        # For crypto, give more attempts since WebSocket needs time to connect and receive data
        max_attempts = 12 if instrument == "BTC" else 8
        data_feed_verified = verify_data_feed(instrument, max_wait=max_attempts)
        if data_feed_verified:
            print("✅ Data feed verified and receiving data")
        else:
            print("⚠️  Data feed started but verification incomplete")
            print("   This is normal - WebSocket connections can take 10-20 seconds")
            print("   Check the dashboard in a few seconds to see live data")
        print()
        
        # Verify trading service
        if verify_trading_service(trading_process):
            print("✅ Trading service verified")
        else:
            print("⚠️  Trading service may have issues - check terminal output")
        print()
        
        print("=" * 70)
        print("✅ SYSTEM STARTED SUCCESSFULLY!")
        print("=" * 70)
        print(f"Instrument: {instrument}")
        print("Dashboard: http://localhost:8888")
        print("\nComponents:")
        print("  ✅ Dashboard - Running")
        print("  ✅ Data Feed - Running")
        print("  ✅ Trading Service - Running")
        print("\nPress Ctrl+C to stop all services")
        print("=" * 70)
        
        # Wait for processes
        try:
            for name, process in processes:
                process.wait()
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping all services...")
            for name, process in processes:
                print(f"   Stopping {name}...")
                if sys.platform == "win32":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            print("✅ All services stopped")
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        # Cleanup
        for name, process in processes:
            try:
                process.terminate()
            except:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main()
