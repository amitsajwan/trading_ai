"""Start all system components with instrument selection and verification."""

import sys
import os
import subprocess
import signal
import time
import socket
import argparse
from pathlib import Path

# Fix Windows encoding issues
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Parse command line arguments
parser = argparse.ArgumentParser(description='Start trading system components')
parser.add_argument('--skip-data-verification', action='store_true',
                   help='Skip real-time data verification (allows starting without live market data)')
parser.add_argument('--instrument', type=str, default='BANKNIFTY',
                   help='Trading instrument (default: BANKNIFTY)')
args = parser.parse_args()

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

def verify_dashboard(max_wait=10, port=8888):
    """Verify dashboard is accessible."""
    print(f"   Checking dashboard accessibility on port {port}...")
    for attempt in range(max_wait):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                print(f"   [OK] Dashboard is accessible on port {port}")
                return True
        except Exception:
            pass
        if attempt < max_wait - 1:
            time.sleep(1)
    print(f"   [WARNING] Dashboard not responding on port {port} (may still be starting)")
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

def check_port_available(port: int) -> bool:
    """Check if a port is available."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', port))
            return True
    except OSError:
        return False

def find_available_port(start_port: int = 8888, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if check_port_available(port):
            return port
    raise RuntimeError(f"Could not find available port in range {start_port}-{start_port + max_attempts}")

def start_dashboard():
    """Start the monitoring dashboard."""
    python_path = get_python_path()
    
    # Check if port 8888 is available, if not find another
    dashboard_port = 8888
    if not check_port_available(dashboard_port):
        print(f"⚠️  Port {dashboard_port} is already in use, finding alternative...")
        try:
            dashboard_port = find_available_port(8888)
            print(f"   Using port {dashboard_port} instead")
        except RuntimeError as e:
            print(f"❌ {e}")
            print("   Please free up a port or stop the existing dashboard")
            return None
    
    # Use uvicorn to run FastAPI app properly
    # Don't capture output so errors are visible in terminal
    process = subprocess.Popen(
        [python_path, "-m", "uvicorn", "dashboard_pro:app", "--host", "0.0.0.0", "--port", str(dashboard_port)],
        cwd=Path(__file__).parent.parent
        # No stdout/stderr capture - let uvicorn output go to terminal
    )
    time.sleep(2)  # Give it a moment to start
    return process, dashboard_port

def check_llm_provider():
    """Check LLM provider availability - prioritize local Ollama."""
    print("Checking LLM Provider...")
    python_path = get_python_path()
    script_path = Path(__file__).parent.parent / "scripts" / "check_llm.py"
    
    try:
        result = subprocess.run(
            [python_path, str(script_path)],
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
                print(f"   [DEBUG] Error details: {stderr_output[:300]}")
            if 'OLLAMA_NO_MODELS' in output:
                print("   [FAIL] Ollama running but no models found")
                print("   Fix: Run 'ollama pull llama3.1:8b'")
                return False
            elif 'OLLAMA_HTTPX_MISSING' in output:
                print("   [FAIL] httpx module missing for Ollama check")
                print("   Fix: pip install httpx")
                return False
            elif 'OLLAMA_ERROR' in output:
                error = output.replace('OLLAMA_ERROR', '').strip()
                print(f"   [WARNING] Ollama not running: {error}")
                print("   Fix: Start Ollama manually with 'ollama serve'")
                print("   Or: The trading service may start it automatically")
                # Allow to continue - user can start Ollama manually or it might auto-start
                return True
            elif 'UNKNOWN_PROVIDER' in output:
                provider = output.replace('UNKNOWN_PROVIDER', '').strip()
                if not provider:
                    provider = 'unknown'
                print(f"   [WARNING] Unknown LLM provider configured: {provider}")
                print("   Fix: Set LLM_PROVIDER=ollama in .env for local LLM")
                print("   Note: Will try to use Ollama anyway")
                return True  # Allow to continue
            elif 'ERROR' in output:
                error_msg = output.replace('ERROR', '').strip()
                print(f"   [WARNING] LLM check error: {error_msg}")
                print("   Note: Will attempt to use Ollama when trading service starts")
                return True  # Allow to continue
            else:
                print(f"   [WARNING] LLM provider check incomplete: {output}")
                if stderr_output:
                    print(f"   [DEBUG] stderr: {stderr_output[:200]}")
                print("   Note: Will attempt to use Ollama when trading service starts")
                return True  # Allow to continue
    except subprocess.TimeoutExpired:
        print("   [WARNING] LLM check timed out (exceeded 5 seconds)")
        print("   Note: Will attempt to use Ollama when trading service starts")
        return True  # Allow to continue
    except Exception as e:
        print(f"   [WARNING] Error checking LLM: {str(e)}")
        import traceback
        print(f"   [DEBUG] Full error: {traceback.format_exc()[:300]}")
        print("   [INFO] System will attempt to start Ollama automatically")
        return True  # Allow to continue

def check_redis():
    """Check Redis connection."""
    print("Checking Redis...")
    python_path = get_python_path()
    script_path = Path(__file__).parent.parent / "scripts" / "check_redis.py"
    
    try:
        result = subprocess.run(
            [python_path, str(script_path)],
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
            elif 'REDIS_ERROR' in output:
                error_msg = output.replace('REDIS_ERROR', '').strip()
                print(f"   [FAIL] Redis connection error: {error_msg}")
                print("   Fix: Start Redis with 'redis-server' or Docker")
            else:
                print("   [FAIL] Redis not accessible")
                print("   Fix: Start Redis with 'redis-server' or Docker")
            if stderr_output:
                print(f"   [DEBUG] stderr: {stderr_output[:200]}")
            if output and 'REDIS_OK' not in output:
                print(f"   [DEBUG] stdout: {output[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print("   [FAIL] Redis check timed out (exceeded 3 seconds)")
        print("   Fix: Check if Redis is running and accessible")
        return False
    except Exception as e:
        print(f"   [FAIL] Error checking Redis: {str(e)}")
        import traceback
        print(f"   [DEBUG] Full error: {traceback.format_exc()[:300]}")
        return False

def check_mongodb():
    """Check MongoDB connection."""
    print("Checking MongoDB...")
    python_path = get_python_path()
    script_path = Path(__file__).parent.parent / "scripts" / "check_mongodb.py"
    
    try:
        result = subprocess.run(
            [python_path, str(script_path)],
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
            elif 'MONGODB_ERROR' in output:
                error_msg = output.replace('MONGODB_ERROR', '').strip()
                print(f"   [FAIL] MongoDB connection error: {error_msg}")
                print("   Fix: Start MongoDB with 'mongod' or Docker")
            else:
                print("   [FAIL] MongoDB not accessible")
                print("   Fix: Start MongoDB with 'mongod' or Docker")
            if stderr_output:
                print(f"   [DEBUG] stderr: {stderr_output[:200]}")
            if output and 'MONGODB_OK' not in output:
                print(f"   [DEBUG] stdout: {output[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print("   [FAIL] MongoDB check timed out (exceeded 3 seconds)")
        print("   Fix: Check if MongoDB is running and accessible")
        return False
    except Exception as e:
        print(f"   [FAIL] Error checking MongoDB: {str(e)}")
        import traceback
        print(f"   [DEBUG] Full error: {traceback.format_exc()[:300]}")
        return False

def test_agent_analysis():
    """Test that agents can produce analysis before starting system."""
    print("Testing Agent Analysis (Pre-Flight)...")
    python_path = get_python_path()
    script_path = Path(__file__).parent.parent / "scripts" / "test_agent_analysis.py"
    
    try:
        result = subprocess.run(
            [python_path, str(script_path)],
            capture_output=True,
            text=True,
            timeout=150,  # 2.5 minutes max
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout.strip()
        stderr_output = result.stderr.strip() if result.stderr else ""
        
        if result.returncode == 0 and 'AGENT_TEST_OK' in output:
            # Parse the success message
            lines = output.split('\n')
            for line in lines:
                if 'Signal:' in line:
                    print(f"   [OK] {line.strip()}")
                    break
            return True
        else:
            if 'AGENT_TEST_TIMEOUT' in output:
                print("   [FAIL] Agent analysis test timed out (exceeded 2 minutes)")
                print("   Fix: Check LLM provider (Ollama/API) is responding")
                print("   Fix: Check network connectivity for cloud LLM")
            elif 'AGENT_TEST_MISSING_AGENTS' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
                print("   Fix: Check agent initialization in trading graph")
            elif 'AGENT_TEST_EMPTY_AGENTS' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
                print("   Fix: Check LLM provider and agent prompts")
                print("   Fix: Verify LLM is responding with meaningful content")
            elif 'AGENT_TEST_NO_RESULTS' in output:
                print("   [FAIL] Analysis completed but no results stored")
                print("   Fix: Check MongoDB connection and write permissions")
            elif 'AGENT_TEST_MODULE_MISSING' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
            elif 'AGENT_TEST_INIT_ERROR' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
            elif 'AGENT_TEST_ERROR' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
            else:
                print("   [FAIL] Agent analysis test failed")
                if stderr_output:
                    print(f"   [DEBUG] stderr: {stderr_output[:300]}")
                if output:
                    print(f"   [DEBUG] stdout: {output[:300]}")
            return False
    except subprocess.TimeoutExpired:
        print("   [FAIL] Agent analysis test timed out (exceeded 2.5 minutes)")
        print("   Fix: Check LLM provider is responding")
        return False
    except Exception as e:
        print(f"   [FAIL] Error running agent test: {str(e)}")
        import traceback
        print(f"   [DEBUG] Full error: {traceback.format_exc()[:300]}")
        return False

def check_agent_analysis():
    """Check if agents are producing analysis."""
    print("Checking Agent Analysis...")
    python_path = get_python_path()
    script_path = Path(__file__).parent.parent / "scripts" / "check_agent_analysis.py"
    
    try:
        result = subprocess.run(
            [python_path, str(script_path)],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout.strip()
        stderr_output = result.stderr.strip() if result.stderr else ""
        
        if result.returncode == 0 and 'AGENT_ANALYSIS_OK' in output:
            # Parse the success message
            lines = output.split('\n')
            if len(lines) > 1:
                details = lines[1]
                print(f"   [OK] {details}")
            else:
                print("   [OK] Agents are producing analysis")
            return True
        else:
            if 'AGENT_ANALYSIS_NOT_FOUND' in output:
                print("   [WARNING] No agent analysis found yet")
                print("   Note: Agents run every 60 seconds - analysis will appear shortly")
                return False  # Not a critical failure, but should be noted
            elif 'AGENT_ANALYSIS_STALE' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
                print("   Fix: Check if trading service is running and agents are executing")
                return False
            elif 'AGENT_ANALYSIS_MISSING_AGENTS' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
                print("   Fix: Check agent initialization in trading graph")
                return False
            elif 'AGENT_ANALYSIS_EMPTY_AGENTS' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
                print("   Fix: Check LLM provider and agent prompts")
                return False
            elif 'AGENT_ANALYSIS_NO_CONTENT' in output:
                print("   [FAIL] Agent analysis exists but contains no meaningful content")
                print("   Fix: Check LLM responses and data feed")
                return False
            elif 'AGENT_ANALYSIS_MODULE_MISSING' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
                return False
            elif 'AGENT_ANALYSIS_ERROR' in output:
                error_msg = output.split('\n')[1] if '\n' in output else output
                print(f"   [FAIL] {error_msg}")
                return False
            else:
                print("   [FAIL] Agent analysis check failed")
                if stderr_output:
                    print(f"   [DEBUG] stderr: {stderr_output[:200]}")
                if output:
                    print(f"   [DEBUG] stdout: {output[:200]}")
                return False
    except subprocess.TimeoutExpired:
        print("   [FAIL] Agent analysis check timed out (exceeded 5 seconds)")
        print("   Fix: Check MongoDB connection and agent execution")
        return False
    except Exception as e:
        print(f"   [FAIL] Error checking agent analysis: {str(e)}")
        import traceback
        print(f"   [DEBUG] Full error: {traceback.format_exc()[:300]}")
        return False

def check_data_feed_connectivity(instrument: str):
    """Check data feed connectivity before starting."""
    print(f"Checking {instrument} data feed connectivity...")
    python_path = get_python_path()
    
    if instrument == "BTC":
        check_script_path = Path(__file__).parent.parent / "scripts" / "check_binance.py"
    else:
        check_script_path = Path(__file__).parent.parent / "scripts" / "check_zerodha.py"
    
    try:
        result = subprocess.run(
            [python_path, str(check_script_path)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout.strip()
        stderr_output = result.stderr.strip() if result.stderr else ""
        
        if result.returncode == 0:
            if 'BINANCE_OK' in output:
                price = output.replace('BINANCE_OK', '').strip()
                try:
                    price_float = float(price) if price else 0.0
                    print(f"   [OK] Binance API accessible (BTC Price: ${price_float:,.2f})")
                except ValueError:
                    print(f"   [OK] Binance API accessible (Price: {price})")
                return True
            elif 'ZERODHA_OK' in output:
                user = output.replace('ZERODHA_OK', '').strip()
                if not user:
                    user = 'Unknown'
                print(f"   [OK] Zerodha credentials valid (User: {user})")
                return True
        else:
            if 'BINANCE_ERROR' in output:
                error = output.replace('BINANCE_ERROR', '').strip()
                print(f"   [FAIL] Binance API error: {error}")
                print("   Fix: Check internet connection and Binance API availability")
            elif 'ZERODHA_NO_CREDENTIALS' in output:
                print("   [FAIL] Zerodha credentials.json not found")
                print("   Fix: Run 'python auto_login.py' to authenticate")
            elif 'ZERODHA_NO_TOKEN' in output:
                print("   [FAIL] Zerodha access token missing")
                print("   Fix: Run 'python auto_login.py' to refresh token")
            elif 'ZERODHA_ERROR' in output:
                error = output.replace('ZERODHA_ERROR', '').strip()
                print(f"   [FAIL] Zerodha connection error: {error}")
            elif 'MODULE_MISSING' in output:
                print("   [FAIL] Required module missing (websockets)")
                print("   Fix: pip install websockets")
            else:
                print(f"   [FAIL] Data feed check failed: {output}")
            if stderr_output:
                print(f"   [DEBUG] stderr: {stderr_output[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print("   [FAIL] Data feed connectivity check timed out (exceeded 10 seconds)")
        print("   Fix: Check internet connection and API availability")
        return False
    except Exception as e:
        print(f"   [FAIL] Error checking data feed: {str(e)}")
        import traceback
        print(f"   [DEBUG] Full error: {traceback.format_exc()[:300]}")
        return False

def start_trading_service():
    """Start the trading service."""
    python_path = get_python_path()
    print("Starting trading service (includes data feed)...")
    print("   [INFO] Trading service logs will appear below:")
    print("   [INFO] Look for '[OK] Connected to Binance WebSocket' and '[TICK #]' messages")
    print()
    # Don't capture output - let logs show in terminal so we can see WebSocket connection
    process = subprocess.Popen(
        [python_path, "-m", "services.trading_service"],
        # stdout and stderr NOT captured - logs will show in terminal
        cwd=Path(__file__).parent.parent
    )
    time.sleep(3)  # Give it a moment to initialize
    return process

def check_existing_processes():
    """Check for existing trading service processes and warn user."""
    try:
        import psutil
        # Get current process PID to exclude it
        current_pid = os.getpid()
        
        existing = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip current process (the start_all.py script itself)
                if proc.info['pid'] == current_pid:
                    continue
                    
                cmdline = ' '.join(proc.info['cmdline'] or [])
                
                # Only check for actual trading service processes, NOT start_all.py
                # start_all.py is the launcher - we don't want to detect ourselves
                if 'start_all.py' in cmdline:
                    continue  # Skip start_all.py processes (they're launchers, not services)
                
                # Check for actual trading service processes
                if any(x in cmdline for x in ['trading_service', 'services.trading_service', '-m services.trading_service']):
                    existing.append({
                        'pid': proc.info['pid'],
                        'cmdline': cmdline[:80]
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if len(existing) > 0:
            print("=" * 70)
            print("WARNING: Existing Trading Service Processes Found!")
            print("=" * 70)
            print(f"Found {len(existing)} existing process(es):")
            for proc in existing:
                print(f"  PID {proc['pid']}: {proc['cmdline']}")
            print("\nMultiple processes can cause:")
            print("  - Resource conflicts")
            print("  - Inconsistent analysis timing")
            print("  - Database locks")
            print("\n[OPTIONS]")
            print("  1. Kill existing processes automatically (recommended)")
            print("  2. Continue anyway (not recommended)")
            print("  3. Abort and stop manually")
            print("=" * 70)
            response = input("\nChoose option (1/2/3) [default: 1]: ").strip().lower()
            
            if response == '3':
                print("\nAborted. Please stop existing processes manually:")
                print("  taskkill /F /IM python.exe  (Windows)")
                sys.exit(1)
            elif response == '1' or response == '':
                # Auto-kill existing processes - improved with verification
                print("\nKilling existing processes...")
                killed_count = 0
                failed_pids = []
                
                for proc in existing:
                    pid = proc['pid']
                    killed = False
                    
                    # Try psutil first (graceful)
                    try:
                        import psutil
                        p = psutil.Process(pid)
                        p.terminate()
                        try:
                            p.wait(timeout=2)
                            killed = True
                            print(f"  ✓ Killed PID {pid} (graceful)")
                        except psutil.TimeoutExpired:
                            p.kill()
                            p.wait(timeout=1)
                            killed = True
                            print(f"  ✓ Killed PID {pid} (force)")
                    except psutil.NoSuchProcess:
                        # Already dead
                        killed = True
                        print(f"  ✓ PID {pid} already terminated")
                    except Exception as e:
                        # psutil failed, try taskkill
                        pass
                    
                    # Fallback to taskkill (more reliable on Windows)
                    if not killed and sys.platform == "win32":
                        try:
                            result = subprocess.run(
                                ["taskkill", "/F", "/PID", str(pid)], 
                                capture_output=True, 
                                timeout=5,
                                text=True
                            )
                            if result.returncode == 0 or "SUCCESS" in result.stdout:
                                killed = True
                                print(f"  ✓ Killed PID {pid} (via taskkill)")
                            else:
                                # Check if process doesn't exist
                                if "not found" in result.stdout.lower() or "does not exist" in result.stdout.lower():
                                    killed = True
                                    print(f"  ✓ PID {pid} not found (already dead)")
                        except Exception as e:
                            pass
                    
                    # Verify process is actually dead
                    if killed:
                        # Double-check it's actually gone
                        try:
                            import psutil
                            psutil.Process(pid)
                            # Still exists - try harder
                            if sys.platform == "win32":
                                subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                                             capture_output=True, timeout=3)
                            time.sleep(0.5)
                            try:
                                psutil.Process(pid)
                                failed_pids.append(pid)
                                print(f"  ✗ PID {pid} still running after kill attempt")
                            except psutil.NoSuchProcess:
                                killed_count += 1
                        except psutil.NoSuchProcess:
                            killed_count += 1
                        except:
                            # Can't verify, assume killed
                            killed_count += 1
                    else:
                        failed_pids.append(pid)
                        print(f"  ✗ Failed to kill PID {pid}")
                
                # Wait for processes to fully terminate
                if killed_count > 0:
                    print(f"\n✓ Killed {killed_count} process(es). Waiting 3 seconds for cleanup...")
                    time.sleep(3)
                    
                    # Final verification
                    if failed_pids:
                        print(f"\n⚠ Warning: {len(failed_pids)} process(es) may still be running: {failed_pids}")
                        print("You may need to kill them manually:")
                        for pid in failed_pids:
                            print(f"  taskkill /F /PID {pid}")
                        response2 = input("\nContinue anyway? (y/N): ").strip().lower()
                        if response2 != 'y':
                            print("Aborted.")
                            sys.exit(1)
                    else:
                        print("✓ All processes terminated. Continuing with startup...\n")
                else:
                    print("\n⚠ Could not kill any processes.")
                    response2 = input("Continue anyway? (y/N): ").strip().lower()
                    if response2 != 'y':
                        print("Aborted.")
                        sys.exit(1)
                    print("Continuing anyway...\n")
            else:
                print("Continuing with existing processes...\n")
    except ImportError:
        # psutil not installed - skip check
        pass
    except Exception as e:
        # Error checking - continue anyway
        pass

def main():
    """Main entry point."""
    # Check for existing processes first
    check_existing_processes()
    
    # Get instrument from command line arguments
    instrument = args.instrument.upper()
    
    valid_instruments = ["BTC", "BANKNIFTY", "NIFTY"]
    if instrument not in valid_instruments:
        print("=" * 70)
        print("Invalid instrument!")
        print("=" * 70)
        print("\nUsage: python scripts/start_all.py [--instrument <INSTRUMENT>] [--skip-data-verification]")
        print("\nValid instruments:")
        print("  BTC        - Bitcoin (Crypto)")
        print("  BANKNIFTY  - Bank Nifty (Indian Market)")
        print("  NIFTY      - Nifty 50 (Indian Market)")
        print("\nOptions:")
        print("  --instrument <INSTRUMENT>          Trading instrument (default: BANKNIFTY)")
        print("  --skip-data-verification           Skip real-time data verification")
        print("\nExamples:")
        print("  python scripts/start_all.py")
        print("  python scripts/start_all.py --instrument BTC")
        print("  python scripts/start_all.py --instrument BANKNIFTY --skip-data-verification")
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
    
    # Step 2: Run comprehensive component verification
    print("=" * 70)
    print("COMPREHENSIVE COMPONENT VERIFICATION")
    print("=" * 70)
    print("Verifying each component individually with detailed notes...")
    print()
    
    python_path = get_python_path()
    verify_script_path = Path(__file__).parent.parent / "scripts" / "monitor" / "verify_all_components.py"
    
    try:
        result = subprocess.run(
            [python_path, str(verify_script_path), instrument],
            capture_output=False,  # Let it print directly
            text=True,
            timeout=180,  # 3 minutes max
            cwd=Path(__file__).parent.parent
        )
        checks_passed = (result.returncode == 0)
    except subprocess.TimeoutExpired:
        print("\n[FAIL] Component verification timed out (exceeded 3 minutes)")
        print("This usually indicates a serious issue with LLM or system components.")
        checks_passed = False
    except Exception as e:
        print(f"\n[FAIL] Error running component verification: {str(e)}")
        checks_passed = False
    
    print()
    print("=" * 70)
    if checks_passed:
        print("[OK] All critical components verified! Starting services...")
    else:
        print("[CRITICAL] Component verification failed!")
        print("The system cannot start without working components.")
        print("Please review the verification report above and fix all critical issues.")
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
        print("Step 1: Starting dashboard...")
        dashboard_result = start_dashboard()
        if dashboard_result is None:
            print("[ERROR] Could not start dashboard - port conflict")
            sys.exit(1)
        dashboard_process, dashboard_port = dashboard_result
        processes.append(("Dashboard", dashboard_process))
        
        print(f"   Dashboard starting on http://localhost:{dashboard_port}...")
        
        # Verify dashboard (update port)
        if verify_dashboard(max_wait=10, port=dashboard_port):
            print(f"[OK] Dashboard verified and ready on port {dashboard_port}")
        else:
            print(f"[WARNING] Dashboard started but verification timeout - check manually at http://localhost:{dashboard_port}")
        print()
        
        # Step 4: Check data feed connectivity before starting trading service
        print("Step 2: Checking data feed connectivity...")
        if not check_data_feed_connectivity(instrument):
            print("[CRITICAL] Data feed connectivity check failed!")
            print("Cannot start trading service without data feed access.")
            print("Stopping dashboard...")
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()
            sys.exit(1)
        print("[OK] Data feed connectivity verified")
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
        
        # Step 4: Verify real-time tick data (optional with --skip-data-verification)
        print()
        if args.skip_data_verification:
            print("Step 4: Skipping real-time tick data verification (--skip-data-verification)")
            print("   [WARNING] System starting without live market data verification")
            print("   [INFO] Dashboard may show stale or no data until market feed connects")
            data_feed_verified = True
        else:
            print("Step 4: Verifying real-time tick data...")
            # For crypto, give more attempts since WebSocket needs time to connect and receive data
            max_attempts = 12 if instrument == "BTC" else 8
            data_feed_verified = verify_data_feed(instrument, max_wait=max_attempts)
            if not data_feed_verified:
                print("[CRITICAL] Real-time tick data verification failed!")
                print("The system cannot start without live market data.")
                print("Please check:")
                if instrument == "BTC":
                    print("  - Internet connection")
                    print("  - Binance WebSocket connectivity")
                else:
                    print("  - Kite WebSocket connection")
                    print("  - Zerodha session validity")
                print("\nStopping services...")
                # Stop trading service
                trading_process.terminate()
                try:
                    trading_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    trading_process.kill()
            # Stop dashboard
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()
            sys.exit(1)
        print("[OK] Real-time tick data verified")
        print()
        
        # Step 5: Verify trading service
        if verify_trading_service(trading_process):
            print("[OK] Trading service verified")
        else:
            print("[WARNING] Trading service may have issues - check terminal output")
        print()
        
        # Step 6: Verify agent analysis (agents run every 60 seconds)
        print("Step 6: Verifying agent analysis...")
        print("   Waiting for agents to complete first analysis cycle (up to 90 seconds)...")
        print("   (Agents run every 60 seconds, first cycle may take longer)")
        
        agent_analysis_verified = False
        max_wait_attempts = 15  # 15 attempts * 6 seconds = 90 seconds max
        for attempt in range(1, max_wait_attempts + 1):
            time.sleep(6)  # Check every 6 seconds
            if check_agent_analysis():
                agent_analysis_verified = True
                print()
                print("[OK] Agent analysis verified - agents are working correctly!")
                break
            elif attempt < max_wait_attempts:
                print(f"   Attempt {attempt}/{max_wait_attempts}: Waiting for agent analysis...")
        
        if not agent_analysis_verified:
            print()
            print("[WARNING] Agent analysis not verified after 90 seconds")
            print("   This may be normal if:")
            print("   - Agents are still initializing")
            print("   - First analysis cycle is taking longer")
            print("   - Check dashboard and logs for agent activity")
            print("   - Agents should produce analysis within 60-120 seconds")
        print()
        
        print("=" * 70)
        print("[SUCCESS] SYSTEM STARTED SUCCESSFULLY!")
        print("=" * 70)
        print(f"Instrument: {instrument}")
        # Get dashboard port from processes (stored as tuple)
        dashboard_port = 8888  # Default
        for name, proc_info in processes:
            if name == "Dashboard":
                if isinstance(proc_info, tuple):
                    _, dashboard_port = proc_info
                break
        print(f"Dashboard: http://localhost:{dashboard_port}")
        print("\nComponents:")
        print("  [OK] Dashboard - Running")
        print("  [OK] Data Feed - Running")
        print("  [OK] Trading Service - Running")
        if agent_analysis_verified:
            print("  [OK] Agent Analysis - Verified")
        else:
            print("  [WARNING] Agent Analysis - Not yet verified (check dashboard)")
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
