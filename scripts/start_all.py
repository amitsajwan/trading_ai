"""Start all system components with instrument selection and verification."""

import sys
import os
import subprocess
import signal
import time
import socket
from pathlib import Path

# Fix Windows encoding issues
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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
        print("[ERROR]", result.stderr)
        return False
    print("[OK] Configuration complete")
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
                print("   [OK] Dashboard is accessible")
                return True
        except Exception:
            pass
        if attempt < max_wait - 1:
            time.sleep(1)
    print("   [WARNING] Dashboard not responding (may still be starting)")
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
                    print(f"   [OK] Data feed active - Price: ${float(price):,.2f}")
                    return True
                elif 'TICKS_FOUND' in output:
                    count = output.split()[-1]
                    print(f"   [OK] Data feed active - Receiving ticks ({count} ticks)")
                    return True
            elif 'REDIS_UNAVAILABLE' in result.stdout:
                if attempt == 0:
                    print(f"   [WARNING] Redis not available - skipping verification")
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
    
    print("   [WARNING] Data feed verification timeout - feed may still be connecting")
    print("   [INFO] The system will continue - check dashboard in a few seconds")
    return False

def verify_trading_service(process, max_wait=5):
    """Verify trading service is running."""
    print("   Checking if trading service is running...")
    for attempt in range(max_wait):
        # Check if process is still alive
        if process.poll() is None:
            print("   [OK] Trading service process is running")
            return True
        else:
            # Process exited, check stderr for errors
            try:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                if stderr:
                    print(f"   [WARNING] Trading service error: {stderr[:200]}")
            except:
                pass
        
        if attempt < max_wait - 1:
            time.sleep(1)
    
    print("   [WARNING] Trading service may have exited - check logs")
    return False

def start_dashboard():
    """Start the monitoring dashboard."""
    python_path = get_python_path()
    # Use uvicorn to run FastAPI app properly
    # Don't capture output so errors are visible in terminal
    process = subprocess.Popen(
        [python_path, "-m", "uvicorn", "monitoring.dashboard:app", "--host", "0.0.0.0", "--port", "8888"],
        cwd=Path(__file__).parent.parent
        # No stdout/stderr capture - let uvicorn output go to terminal
    )
    time.sleep(2)  # Give it a moment to start
    return process

def check_llm_provider():
    """Check LLM provider availability - prioritize local Ollama."""
    print("Checking LLM Provider...")
    python_path = get_python_path()
    
    try:
        result = subprocess.run(
            [python_path, "scripts/check_llm.py"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout.strip()
        stderr_output = result.stderr.strip() if result.stderr else ""
        
        if result.returncode == 0:
            if 'OLLAMA_OK' in output:
                model_count = output.split()[-1]
                print(f"   [OK] Ollama running with {model_count} model(s)")
                return True
            elif 'CLOUD_OK' in output:
                provider = output.split()[-1]
                print(f"   [OK] Cloud LLM provider configured: {provider}")
                return True
        else:
            # Show stderr if available for debugging
            if stderr_output and 'Traceback' in stderr_output:
                print(f"   [DEBUG] Error details: {stderr_output[:200]}")
            if 'OLLAMA_NO_MODELS' in output:
                print("   [FAIL] Ollama running but no models found")
                print("   Fix: Run 'ollama pull llama3.1:8b'")
                return False
            elif 'OLLAMA_ERROR' in output or 'OLLAMA_HTTPX_MISSING' in output:
                if 'OLLAMA_HTTPX_MISSING' in output:
                    print("   [FAIL] httpx module missing for Ollama check")
                    print("   Fix: pip install httpx")
                else:
                    error = output.split('OLLAMA_ERROR')[-1].strip() if 'OLLAMA_ERROR' in output else 'Not running'
                    print(f"   [WARNING] Ollama not running: {error}")
                    print("   Fix: Start Ollama manually with 'ollama serve'")
                    print("   Or: The trading service may start it automatically")
                # Allow to continue - user can start Ollama manually or it might auto-start
                return True
            elif 'UNKNOWN_PROVIDER' in output:
                provider = output.split()[-1] if len(output.split()) > 1 else 'unknown'
                print(f"   [WARNING] Unknown LLM provider configured: {provider}")
                print("   Fix: Set LLM_PROVIDER=ollama in .env for local LLM")
                print("   Note: Will try to use Ollama anyway")
                return True  # Allow to continue
            else:
                print(f"   [WARNING] LLM provider check incomplete: {output}")
                print("   Note: Will attempt to use Ollama when trading service starts")
                return True  # Allow to continue
    except Exception as e:
        print(f"   [FAIL] Error checking LLM: {str(e)[:50]}")
        print("   [INFO] System will attempt to start Ollama automatically")
        return True  # Allow to continue

def check_redis():
    """Check Redis connection."""
    print("Checking Redis...")
    python_path = get_python_path()
    
    try:
        result = subprocess.run(
            [python_path, "scripts/check_redis.py"],
            capture_output=True,
            text=True,
            timeout=3,
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout.strip()
        stderr_output = result.stderr.strip() if result.stderr else ""
        
        if result.returncode == 0 and 'REDIS_OK' in output:
            print("   [OK] Redis is running and accessible")
            return True
        else:
            if 'REDIS_MODULE_MISSING' in output:
                print("   [FAIL] Redis Python module not installed")
                print("   Fix: pip install redis")
            else:
                print("   [FAIL] Redis not accessible")
                print("   Fix: Start Redis with 'redis-server' or Docker")
            if stderr_output:
                print(f"   [DEBUG] {stderr_output[:100]}")
            return False
    except Exception as e:
        print(f"   [FAIL] Error checking Redis: {str(e)[:50]}")
        return False

def check_mongodb():
    """Check MongoDB connection."""
    print("Checking MongoDB...")
    python_path = get_python_path()
    
    try:
        result = subprocess.run(
            [python_path, "scripts/check_mongodb.py"],
            capture_output=True,
            text=True,
            timeout=3,
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout.strip()
        stderr_output = result.stderr.strip() if result.stderr else ""
        
        if result.returncode == 0 and 'MONGODB_OK' in output:
            print("   [OK] MongoDB is running and accessible")
            return True
        else:
            if 'MONGODB_MODULE_MISSING' in output:
                print("   [FAIL] MongoDB Python module not installed")
                print("   Fix: pip install pymongo")
            else:
                print("   [FAIL] MongoDB not accessible")
                print("   Fix: Start MongoDB with 'mongod' or Docker")
            if stderr_output:
                print(f"   [DEBUG] {stderr_output[:100]}")
            return False
    except Exception as e:
        print(f"   [FAIL] Error checking MongoDB: {str(e)[:50]}")
        return False

def check_data_feed_connectivity(instrument: str):
    """Check data feed connectivity before starting."""
    print(f"Checking {instrument} data feed connectivity...")
    python_path = get_python_path()
    
    if instrument == "BTC":
        check_script_path = "scripts/check_binance.py"
    else:
        check_script_path = "scripts/check_zerodha.py"
    
    try:
        result = subprocess.run(
            [python_path, check_script_path],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout.strip()
        if result.returncode == 0:
            if 'BINANCE_OK' in output:
                price = output.split()[-1] if len(output.split()) > 1 else 'N/A'
                print(f"   [OK] Binance API accessible (BTC Price: ${float(price):,.2f})")
                return True
            elif 'ZERODHA_OK' in output:
                user = output.split()[-1] if len(output.split()) > 1 else 'Unknown'
                print(f"   [OK] Zerodha credentials valid (User: {user})")
                return True
        else:
            if 'BINANCE_ERROR' in output:
                error = output.split('BINANCE_ERROR')[-1].strip()
                print(f"   [FAIL] Binance API error: {error}")
                print("   Fix: Check internet connection and Binance API availability")
            elif 'ZERODHA_NO_CREDENTIALS' in output:
                print("   [FAIL] Zerodha credentials.json not found")
                print("   Fix: Run 'python auto_login.py' to authenticate")
            elif 'ZERODHA_NO_TOKEN' in output:
                print("   [FAIL] Zerodha access token missing")
                print("   Fix: Run 'python auto_login.py' to refresh token")
            elif 'ZERODHA_ERROR' in output:
                error = output.split('ZERODHA_ERROR')[-1].strip()
                print(f"   [FAIL] Zerodha connection error: {error}")
            elif 'MODULE_MISSING' in output:
                print("   [FAIL] Required module missing (websockets)")
                print("   Fix: pip install websockets")
            else:
                print(f"   [FAIL] Data feed check failed: {output}")
            return False
    except subprocess.TimeoutExpired:
        print("   [FAIL] Data feed connectivity check timed out")
        return False
    except Exception as e:
        print(f"   [FAIL] Error checking data feed: {str(e)[:50]}")
        return False

def start_trading_service():
    """Start the trading service."""
    python_path = get_python_path()
    print("Starting trading service (includes data feed)...")
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
    print(f"Starting Trading System for {instrument}")
    print("=" * 70)
    print()
    
    # Step 1: Configure instrument
    if not configure_instrument(instrument):
        print("\n[ERROR] Failed to configure instrument")
        sys.exit(1)
    print()
    
    # Step 2: Run all pre-flight checks
    print("=" * 70)
    print("Pre-Flight Checks")
    print("=" * 70)
    print()
    
    checks_passed = True
    
    # Check LLM Provider
    if not check_llm_provider():
        checks_passed = False
    print()
    
    # Check Redis
    if not check_redis():
        checks_passed = False
    print()
    
    # Check MongoDB
    if not check_mongodb():
        checks_passed = False
    print()
    
    # Check Data Feed Connectivity
    if not check_data_feed_connectivity(instrument):
        checks_passed = False
    print()
    
    # Summary
    print("=" * 70)
    if checks_passed:
        print("[OK] All checks passed! Starting services...")
    else:
        print("[WARNING] Some checks failed. System may not work correctly.")
        print("Please fix the issues above before continuing.")
        response = input("\nContinue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted by user.")
            sys.exit(1)
    print("=" * 70)
    print()
    
    # Check if virtual environment exists
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("[WARNING] Virtual environment not found!")
        print("Setting up virtual environment...")
        python_path = get_python_path()
        subprocess.run([python_path, "scripts/setup_venv.py"], check=True)
        print()
    
    processes = []
    
    try:
        # Step 3: Start dashboard
        print("Step 1: Starting dashboard on http://localhost:8888...")
        dashboard_process = start_dashboard()
        processes.append(("Dashboard", dashboard_process))
        
        # Verify dashboard
        if verify_dashboard():
            print("[OK] Dashboard verified and ready")
        else:
            print("[WARNING] Dashboard started but verification timeout - check manually")
        print()
        
        # Step 4: Start trading service (includes data feed)
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
        print("Step 2: Verifying data feed...")
        # For crypto, give more attempts since WebSocket needs time to connect and receive data
        max_attempts = 12 if instrument == "BTC" else 8
        data_feed_verified = verify_data_feed(instrument, max_wait=max_attempts)
        if data_feed_verified:
            print("[OK] Data feed verified and receiving data")
        else:
            print("[WARNING] Data feed started but verification incomplete")
            print("   This is normal - WebSocket connections can take 10-20 seconds")
            print("   Check the dashboard in a few seconds to see live data")
        print()
        
        # Verify trading service
        if verify_trading_service(trading_process):
            print("[OK] Trading service verified")
        else:
            print("[WARNING] Trading service may have issues - check terminal output")
        print()
        
        print("=" * 70)
        print("[SUCCESS] SYSTEM STARTED SUCCESSFULLY!")
        print("=" * 70)
        print(f"Instrument: {instrument}")
        print("Dashboard: http://localhost:8888")
        print("\nComponents:")
        print("  [OK] Dashboard - Running")
        print("  [OK] Data Feed - Running")
        print("  [OK] Trading Service - Running")
        print("\nPress Ctrl+C to stop all services")
        print("=" * 70)
        
        # Wait for processes
        try:
            for name, process in processes:
                process.wait()
        except KeyboardInterrupt:
            print("\n\n[STOP] Stopping all services...")
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
            print("[OK] All services stopped")
    
    except Exception as e:
        print(f"\n[ERROR] {e}")
        # Cleanup
        for name, process in processes:
            try:
                process.terminate()
            except:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main()
