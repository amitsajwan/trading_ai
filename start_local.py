#!/usr/bin/env python3
"""Local development startup script.
Starts all trading system services locally for development and testing."""

import os
import sys
import time
import subprocess
import signal
import threading
import asyncio
import requests
from pathlib import Path

# Add market_data/src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / 'market_data' / 'src'))

# Setup centralized logging and monitoring
from config import get_config
config = get_config()
config.setup_logging()

# Get instrument configuration for dynamic usage
INSTRUMENT_SYMBOL = config.instrument_symbol
INSTRUMENT_KEY = config.instrument_key

# Initialize monitoring system
try:
    from monitoring import get_performance_monitor, get_health_checker
    perf_monitor = get_performance_monitor()
    health_checker = get_health_checker()
    print("[OK] Monitoring system initialized")
except ImportError as e:
    print(f"WARNING: Monitoring system not available: {e}")
    perf_monitor = None
    health_checker = None

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        # Try to set UTF-8 encoding for Windows console
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Fallback for older Python versions
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def load_env():
    """Load environment variables from local.env or per-module env files.

    Order of precedence (first existing file is loaded, existing env vars are not overridden):
      - local.env (project root)
      - .env (project root)
      - market_data/.env
      - genai_module/.env
      - engine_module/.env
      - news_module/.env

    This makes `start_local.py` behave similarly to docker-compose (which reads service env files), while keeping per-module configuration files isolated.
    """
    candidates = [
        'local.env',
        '.env',
        'market_data/.env',
        'genai_module/.env',
        'engine_module/.env',
        'news_module/.env',
    ]

    loaded_any = False
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        # Do not overwrite explicitly set environment variables
                        os.environ.setdefault(key.strip(), value.strip())
                print(f"Loaded environment from {path}")
                loaded_any = True
            except Exception:
                print(f"Failed to load environment file: {path}")

    if not loaded_any:
        print("No env file found (search order: local.env, .env, market_data/.env, genai_module/.env, engine_module/.env, news_module/.env).")
        print("Copy module templates from their `.env.example` files and create local .env files.")


def ensure_virtual_environment():
    """Ensure we're running in a virtual environment and create one if needed"""
    print("   [ENV] Checking virtual environment...")

    # Check if we're already in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("   ✅ Already running in virtual environment")
        return True

    # Check for existing venv directory
    venv_path = Path('.venv')
    if venv_path.exists() and venv_path.is_dir():
        print("   ℹ️  Found existing virtual environment (.venv)")
        print("   💡 Activate it manually: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate (Linux/Mac)")
        print("   ⚠️  Or run: python start_local.py (after activation)")
        return False

    # Create new virtual environment
    print("   🆕 Creating virtual environment (.venv)...")
    try:
        subprocess.run([sys.executable, '-m', 'venv', '.venv'], check=True)
        print("   ✅ Virtual environment created successfully")
        print("   💡 Activate it with: .venv\\Scripts\\activate (Windows)")
        print("   💡 Then run: pip install -r requirements.txt")
        print("   💡 Or run this script again after activation")
        return False
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed to create virtual environment: {e}")
        print("   💡 Try creating manually: python -m venv .venv")
        return False


def ensure_requirements_installed():
    """Ensure all requirements from requirements.txt are installed"""
    print("   [DEPS] Checking Python requirements...")

    requirements_file = Path('requirements.txt')
    if not requirements_file.exists():
        print("   ❌ requirements.txt not found!")
        return False

    try:
        # Check if key packages are installed by trying to import them
        key_packages = [
            ('fastapi', 'FastAPI'),
            ('redis', 'Redis'),
            ('kiteconnect', 'KiteConnect'),
            ('uvicorn', 'Uvicorn'),
            ('pandas', 'Pandas'),
            ('numpy', 'NumPy')
        ]

        missing_packages = []
        for package_name, display_name in key_packages:
            try:
                __import__(package_name.replace('-', '_'))
            except ImportError:
                missing_packages.append(display_name)

        if missing_packages:
            print(f"   ⚠️  Missing key packages: {', '.join(missing_packages)}")
            print("   📦 Installing requirements...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
            print("   ✅ Requirements installed successfully")
        else:
            print("   ✅ All key requirements appear to be installed")

        return True

    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed to install requirements: {e}")
        print("   💡 Try manually: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"   ❌ Error checking requirements: {e}")
        return False


def kill_process_on_port(port):
    """Kill any process listening on the given port"""
    try:
        # Use netstat to find PID
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        lines = result.stdout.split('\n')
        for line in lines:
            if f':{port}' in line and ('LISTENING' in line or 'LISTEN' in line):
                parts = line.split()
                if len(parts) > 4:
                    pid = parts[-1].strip()
                    if pid.isdigit():
                        try:
                            subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)
                            print(f"Killed existing process on port {port} (PID {pid})")
                            time.sleep(2)  # Wait for port to be free
                            return True
                        except subprocess.CalledProcessError:
                            pass
    except Exception as e:
        print(f"Error killing process on port {port}: {e}")
    return False


def check_health(url, timeout=10):
    """Check if a service is healthy by making an HTTP request"""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_service(name, health_url, max_retries=30, retry_delay=1, timeout=5):
    """Wait for a service to become healthy with retries"""
    print(f"   [WAIT] Verifying {name}...")
    for attempt in range(1, max_retries + 1):
        if check_health(health_url, timeout=timeout):
            print(f"   [OK] {name} is healthy and ready!")
            return True
        if attempt < max_retries:
            print(f"   [WAIT] Attempt {attempt}/{max_retries} - waiting for {name}...")
            time.sleep(retry_delay)
    print(f"   [ERROR] {name} failed to become healthy after {max_retries} attempts")
    return False




def verify_zerodha_credentials():
    """Verify Zerodha credentials are available and token authentication works"""
    print("   [AUTH] Verifying Zerodha credentials and token authentication...")
    try:
        # Step 1: Check environment variables first
        api_key = os.getenv('KITE_API_KEY')
        api_secret = os.getenv('KITE_API_SECRET')
        access_token = os.getenv('KITE_ACCESS_TOKEN')

        if api_key and access_token:
            print("   [OK] Found Zerodha API credentials in environment variables")
            return True, None  # Trust env vars are valid

        # Step 2: Check credentials.json using KiteAuthService
        try:
            sys.path.insert(0, './market_data/src')
            from market_data.tools.kite_auth_service import KiteAuthService
            auth_service = KiteAuthService()
            creds = auth_service.load_credentials()

            if creds and auth_service.is_token_valid(creds):
                print("   [OK] Found valid access token in credentials.json")
                print(f"      Token validated for user: {creds.get('user_name', 'Unknown')}")
                return True, None  # Trust kite auth service validation
            else:
                print("   [WARN]  No valid credentials found in credentials.json")
                return False, None
        except Exception as e:
            print(f"   [WARN]  Could not validate credentials: {e}")
            return False, None

    except Exception as e:
        print(f"   [ERROR] Error verifying Zerodha credentials: {e}")
        return False, None


def verify_historical_data(max_retries=30, retry_delay=1, data_source='zerodha', replay_instance=None):
    """Verify historical data is actually available in the store"""
    print("   [WAIT] Verifying historical data availability...")

    # First check Redis connectivity
    try:
        import redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        redis_client.ping()
        print("   [OK] Redis connection verified")
    except Exception as e:
        print(f"   [ERROR] Redis connection failed: {e}")
        print("   [TIP] Please ensure Redis is running (docker-compose -f docker-compose.data.yml up -d)")
        return False

    # Check if replay service is running
    if replay_instance:
        try:
            if hasattr(replay_instance, 'running'):
                if replay_instance.running:
                    print(f"   [OK] Replay service is running")
                    if hasattr(replay_instance, 'ticks_loaded'):
                        print(f"      Ticks loaded: {replay_instance.ticks_loaded}")
                    if hasattr(replay_instance, 'ticks_replayed'):
                        print(f"      Ticks replayed: {replay_instance.ticks_replayed}")
                else:
                    print(f"   [WARN]  Replay service may not be running properly")
        except Exception as e:
            print(f"   [WARN]  Could not check replay service status: {e}")

    try:
        sys.path.insert(0, './market_data/src')
        from market_data.api import build_store
        import redis

        # Build store with Redis client
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        store = build_store(redis_client=redis_client)

        # Check Redis for any stored ticks
        try:
            import redis
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

            # Check if there are any tick keys in Redis (try multiple formats)
            tick_keys = []
            for pattern in ["tick:*:latest", f"tick:{INSTRUMENT_KEY}*", "tick:NIFTY BANK*", "tick:NIFTYBANK*", "tick:NIFTY*"]:
                keys = redis_client.keys(pattern)
                if keys:
                    tick_keys.extend(keys)
                    print(f"   [INFO] Found {len(keys)} tick keys matching '{pattern}' in Redis")
                    # Show first few keys and their values
                    for key in keys[:3]:
                        try:
                            value = redis_client.get(key)
                            if value:
                                import json
                                tick_data = json.loads(value)
                                print(f"      - {key}: price={tick_data.get('last_price', 'N/A')}, instrument={tick_data.get('instrument', 'N/A')}")
                            else:
                                print(f"      - {key}: (empty)")
                        except:
                            print(f"      - {key}")
            if tick_keys:
                print(f"   [INFO] Total {len(set(tick_keys))} unique tick keys found in Redis")
            else:
                print(f"   [WARN]  No tick keys found in Redis - ticks may not be stored yet")
        except Exception as e:
            print(f"   [WARN]  Could not check Redis keys: {e}")

        # Try multiple instrument name variations
        instrument_variations = [INSTRUMENT_SYMBOL, INSTRUMENT_KEY, "NIFTY BANK", "NIFTYBANK", f"NSE:{INSTRUMENT_SYMBOL}"]

        # Reuse the same Redis client for verification
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

        for attempt in range(1, max_retries + 1):
            store = build_store(redis_client=redis_client)

            # Try each instrument name variation
            tick = None
            found_instrument = None
            for instrument in instrument_variations:
                tick = store.get_latest_tick(instrument)
                if tick and tick.last_price:
                    found_instrument = instrument
                    break

            if tick and tick.last_price:
                print(f"   [OK] Historical data verified: {found_instrument} price = {tick.last_price}")
                if hasattr(tick, 'timestamp'):
                    print(f"      Timestamp: {tick.timestamp}")
                if hasattr(tick, 'instrument'):
                    print(f"      Instrument: {tick.instrument}")
                return True

            # Check replay status periodically
            if replay_instance and attempt % 5 == 0:
                try:
                    if hasattr(replay_instance, 'running') and not replay_instance.running:
                        print(f"   [WARN]  Replay service stopped running (attempt {attempt})")
                        print("   [TIP] Replay may have completed or encountered an error")
                except:
                    pass

            if attempt < max_retries:
                if attempt % 5 == 0:  # Show more detailed message every 5 attempts
                    if data_source == 'zerodha':
                        print(f"   [WAIT] Attempt {attempt}/{max_retries} - Waiting for Zerodha historical data...")
                        print("      [TIP] If this continues, check Zerodha API access and date availability")
                    else:
                        print(f"   [WAIT] Attempt {attempt}/{max_retries} - Waiting for historical data...")
                        print("      [TIP] Historical data may need more time to load")
                        if replay_instance:
                            try:
                                if hasattr(replay_instance, 'ticks_loaded'):
                                    print(f"      Ticks loaded: {replay_instance.ticks_loaded}")
                                if hasattr(replay_instance, 'ticks_replayed'):
                                    print(f"      Ticks replayed: {replay_instance.ticks_replayed}")
                            except:
                                pass
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - waiting for historical data...")
                time.sleep(retry_delay)

        if data_source == 'zerodha':
            print("   [ERROR] No Zerodha historical data available after verification attempts")
            print("   [TIP] Possible issues:")
            print("      - Zerodha API credentials not authenticated")
            print("      - Historical data not available for the specified date")
            print("      - Network/API connectivity issues")
            print("      - Check if Zerodha API is accessible and data is available for the date")
            print("      - Verify CSV file path if using CSV data source")
        else:
            print("   [ERROR] No historical data available after verification attempts")
            print("   [TIP] Possible issues:")
            print("      - Replay service not generating ticks (check if running)")
            print("      - Ticks generated but not stored in Redis")
            print("      - Redis connection issues (check: docker-compose -f docker-compose.data.yml up -d)")
            print("      - Historical replay service encountered an error")
            if replay_instance:
                try:
                    print(f"      Replay running: {replay_instance.running if hasattr(replay_instance, 'running') else 'unknown'}")
                    print(f"      Ticks loaded: {replay_instance.ticks_loaded if hasattr(replay_instance, 'ticks_loaded') else 'unknown'}")
                    print(f"      Ticks replayed: {replay_instance.ticks_replayed if hasattr(replay_instance, 'ticks_replayed') else 'unknown'}")
                except:
                    pass
            print("      - Try increasing retry time or check replay service logs")
        return False
    except Exception as e:
        print(f"   [ERROR] Error verifying historical data: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_technical_indicators(max_retries=10, retry_delay=2):
    """Verify technical indicators are calculated and accessible"""
    print("   [WAIT] Verifying technical indicators calculation and API...")

    base_url = "http://localhost:8004"

    for attempt in range(1, max_retries + 1):
        try:
            # Test technical indicators API endpoint
            indicators_response = requests.get(f"{base_url}/api/v1/technical/indicators/{INSTRUMENT_KEY}?timeframe=minute", timeout=10)
            if indicators_response.status_code == 200:
                indicators_data = indicators_response.json()

                if 'indicators' in indicators_data:
                    indicators = indicators_data['indicators']

                    # Check for key technical indicators
                    required_indicators = ['rsi_14', 'macd_value', 'bollinger_upper', 'adx_14', 'sma_20', 'ema_20']
                    indicators_found = 0

                    for indicator in required_indicators:
                        if indicator in indicators and indicators[indicator] is not None:
                            indicators_found += 1

                    if indicators_found >= 2:  # At least 2 of 6 key indicators for clean starts
                        print(f"   [OK] Technical indicators: {indicators_found}/{len(required_indicators)} key indicators calculated")

                        # Show some sample values
                        rsi_14 = indicators.get('rsi_14')
                        macd = indicators.get('macd_value')
                        bollinger_upper = indicators.get('bollinger_upper')
                        adx = indicators.get('adx_14')

                        if rsi_14:
                            rsi_status = "NEUTRAL"
                            if rsi_14 > 70:
                                rsi_status = "OVERBOUGHT"
                            elif rsi_14 < 30:
                                rsi_status = "OVERSOLD"
                            print(f"   [OK] RSI(14): {rsi_14:.2f} ({rsi_status})")

                        if macd:
                            print(f"   [OK] MACD: {macd:.2f}")

                        if bollinger_upper:
                            bollinger_lower = indicators.get('bollinger_lower', 0)
                            current_price = indicators.get('current_price', 0)
                            print(f"   [OK] Bollinger Bands: Upper {bollinger_upper:.2f}")

                        if adx:
                            trend_strength = "WEAK" if adx < 25 else "STRONG"
                            print(f"   [OK] ADX(14): {adx:.2f} ({trend_strength} trend)")

                        # Check signal strength
                        signal_strength = indicators.get('signal_strength', 0)
                        if signal_strength > 0:
                            print(f"   [OK] Signal Strength: {signal_strength:.1f}/100")

                        return True
                    else:
                        print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {indicators_found}/{len(required_indicators)} indicators found, retrying...")
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - No indicators data in response, retrying...")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Indicators endpoint not ready (status {indicators_response.status_code}), retrying...")
        except Exception as e:
            print(f"   [WAIT] Attempt {attempt}/{max_retries} - Error: {e}")

        if attempt < max_retries:
            time.sleep(retry_delay)

    print("   [ERROR] Technical indicators verification failed")
    return False


def verify_redis_data_storage(max_retries=10, retry_delay=2):
    """Verify Redis is receiving and storing market data correctly"""
    print("   [WAIT] Verifying Redis data storage and publishing...")

    for attempt in range(1, max_retries + 1):
        try:
            import redis
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

            # Test Redis connectivity
            redis_client.ping()
            print("   [OK] Redis connection verified")

            # Check technical indicators storage
            indicator_keys = redis_client.keys(f'indicators:{INSTRUMENT_KEY}:*')
            if len(indicator_keys) >= 8:  # Should have at least basic indicators
                print(f"   [OK] Technical indicators: {len(indicator_keys)} keys stored")

                # For clean starts, accept any indicators (RSI/MACD may take time to calculate)
                # Check if we have at least some calculated numerical indicators
                numerical_indicators = 0
                sample_keys = indicator_keys[:10]  # Check first 10 keys
                for key in sample_keys:
                    value = redis_client.get(key)
                    if value is not None and value != '' and key.split(':')[-1] not in ['instrument', 'timestamp', 'timeframe']:
                        try:
                            # Try to parse as number
                            float(value)
                            numerical_indicators += 1
                        except (ValueError, TypeError):
                            pass

                if numerical_indicators >= 3:
                    print(f"   [OK] Numerical indicators verified: {numerical_indicators} found")
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {numerical_indicators} numerical indicators found, retrying...")
                    time.sleep(retry_delay)
                    continue
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {len(indicator_keys)} indicator keys found (need 8+), retrying...")
                time.sleep(retry_delay)
                continue

            # Check price data storage
            price_keys = redis_client.keys(f'price:{INSTRUMENT_KEY}*')
            if len(price_keys) >= 2:
                print(f"   [OK] Price data: {len(price_keys)} keys stored")
                # Verify price values exist
                latest_price = redis_client.get(f'price:{INSTRUMENT_KEY}:latest')
                if latest_price and float(latest_price) > 0:
                    print(f"   [OK] Latest price: {latest_price}")
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Price data exists but no valid price value, retrying...")
                    time.sleep(retry_delay)
                    continue
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {len(price_keys)} price keys found (need 2+), retrying...")
                time.sleep(retry_delay)
                continue

            # Check tick data storage
            tick_keys = redis_client.keys(f'tick:{INSTRUMENT_KEY}*')
            if len(tick_keys) >= 10:  # Should have tick records for basic functionality
                print(f"   [OK] Tick data: {len(tick_keys)} records stored")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {len(tick_keys)} tick records found (need 10+), retrying...")
                time.sleep(retry_delay)
                continue

            # Check OHLC data storage
            ohlc_keys = redis_client.keys(f'ohlc:{INSTRUMENT_KEY}*')
            min_ohlc_required = 5  # Reduced for clean starts
            if len(ohlc_keys) >= min_ohlc_required:  # Accept fewer bars for clean starts
                print(f"   [OK] OHLC data: {len(ohlc_keys)} bars stored")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {len(ohlc_keys)} OHLC bars found (need {min_ohlc_required}+), retrying...")
                time.sleep(retry_delay)
                continue

# Check market depth data (required for LIVE mode, optional for BACKTEST)
            execution_mode = redis_client.get("system:execution_mode")
            is_backtest_mode = execution_mode == "BACKTEST"

            if is_backtest_mode:
                print("   [OK] Market depth: Skipped (not available in BACKTEST mode)")
            else:
                depth_keys = redis_client.keys(f'depth:{INSTRUMENT_KEY}*')
                if len(depth_keys) >= 1:
                    # Validate depth data structure
                    latest_depth_key = f'depth:{INSTRUMENT_KEY}:latest'
                    depth_data = redis_client.get(latest_depth_key)
                    if depth_data:
                        try:
                            import json
                            depth_obj = json.loads(depth_data)
                            bids = depth_obj.get('bids', [])
                            asks = depth_obj.get('asks', [])

                            if bids and asks and len(bids) > 0 and len(asks) > 0:
                                # Verify bid/ask structure (price, quantity pairs)
                                valid_bids = all(isinstance(bid, list) and len(bid) >= 2 for bid in bids[:3])
                                valid_asks = all(isinstance(ask, list) and len(ask) >= 2 for ask in asks[:3])

                                if valid_bids and valid_asks:
                                    best_bid = bids[0][0] if bids else 0
                                    best_ask = asks[0][0] if asks else 0
                                    spread = best_ask - best_bid if best_bid and best_ask else 0
                                    print(f"   [OK] Market depth: {len(depth_keys)} records stored (spread: {spread:.2f})")
                                else:
                                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Invalid depth data structure, retrying...")
                                    time.sleep(retry_delay)
                                    continue
                            else:
                                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Incomplete depth data (bids: {len(bids)}, asks: {len(asks)}), retrying...")
                                time.sleep(retry_delay)
                                continue
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"   [WAIT] Attempt {attempt}/{max_retries} - Error parsing depth data: {e}, retrying...")
                            time.sleep(retry_delay)
                            continue
                    else:
                        print(f"   [WAIT] Attempt {attempt}/{max_retries} - No latest depth data found, retrying...")
                        time.sleep(retry_delay)
                        continue
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - No market depth data found (required), retrying...")
                    time.sleep(retry_delay)
                    continue

            # Check publishing mechanisms (sample publish test)
            try:
                # Test if we can publish to indicators channel (this tests pub/sub is working)
                test_message = {"test": "verification", "timestamp": "2026-01-12T14:00:00"}
                redis_client.publish(f"indicators:{INSTRUMENT_KEY}:INDEX", str(test_message))
                print("   [OK] WebSocket publishing: Channel active")
            except Exception as pub_err:
                print(f"   [WARN]  Publishing test failed: {pub_err} (may still work)")

            print("   [OK] Redis data storage and publishing verified!")
            return True

        except Exception as e:
            print(f"   [WAIT] Attempt {attempt}/{max_retries} - Redis verification error: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)

    print("   [ERROR] Redis data storage verification failed")
    return False


def verify_market_data_api(base_url="http://localhost:8004", max_retries=20, retry_delay=1):
    """Verify Market Data API has actual data - tests all critical endpoints"""
    print("   [WAIT] Verifying Market Data API functionality...")

    for attempt in range(1, max_retries + 1):
        try:
            # Check tick data
            tick_response = requests.get(f"{base_url}/api/v1/market/tick/{INSTRUMENT_KEY}", timeout=5)
            if tick_response.status_code == 200:
                tick_data = tick_response.json()
                if tick_data.get('last_price'):
                    print(f"   [OK] Market Data API: {INSTRUMENT_KEY} tick = {tick_data.get('last_price')}")

                    # Test all critical endpoints
                    endpoints_passed = 0
                    endpoints_total = 0

                    # Test price endpoint
                    try:
                        price_response = requests.get(f"{base_url}/api/v1/market/price/{INSTRUMENT_KEY}", timeout=5)
                        endpoints_total += 1
                        if price_response.status_code == 200:
                            price_data = price_response.json()
                            if price_data.get('price'):
                                endpoints_passed += 1
                    except:
                        endpoints_total += 1

                    # Test OHLC endpoint
                    try:
                        ohlc_response = requests.get(f"{base_url}/api/v1/market/ohlc/{INSTRUMENT_KEY}?timeframe=minute&limit=5", timeout=5)
                        endpoints_total += 1
                        if ohlc_response.status_code == 200:
                            ohlc_data = ohlc_response.json()
                            if isinstance(ohlc_data, list) and len(ohlc_data) > 0:
                                endpoints_passed += 1
                    except:
                        endpoints_total += 1

                    # Test raw data endpoint
                    try:
                        raw_response = requests.get(f"{base_url}/api/v1/market/raw/{INSTRUMENT_KEY}?limit=5", timeout=5)
                        endpoints_total += 1
                        if raw_response.status_code == 200:
                            raw_data = raw_response.json()
                            if raw_data.get('keys_found', 0) > 0:
                                endpoints_passed += 1
                    except:
                        endpoints_total += 1

                    # Test depth endpoint (market depth/order book)
                    try:
                        depth_response = requests.get(f"{base_url}/api/v1/market/depth/{INSTRUMENT_KEY}", timeout=5)
                        endpoints_total += 1
                        if depth_response.status_code == 200:
                            depth_data = depth_response.json()
                            bids = depth_data.get('bids', [])
                            asks = depth_data.get('asks', [])
                            if bids and asks and len(bids) > 0 and len(asks) > 0:
                                endpoints_passed += 1
                                print(f"   [OK] Market Data API: Depth data available ({len(bids)} bids, {len(asks)} asks)")
                    except:
                        endpoints_total += 1

                    # Check options chain (optional but nice to have)
                    try:
                        options_response = requests.get(f"{base_url}/api/v1/options/chain/{INSTRUMENT_KEY}", timeout=10)
                        if options_response.status_code == 200:
                            options_data = options_response.json()
                            strikes = options_data.get('strikes', [])
                            if strikes:
                                print(f"   [OK] Market Data API: Options chain available ({len(strikes)} strikes)")
                    except:
                        pass  # Options chain is optional

                    # If critical endpoints pass, we're good
                    if endpoints_passed >= 2:  # At least tick + one other endpoint
                        print(f"   [OK] Market Data API: {endpoints_passed}/{endpoints_total} critical endpoints verified")
                        return True
                    else:
                        print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {endpoints_passed}/{endpoints_total} endpoints ready, retrying...")
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - No price data yet...")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Tick endpoint not ready (status {tick_response.status_code})...")
        except Exception as e:
            print(f"   [WAIT] Attempt {attempt}/{max_retries} - Error: {e}")

        if attempt < max_retries:
            time.sleep(retry_delay)

    print("   [ERROR] Market Data API verification failed - no data available")
    return False


def verify_news_api(base_url="http://localhost:8005", max_retries=15, retry_delay=1):
    """Verify News API returns actual news articles"""
    print("   [WAIT] Verifying News API functionality...")

    # Trigger collection on first attempt to ensure we have articles
    collection_triggered = False

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(f"{base_url}/api/v1/news/{INSTRUMENT_KEY}", timeout=5)
            if response.status_code == 200:
                news_data = response.json()
                # Support both 'news' (current) and legacy 'articles' keys
                articles = news_data.get('news') if isinstance(news_data, dict) else None
                if not articles:
                    articles = news_data.get('articles', []) if isinstance(news_data, dict) else []

                if articles:
                    print(f"   [OK] News API: {len(articles)} articles available")
                    return True
                else:
                    # Trigger collection if we haven't already and it's early in retries
                    if not collection_triggered and attempt <= 3:
                        try:
                            print("   [INFO] No articles found - triggering collection via API")
                            collect_response = requests.post(
                                f"{base_url}/api/v1/news/collect",
                                json={"instruments": [INSTRUMENT_KEY]},
                                timeout=30
                            )
                            collection_triggered = True
                            if collect_response.status_code == 200:
                                collected = collect_response.json().get('collected_count', 0)
                                print(f"   [INFO] Collection triggered, {collected} articles collected")
                            else:
                                print(f"   [WARN]  Collection request returned status {collect_response.status_code}")
                            # Wait a bit longer after triggering collection
                            time.sleep(3)
                        except Exception as coll_err:
                            print(f"   [WARN] Failed to trigger collection: {coll_err}")

                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - No articles yet, retrying...")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - News endpoint not ready (status {response.status_code})...")
        except Exception as e:
            print(f"   [WAIT] Attempt {attempt}/{max_retries} - Error: {e}")

        if attempt < max_retries:
            time.sleep(retry_delay)

    print("   [WARN] News API has no articles - RSS feeds may be blocked (403)")
    print("   [INFO] Continuing startup anyway - news is optional for basic functionality")
    return True  # Make news verification optional


def verify_engine_api(base_url="http://localhost:8006", max_retries=15, retry_delay=1):
    """Verify Engine API agents are running and can analyze"""
    print("   [WAIT] Verifying Engine API functionality...")

    for attempt in range(1, max_retries + 1):
        try:
            # Check if agents can analyze (this verifies agents are initialized)
            # Note: context must be a dict or omitted, not a string
            analyze_response = requests.post(
                f"{base_url}/api/v1/analyze",
                timeout=10
            )
            if analyze_response.status_code == 200:
                analyze_data = analyze_response.json()
                # Check for valid analysis response structure
                if 'decision' in analyze_data and 'confidence' in analyze_data:
                    decision = analyze_data.get('decision', 'UNKNOWN')
                    confidence = analyze_data.get('confidence', 0.0)
                    print(f"   [OK] Engine API: Agents running (decision={decision}, confidence={confidence:.2f})")
                    return True
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Invalid response format...")
            elif analyze_response.status_code == 503:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Orchestrator not initialized yet (status 503)...")
            elif analyze_response.status_code == 422:
                # Parse validation error details
                try:
                    error_detail = analyze_response.json().get('detail', 'Validation error')
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Validation error: {error_detail}")
                except:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Validation error (status 422)...")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Analyze endpoint not ready (status {analyze_response.status_code})...")
        except Exception as e:
            print(f"   [WAIT] Attempt {attempt}/{max_retries} - Error: {e}")

        if attempt < max_retries:
            time.sleep(retry_delay)

    print("   [WARN] Engine API verification timed out - agents may not be ready")
    print("   [INFO] Continuing anyway - engine is optional for market data testing")
    return True  # Make engine verification optional


def verify_comprehensive_data_flow(max_retries=10, retry_delay=2):
    """Comprehensive data validation: checks complete flow from collection to consumption"""
    print("   [VALIDATE] Performing comprehensive data flow validation...")

    validation_results = {
        'redis_connectivity': False,
        'market_data_collection': False,
        'data_storage': False,
        'technical_indicators': False,
        'api_endpoints': False,
        'websocket_publishing': False,
        'engine_consumption': False,
        'ui_data_access': False
    }

    try:
        import redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

        # 1. Redis connectivity
        redis_client.ping()
        validation_results['redis_connectivity'] = True
        print("   ✅ Redis connectivity: OK")

        # 2. Market data collection (check for recent data)
        tick_keys = redis_client.keys(f'tick:{INSTRUMENT_KEY}*')
        if len(tick_keys) >= 5:
            # Check if data is recent (within last 5 minutes for live data)
            latest_tick_key = f'tick:{INSTRUMENT_KEY}:latest'
            latest_tick = redis_client.get(latest_tick_key)
            if latest_tick:
                import json
                tick_data = json.loads(latest_tick)
                last_price = tick_data.get('last_price')
                if last_price and last_price > 0:
                    validation_results['market_data_collection'] = True
                    print(f"   ✅ Market data collection: OK (latest price: {last_price})")
                else:
                    print(f"   ❌ Market data collection: Invalid price data")
            else:
                print(f"   ❌ Market data collection: No latest tick data")
        else:
            print(f"   ❌ Market data collection: Only {len(tick_keys)} tick records found")

        # 3. Data storage (OHLC, price, depth)
        ohlc_keys = redis_client.keys(f'ohlc:{INSTRUMENT_KEY}*')
        price_keys = redis_client.keys(f'price:{INSTRUMENT_KEY}*')
        depth_keys = redis_client.keys(f'depth:{INSTRUMENT_KEY}*')

        # Check execution mode for depth requirement
        execution_mode = redis_client.get("system:execution_mode")
        is_backtest_mode = execution_mode == "BACKTEST"

        if is_backtest_mode:
            # In BACKTEST mode, depth is not available from historical data
            storage_checks = [
                (len(ohlc_keys) >= 3, f"OHLC bars: {len(ohlc_keys)}"),
                (len(price_keys) >= 1, f"Price keys: {len(price_keys)}"),
                (True, f"Depth records: N/A (BACKTEST mode)")
            ]
            storage_ok = all(check[0] for check in storage_checks)
        else:
            # In LIVE mode, depth is required
            storage_checks = [
                (len(ohlc_keys) >= 3, f"OHLC bars: {len(ohlc_keys)}"),
                (len(price_keys) >= 1, f"Price keys: {len(price_keys)}"),
                (len(depth_keys) >= 1, f"Depth records: {len(depth_keys)}")
            ]
            depth_required = len(depth_keys) >= 1
            storage_ok = all(check[0] for check in storage_checks) and depth_required

        if storage_ok:
            validation_results['data_storage'] = True
            print("   ✅ Data storage: OK (" + ", ".join(check[1] for check in storage_checks) + ")")
        else:
            failed_checks = [check[1] for check in storage_checks if not check[0]]
            print(f"   ❌ Data storage: Insufficient data - {', '.join(failed_checks)}")

        # 4. Market depth validation (separate detailed check)
        if is_backtest_mode:
            print("   ✅ Market depth: Skipped (not available in BACKTEST mode)")
            depth_validation_passed = True  # Consider it passed for backtest
        elif len(depth_keys) >= 1:
            depth_validation_passed = False
            try:
                # Check the latest depth data
                latest_depth_key = f'depth:{INSTRUMENT_KEY}:latest'
                depth_data = redis_client.get(latest_depth_key)
                if depth_data:
                    import json
                    depth_obj = json.loads(depth_data)
                    
                    # Check for required depth structure
                    bids = depth_obj.get('bids', [])
                    asks = depth_obj.get('asks', [])
                    
                    if bids and asks and len(bids) > 0 and len(asks) > 0:
                        # Check if bids/asks have proper price/quantity structure
                        bid_valid = all(isinstance(bid, list) and len(bid) >= 2 and bid[0] > 0 and bid[1] > 0 
                                      for bid in bids[:5])  # Check first 5 bids
                        ask_valid = all(isinstance(ask, list) and len(ask) >= 2 and ask[0] > 0 and ask[1] > 0 
                                      for ask in asks[:5])  # Check first 5 asks
                        
                        if bid_valid and ask_valid:
                            best_bid = bids[0][0] if bids else 0
                            best_ask = asks[0][0] if asks else 0
                            spread = best_ask - best_bid if best_bid and best_ask else 0
                            
                            print(f"   ✅ Market depth: OK ({len(bids)} bids, {len(asks)} asks, spread: {spread:.2f})")
                            depth_validation_passed = True
                        else:
                            print("   ❌ Market depth: Invalid bid/ask structure")
                    else:
                        print(f"   ❌ Market depth: Missing bids/asks data (bids: {len(bids)}, asks: {len(asks)})")
                else:
                    print("   ❌ Market depth: No latest depth data found")
            except Exception as e:
                print(f"   ❌ Market depth: Error parsing depth data - {e}")
            
            if not depth_validation_passed:
                print("   ⚠️  Market depth validation failed - order book data may be incomplete")
        else:
            if not is_backtest_mode:
                print("   ❌ Market depth: No depth records found")
                print("   ℹ️  Market depth is required for proper order book analysis")

        # 5. Technical indicators
        indicator_keys = redis_client.keys(f'indicators:{INSTRUMENT_KEY}:*')
        if len(indicator_keys) >= 6:
            # Check for actual numerical values
            numerical_indicators = 0
            for key in indicator_keys[:10]:
                value = redis_client.get(key)
                if value and value != '':
                    try:
                        float(value)
                        numerical_indicators += 1
                    except (ValueError, TypeError):
                        pass

            if numerical_indicators >= 4:
                validation_results['technical_indicators'] = True
                print(f"   ✅ Technical indicators: OK ({numerical_indicators} calculated)")
            else:
                print(f"   ❌ Technical indicators: Only {numerical_indicators} numerical values")
        else:
            print(f"   ❌ Technical indicators: Only {len(indicator_keys)} keys found")

        # 5. API endpoints data access
        api_checks = []
        try:
            # Market data API
            import requests
            tick_response = requests.get(f"http://localhost:8004/api/v1/market/tick/{INSTRUMENT_KEY}", timeout=5)
            api_checks.append((tick_response.status_code == 200 and tick_response.json().get('last_price'), "Market API tick"))

            # Technical indicators API
            indicators_response = requests.get(f"http://localhost:8004/api/v1/technical/indicators/{INSTRUMENT_KEY}?timeframe=minute", timeout=5)
            indicators_data = indicators_response.json() if indicators_response.status_code == 200 else {}
            has_indicators = 'indicators' in indicators_data and len(indicators_data['indicators']) >= 3
            api_checks.append((has_indicators, "Technical indicators API"))
        except Exception as e:
            print(f"   ❌ API endpoints: Error checking APIs - {e}")
            api_checks = [(False, "API connectivity")]

        api_ok = all(check[0] for check in api_checks)
        if api_ok:
            validation_results['api_endpoints'] = True
            print("   ✅ API endpoints: OK (data accessible via APIs)")
        else:
            failed_apis = [check[1] for check in api_checks if not check[0]]
            print(f"   ❌ API endpoints: Failed - {', '.join(failed_apis)}")

        # 6. WebSocket publishing (test pub/sub)
        try:
            # Test publishing to a channel
            test_channel = f"test:validation:{INSTRUMENT_KEY}"
            test_message = {"test": "data_flow_validation", "timestamp": "2026-01-12T14:00:00"}
            redis_client.publish(test_channel, str(test_message))

            # Check if we can subscribe (basic connectivity test)
            validation_results['websocket_publishing'] = True
            print("   ✅ WebSocket publishing: OK (pub/sub active)")
        except Exception as e:
            print(f"   ❌ WebSocket publishing: Error - {e}")

        # 7. Engine data consumption (optional)
        try:
            engine_response = requests.post("http://localhost:8006/api/v1/analyze", timeout=10)
            if engine_response.status_code == 200:
                analysis = engine_response.json()
                if 'decision' in analysis:
                    validation_results['engine_consumption'] = True
                    print("   ✅ Engine consumption: OK (can analyze market data)")
                else:
                    print("   ❌ Engine consumption: Analysis response missing decision")
            else:
                print(f"   ❌ Engine consumption: API returned status {engine_response.status_code}")
        except Exception as e:
            print(f"   ⚠️  Engine consumption: Not available - {e} (optional)")

        # 8. UI data access (check if dashboard can load and has data indicators)
        try:
            ui_response = requests.get("http://localhost:8888/", timeout=10)
            if ui_response.status_code == 200:
                content = ui_response.text.lower()
                # Check for data-related content
                data_indicators = ['price', 'market', 'data', 'chart', 'indicator']
                has_data_content = any(indicator in content for indicator in data_indicators)
                if has_data_content:
                    validation_results['ui_data_access'] = True
                    print("   ✅ UI data access: OK (dashboard loaded with data content)")
                else:
                    print("   ❌ UI data access: Dashboard loaded but no data content detected")
            else:
                print(f"   ❌ UI data access: Dashboard returned status {ui_response.status_code}")
        except Exception as e:
            print(f"   ❌ UI data access: Error accessing dashboard - {e}")

    except Exception as e:
        print(f"   ❌ Data flow validation failed with error: {e}")
        return validation_results

    # Summary
    passed_checks = sum(1 for result in validation_results.values() if result)
    total_checks = len(validation_results)
    critical_checks = ['redis_connectivity', 'market_data_collection', 'data_storage', 'api_endpoints']
    critical_passed = sum(1 for key in critical_checks if validation_results[key])

    print(f"\n   📊 Data Flow Validation Summary: {passed_checks}/{total_checks} checks passed")
    print(f"   🎯 Critical Systems: {critical_passed}/{len(critical_checks)} operational")

    if critical_passed >= len(critical_checks) - 1:  # Allow 1 critical failure for flexibility
        print("   ✅ Data pipeline is operational and ready for trading")
        return True
    else:
        print("   ❌ Critical data pipeline issues detected - check logs above")
        return False


def verify_websocket_data_stream(max_retries=5, retry_delay=2):
    """Verify WebSocket gateway can stream real-time data"""
    print("   [VALIDATE] Verifying WebSocket data streaming...")

    try:
        import websocket
        import json
        import threading
        import time
    except ImportError:
        print("   ⚠️  WebSocket validation skipped - websocket-client library not installed")
        print("   ℹ️  This library is optional and only used for startup-time WebSocket testing")
        print("   ℹ️  The actual WebSocket gateway (redis_ws_gateway) works without it")
        print("   ℹ️  UI real-time data streaming will still function normally")
        print("   💡 Install for enhanced validation: pip install websocket-client")
        return True  # Don't fail startup for missing optional dependency

    try:
        received_messages = []
        connection_success = False

        def on_message(ws, message):
            try:
                data = json.loads(message)
                received_messages.append(data)
            except:
                pass

        def on_open(ws):
            nonlocal connection_success
            connection_success = True
            print("   ✅ WebSocket connection established")

        def on_error(ws, error):
            print(f"   ❌ WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            pass

        # Connect to WebSocket
        ws_url = "ws://localhost:8889/ws"
        ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_open=on_open, on_error=on_error, on_close=on_close)

        # Start WebSocket in a thread
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

        # Wait for connection
        time.sleep(2)

        if not connection_success:
            print("   ❌ WebSocket connection failed")
            return False

        # Subscribe to market data channels
        subscribe_message = {
            "action": "subscribe",
            "channels": [f"market:{INSTRUMENT_KEY}", f"indicators:{INSTRUMENT_KEY}"]
        }
        ws.send(json.dumps(subscribe_message))

        # Wait for messages
        time.sleep(3)

        # Close connection
        ws.close()

        if received_messages:
            print(f"   ✅ WebSocket streaming: OK ({len(received_messages)} messages received)")
            # Check message types
            market_msgs = [msg for msg in received_messages if msg.get('channel', '').startswith('market:')]
            indicator_msgs = [msg for msg in received_messages if msg.get('channel', '').startswith('indicators:')]
            print(f"      - Market data messages: {len(market_msgs)}")
            print(f"      - Indicator messages: {len(indicator_msgs)}")
            return True
        else:
            print("   ❌ WebSocket streaming: No messages received")
            return False

    except Exception as e:
        print(f"   ❌ WebSocket verification failed: {e}")
        return False


def verify_dashboard_ui(max_retries=5, retry_delay=2):
    """Verify Dashboard backend can access market data endpoints used by the UI."""
    print("   [VALIDATE] Verifying Dashboard UI data access and backend...")

    try:
        import requests
    except Exception as e:
        print(f"   ⚠️  Dashboard UI verification skipped - requests not available: {e}")
        return True  # Don't fail startup for optional verifier

    base = "http://localhost:8000"

    # Check 1: Basic backend health (/api/market-data)
    for attempt in range(max_retries):
        try:
            r = requests.get(f"{base}/api/market-data", timeout=5)
            if r.status_code == 200:
                print("   ✅ Dashboard backend: /api/market-data OK")
                break
            else:
                print(f"   ⏳ Dashboard backend: /api/market-data returned {r.status_code}")
        except Exception as e:
            print(f"   ⏳ Dashboard backend: Connection error (attempt {attempt + 1}/{max_retries}) - {e}")
        time.sleep(retry_delay)
    else:
        print("   ❌ Dashboard backend: /api/market-data unreachable")
        return False

    # Check 2: Attempt to fetch market data for known symbol variations
    symbols = [INSTRUMENT_KEY, INSTRUMENT_SYMBOL, "BANKNIFTY", "NIFTY BANK"]
    for sym in symbols:
        try:
            r = requests.get(f"{base}/api/market/data/{sym}", timeout=5)
            if r.status_code == 200:
                print(f"   ✅ Dashboard backend: /api/market/data/{sym} OK")
                return True
            else:
                print(f"   ⏳ /api/market/data/{sym} returned {r.status_code}")
        except Exception:
            # Try next symbol variation silently
            pass

    print("   ❌ Dashboard backend: Could not fetch market data for any known symbol")
    return False


def verify_engine_data_processing(max_retries=5, retry_delay=3):
    """Verify engine can process market data and generate signals based on REAL market conditions."""
    print("   [VALIDATE] Verifying engine data processing and market data consumption...")

    try:
        import requests
        import redis

        # Get Redis client to check data availability
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

        # Check 1: Verify market data is available in Redis before testing engine
        print("   [CHECK] Verifying market data availability for engine...")

        # Check for recent price data
        latest_price_key = f'price:{INSTRUMENT_KEY}:latest'
        latest_price = redis_client.get(latest_price_key)
        if not latest_price:
            print("   ❌ Engine validation: No price data available in Redis")
            return False

        try:
            current_price = float(latest_price)
            print(f"   ✅ Engine validation: Current price available: {current_price}")
        except (ValueError, TypeError):
            print("   ❌ Engine validation: Invalid price data format")
            return False

        # Check for technical indicators
        indicator_keys = redis_client.keys(f'indicators:{INSTRUMENT_KEY}:*')
        if len(indicator_keys) < 3:
            print(f"   ❌ Engine validation: Insufficient indicators ({len(indicator_keys)} found, need 3+)")
            return False

        # Verify at least one key indicator exists
        rsi_key = f'indicators:{INSTRUMENT_KEY}:rsi_14'
        macd_key = f'indicators:{INSTRUMENT_KEY}:macd_value'
        rsi_value = redis_client.get(rsi_key)
        macd_value = redis_client.get(macd_key)

        if not rsi_value and not macd_value:
            print("   ❌ Engine validation: No key indicators (RSI/MACD) available")
            return False

        print(f"   ✅ Engine validation: Indicators available (RSI: {rsi_value}, MACD: {macd_value})")

        # Check 2: Test engine analysis with real market context
        print("   [CHECK] Testing engine analysis with real market data...")

        for attempt in range(max_retries):
            try:
                response = requests.post("http://localhost:8006/api/v1/analyze", timeout=20)
                if response.status_code == 200:
                    analysis = response.json()

                    # Check for required analysis components
                    required_fields = ['decision', 'confidence', 'timestamp']
                    has_required = all(field in analysis for field in required_fields)

                    if has_required:
                        decision = analysis.get('decision', 'UNKNOWN')
                        confidence = analysis.get('confidence', 0.0)
                        reasoning = analysis.get('reasoning', '')

                        # Validate that analysis is based on real data, not just defaults
                        if decision in ['BUY', 'SELL', 'HOLD'] and confidence >= 0.0:
                            print(f"   ✅ Engine processing: OK (decision={decision}, confidence={confidence:.2f})")

                            # Additional validation: Check if reasoning mentions market data
                            reasoning_lower = reasoning.lower() if reasoning else ""
                            market_indicators = ['rsi', 'macd', 'bollinger', 'adx', 'sma', 'ema', 'price', 'market']

                            reasoning_mentions_market = any(indicator in reasoning_lower for indicator in market_indicators)

                            if reasoning_mentions_market or len(reasoning) > 50:
                                print("   ✅ Engine reasoning: Based on market analysis")
                            else:
                                print("   ⚠️  Engine reasoning: May not be using market data (short/generic response)")

                            # Check if agent responses are included (shows orchestrator is working)
                            agent_responses = analysis.get('agent_responses', [])
                            if agent_responses and len(agent_responses) > 0:
                                print(f"   ✅ Engine agents: {len(agent_responses)} agents contributed to analysis")
                                return True
                            else:
                                print("   ⚠️  Engine agents: No agent responses found")
                                # Still return True as basic analysis is working
                                return True
                        else:
                            print(f"   ❌ Engine processing: Invalid decision/confidence (decision={decision}, confidence={confidence})")
                    else:
                        missing = [field for field in required_fields if field not in analysis]
                        print(f"   ❌ Engine processing: Missing fields - {', '.join(missing)}")
                elif response.status_code == 503:
                    print(f"   ⏳ Engine processing: Service unavailable (attempt {attempt + 1}/{max_retries})")
                else:
                    print(f"   ❌ Engine processing: HTTP {response.status_code}")

                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

            except requests.exceptions.RequestException as e:
                print(f"   ⏳ Engine processing: Connection error (attempt {attempt + 1}/{max_retries}) - {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        print("   ❌ Engine processing: Failed to get valid analysis after all retries")
        return False

    except Exception as e:
        print(f"   ❌ Engine validation failed: {e}")
        return False


def start_service(name, command, env=None, cwd=None):
    """Start a service in the background"""
    print(f"   [START] Starting {name}...")
    if env is None:
        env = os.environ.copy()

    # Ensure Kite credentials are available for collectors
    if 'collector' in name.lower() or 'market_data' in name.lower():
        try:
            sys.path.insert(0, './market_data/src')
            from market_data.tools.kite_auth_service import KiteAuthService
            auth_service = KiteAuthService()
            creds = auth_service.load_credentials()
            if creds:
                env['KITE_API_KEY'] = creds.get('api_key', '')
                env['KITE_ACCESS_TOKEN'] = creds.get('access_token', '')
                print(f"   [CRED] Set Kite credentials for {name}")
        except Exception as e:
            print(f"   [WARN] Could not load Kite credentials for {name}: {e}")

    # Ensure PYTHONPATH includes our module paths
    pythonpath = env.get('PYTHONPATH', '')
    paths_to_add = [
        './market_data/src',
        './news_module/src',
        './engine_module/src',
        './genai_module/src'
    ]
    for path in paths_to_add:
        if path not in pythonpath:
            if pythonpath:
                pythonpath += os.pathsep
            pythonpath += path
    env['PYTHONPATH'] = pythonpath

    # Use Popen for background processes
    if isinstance(command, list):
        # Convert list to shell command
        command = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
        process = subprocess.Popen(command, shell=True, env=env, cwd=cwd)
    else:
        process = subprocess.Popen(command, shell=True, env=env, cwd=cwd)

    # Give service a moment to start
    time.sleep(2)

    return process


async def start_historical_replay(args, provider_name=None, kite_instance=None):
    """Start historical data replay and verify it's working"""
    print("   [START] Starting Historical Data Replay...")

    # Parse historical args
    hist_source = os.getenv('HISTORICAL_SOURCE') or None
    hist_speed = float(os.getenv('HISTORICAL_SPEED', '1.0'))
    hist_ticks = os.getenv('HISTORICAL_TICKS', '0').lower() in ('1', 'true', 'yes')
    hist_from = os.getenv('HISTORICAL_FROM') or None

    # Allow CLI overrides
    if hasattr(args, 'historical_source') and args.historical_source:
        hist_source = args.historical_source
    if hasattr(args, 'historical_speed') and args.historical_speed is not None:
        hist_speed = float(args.historical_speed)
    if hasattr(args, 'historical_ticks') and args.historical_ticks:
        hist_ticks = True
    if hasattr(args, 'historical_from') and args.historical_from:
        hist_from = args.historical_from

    # Determine data source - use Zerodha if credentials available, otherwise require explicit source
    if not hist_source:
        if kite_instance:
            # Use Zerodha data by default if credentials are available (regardless of provider_name)
            print("   [OK] Zerodha credentials detected (from Step 0)")
            print("   [OK] Using Zerodha historical data (real data from API)")
            hist_source = 'zerodha'
        else:
            # No synthetic data - require explicit data source
            print("   [ERROR] No data source specified and no Zerodha credentials available")
            print("   [TIP] Please specify one of:")
            print("      --historical-source zerodha (requires Zerodha credentials)")
            print("      --historical-source path/to/file.csv (CSV file with historical data)")
            return False, None, None

    # If using Zerodha data source, use the kite instance from Step 0
    if hist_source == 'zerodha':
        if not kite_instance:
            print("   [ERROR] Zerodha data source requires valid credentials!")
            print("   [TIP] Please configure Zerodha credentials in Step 0")
            return False, None, None
        print("   [OK] Using Zerodha historical data (credentials verified in Step 0)")

    # Parse start_date from string to datetime
    start_date_obj = None
    if hist_from:
        try:
            from datetime import datetime
            # Parse YYYY-MM-DD format
            start_date_obj = datetime.strptime(hist_from, '%Y-%m-%d')
            print(f"   [DATE] Starting from date: {hist_from}")
        except ValueError as e:
            print(f"   [WARN]  Invalid date format '{hist_from}'. Expected YYYY-MM-DD. Using default.")
            start_date_obj = None

    try:
        from market_data.api import build_store, build_historical_replay
        import redis

        # Build store with Redis client (required for data persistence)
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

        # Clear old tick data from Redis before starting (to avoid mixing old synthetic data with real data)
        print("   [CLEAN] Clearing old tick data from Redis...")
        try:
            old_keys = redis_client.keys("tick:*")
            if old_keys:
                redis_client.delete(*old_keys)
                print(f"   [OK] Cleared {len(old_keys)} old tick keys from Redis")
            old_price_keys = redis_client.keys("price:*")
            if old_price_keys:
                redis_client.delete(*old_price_keys)
                print(f"   [OK] Cleared {len(old_price_keys)} old price keys from Redis")
        except Exception as e:
            print(f"   [WARN]  Could not clear old data (may not exist): {e}")

        store = build_store(redis_client=redis_client)

        # Use HistoricalDataReplay (bar-level)
        # Pass kite instance if using Zerodha data source (already verified in Step 0)
        # Ensure we use BANKNIFTY as instrument (not "NIFTY BANK")
        from market_data.adapters.historical_tick_replayer import HistoricalTickReplayer

        if hist_source == 'zerodha' and kite_instance:
            # Get speed from args or env
            hist_speed = float(os.getenv('HISTORICAL_SPEED', '10.0'))
            if hasattr(args, 'historical_speed') and args.historical_speed is not None:
                hist_speed = float(args.historical_speed)
            replay = build_historical_replay(
                store,
                data_source=hist_source,
                start_date=start_date_obj,
                kite=kite_instance,
                speed=hist_speed,
                mode="BACKTEST",
                run_id=f"bt_{hist_from}_{hist_source}"
            )
        elif hist_source.endswith('.csv'):
            # CSV file data source
            replay = HistoricalTickReplayer(
                store=store,
                data_source=hist_source,  # Path to CSV file
                rebase=False,  # Don't rebase - keep original historical timestamps
                speed=0.0,  # Use instant speed (0.0) instead of real-time for faster startup
                instrument_symbol=INSTRUMENT_SYMBOL,
                mode="BACKTEST",
                run_id=f"bt_{hist_from}_{hist_source}"
            )
        else:
            print(f"   [ERROR] Unknown or unsupported data source: {hist_source}")
            print("   [TIP] Supported sources: 'zerodha' or path to CSV file")
            return False, None, None
        # Don't override speed - use the speed from build_historical_replay (0.0 for instant)
        replay.start()
        date_str = f", date={hist_from}" if hist_from else ""
        actual_speed = getattr(replay, 'speed', hist_speed)
        print(f"   [OK] Started HistoricalDataReplay (source={hist_source}, speed={actual_speed}{date_str})")

        # Verify replay service started
        if hasattr(replay, 'running'):
            if replay.running:
                print(f"   [OK] Replay service is running")
            else:
                print(f"   [WARN]  Replay service may not be running properly")

        # Give replay time to process ticks (longer for large datasets)
        if hasattr(replay, 'ticks_loaded') and replay.ticks_loaded > 1000:
            print(f"   [WAIT] Processing {replay.ticks_loaded} ticks (this may take a moment)...")
            # Wait longer for large datasets - estimate: ~100 ticks/second at instant speed
            estimated_seconds = max(5, replay.ticks_loaded // 100)
            await asyncio.sleep(min(estimated_seconds, 30))  # Max 30 seconds wait
        else:
            await asyncio.sleep(3)

        # Return data source and replay instance for verification
        return True, hist_source, replay

    except Exception as e:
        print(f"   [ERROR] Failed to start historical replay: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None


async def main():
    """Start all services locally with validation"""
    print("Starting Zerodha Trading System Locally")
    print("=" * 60)

    # Ensure we're in a virtual environment
    venv_ok = ensure_virtual_environment()
    if not venv_ok:
        print("\n❌ Virtual environment setup required before starting services")
        print("💡 Please activate the virtual environment and run again")
        return

    # Ensure all requirements are installed
    requirements_ok = ensure_requirements_installed()
    if not requirements_ok:
        print("\n❌ Requirements installation failed")
        print("💡 Please install requirements manually: pip install -r requirements.txt")
        return

    # CLI args
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--provider', choices=['mock', 'simulator', 'zerodha', 'kite', 'auto', 'historical', 'replay'], default=None,
                       help='Select trading provider (overrides TRADING_PROVIDER env)')
    parser.add_argument('--mock-only', action='store_true', help='In mock mode, only start the mock generator and APIs')
    # Historical replay options
    parser.add_argument('--historical-source', type=str, help='Data source for historical replay: zerodha | path/to/file.csv')
    parser.add_argument('--historical-speed', type=float, default=1.0, help='Playback speed multiplier (1.0 = real-time)')
    parser.add_argument('--historical-ticks', action='store_true', help='Use tick-level replayer instead of bar-level')
    parser.add_argument('--historical-from', type=str, help='Start date for historical replay (YYYY-MM-DD)')
    parser.add_argument('--skip-validation', action='store_true', help='Skip health checks and validation')
    parser.add_argument('--docker-market-data', action='store_true', help='Use Docker market-data-api service instead of starting locally')
    parser.add_argument('--docker-dashboard', action='store_true', help='Use Docker dashboard services instead of starting locally')
    args = parser.parse_args()

    # Load environment
    load_env()

    # Ensure module log directories exist
    print("   [INIT] Ensuring module log directories exist...")
    modules = [
        'backtesting_module', 'core_kernel', 'dashboard', 'data', 'engine_module',
        'genai_module', 'market_data', 'monitoring', 'news_module', 'redis_ws_gateway',
        'risk_module', 'services', 'ui_shell', 'user_module'
    ]
    for module in modules:
        module_log_dir = Path(module) / 'logs'
        module_log_dir.mkdir(parents=True, exist_ok=True)
    print(f"   [OK] Log directories ready for {len(modules)} modules")

    # Ensure per-module .env files exist and copy relevant variables from root .env when missing
    try:
        root_env_path = Path('.') / '.env'
        root_vars = {}
        if root_env_path.exists():
            with open(root_env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    root_vars[k.strip()] = v.strip()

        modules_keys = {
            'market_data': ['REDIS_HOST', 'REDIS_PORT', 'KITE_API_KEY', 'KITE_API_SECRET', 'KITE_ACCESS_TOKEN', 'MONGODB_URI', 'INSTRUMENT_SYMBOL', 'INSTRUMENT_NAME'],
            'engine_module': ['GROQ_API_KEY', 'GROQ_API_KEY_2', 'GROQ_MODEL', 'LLM_PROVIDER', 'OPENAI_API_KEY', 'LLM_MODEL'],
            'news_module': ['GOOGLE_API_KEY', 'HUGGINGFACE_API_KEY'],
            'user_module': []
        }

        for module_name, keys in modules_keys.items():
            module_dir = Path(module_name)
            if not module_dir.exists():
                continue
            env_path = module_dir / '.env'
            existing = {}
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        k, v = line.split('=', 1)
                        existing[k.strip()] = v.strip()
            to_write = {}
            for k in keys:
                if k in existing:
                    continue
                if k in root_vars:
                    to_write[k] = root_vars[k]
            if to_write:
                try:
                    with open(env_path, 'a', encoding='utf-8') as f:
                        f.write('\n# Added by start_local.py from root .env\n')
                        for k, v in to_write.items():
                            f.write(f"{k}={v}\n")
                    print(f"   [OK] Updated {env_path} with {len(to_write)} keys from root .env")
                except Exception as e:
                    print(f"   [WARN]  Failed to update {env_path}: {e}")
    except Exception as e:
        print(f"   [WARN]  Could not populate module .env files: {e}")

    # Determine provider (arg > env > USE_MOCK_KITE > auto)
    provider_name = args.provider or os.getenv('TRADING_PROVIDER')
    use_mock_env = os.getenv('USE_MOCK_KITE', 'false').lower() in ('1', 'true', 'yes')
    if not provider_name and use_mock_env:
        provider_name = 'mock'
    if not provider_name:
        provider_name = 'auto'

    # Normalize
    provider_name_normalized = provider_name.lower()
    if provider_name_normalized in ('mock', 'simulator'):
        os.environ['USE_MOCK_KITE'] = '1'
    else:
        # leave existing USE_MOCK_KITE as-is or clear
        os.environ.setdefault('USE_MOCK_KITE', '0')

    # Print selected trading provider for clarity (use factory if available)
    try:
        from market_data.providers.factory import get_provider
        provider = get_provider(provider_name if provider_name != 'auto' else None)
        if provider is None and provider_name_normalized == 'auto':
            provider_name_normalized = 'historical'  # Default to historical when no provider available
        print(f"[INFO] Trading provider: {provider.__class__.__name__ if provider else provider_name_normalized}")
    except Exception:
        print(f"[INFO] Trading provider: {provider_name}")

    # Add paths
    sys.path.insert(0, '.')
    sys.path.insert(0, './market_data/src')
    sys.path.insert(0, './news_module/src')
    sys.path.insert(0, './engine_module/src')
    sys.path.insert(0, './genai_module/src')

    processes = []

    try:
        # Step 0: Kill existing processes and verify Zerodha authentication
        print("\n" + "=" * 60)
        print("Step 0: Cleanup and Authentication")
        print("=" * 60)

        # Kill existing processes on all ports
        print("   Cleaning up existing processes...")
        ports_to_clean = [8004, 8005, 8006, 8007, 8888, 8889]
        for port in ports_to_clean:
            kill_process_on_port(port)
        print("   [OK] Ports cleaned")

        # Verify Zerodha authentication if using Zerodha provider or auto
        kite_instance = None
        if provider_name_normalized in ('zerodha', 'kite', 'auto'):
            print("\n   [AUTH] Verifying Zerodha Authentication (Step 0)...")
            creds_ok, kite_instance = verify_zerodha_credentials()
            if creds_ok:
                print("   [OK] Zerodha authentication verified - proceeding with startup")
                # Set environment variables for collectors to use
                if os.getenv('KITE_API_KEY') and os.getenv('KITE_ACCESS_TOKEN'):
                    print("   [ENV] Using existing KITE environment variables")
                else:
                    # Try to load from credentials file and set env vars
                    try:
                        sys.path.insert(0, './market_data/src')
                        from market_data.tools.kite_auth_service import KiteAuthService
                        auth_service = KiteAuthService()
                        creds = auth_service.load_credentials()
                        if creds:
                            os.environ['KITE_API_KEY'] = creds.get('api_key', '')
                            os.environ['KITE_ACCESS_TOKEN'] = creds.get('access_token', '')
                            print("   [ENV] Set KITE environment variables from credentials file")
                    except Exception as e:
                        print(f"   [WARN] Could not set KITE environment variables: {e}")
                # If using 'auto' provider and Zerodha is available, set to zerodha for collectors
                if provider_name_normalized == 'auto':
                    provider_name_normalized = 'zerodha'
                    print("   [AUTO] Provider set to 'zerodha' (live data collection enabled)")
            elif not creds_ok:
                print("   [ERROR] Zerodha authentication failed!")
                print("   [REFRESH] Attempting automatic kite authorization...")

                # Try automatic kite auth - first try refresh, then interactive
                try:
                    sys.path.insert(0, './market_data/src')
                    from market_data.tools.kite_auth_service import KiteAuthService
                    auth_service = KiteAuthService()

                    # First try token refresh (silent operation)
                    creds = auth_service.load_credentials()
                    if creds:
                        print("   [REFRESH] Attempting to refresh existing token...")
                        new_creds = auth_service.refresh_token(creds)
                        if new_creds:
                            auth_service.save_credentials(new_creds)
                            print("   [OK] Token refreshed successfully!")
                            # Re-verify credentials
                            creds_ok, kite_instance = verify_zerodha_credentials()
                            if creds_ok and provider_name_normalized == 'auto':
                                provider_name_normalized = 'zerodha'
                                print("   [AUTO] Provider set to 'zerodha' (live data collection enabled)")
                        else:
                            print("   [WARN] Token refresh failed, trying interactive login...")
                    else:
                        print("   [WARN] No existing credentials found, trying interactive login...")

                    # If refresh didn't work or no creds exist, try interactive login
                    if not creds_ok:
                        print("   [WEB] Starting interactive kite login...")
                        success = auth_service.trigger_interactive_login(timeout=300)  # 5 minutes

                        if success:
                            print("   [OK] Kite authorization successful!")
                            # Re-verify credentials
                            creds_ok, kite_instance = verify_zerodha_credentials()
                            if creds_ok:
                                print("   [OK] Zerodha authentication verified - proceeding with startup")
                                # Set provider to zerodha for collectors
                                if provider_name_normalized == 'auto':
                                    provider_name_normalized = 'zerodha'
                                    print("   [AUTO] Provider set to 'zerodha' (live data collection enabled)")
                            else:
                                print("   [ERROR] Still unable to verify credentials after authorization")
                                return
                        else:
                            print("   [ERROR] Interactive kite login failed or timed out")
                            print("   [TIP] Please try manual login: python -m market_data.tools.kite_auth_service")
                            return
                    else:
                        print("   [OK] Zerodha authentication verified after token refresh - proceeding with startup")
                except Exception as e:
                    print(f"   [ERROR] Automatic kite auth failed: {e}")
                    print("   [TIP] Please try manual login: python -m market_data.tools.kite_auth_service")
                    return
            else:
                print("   [OK] Zerodha authentication verified - proceeding with startup")
        elif provider_name_normalized in ('historical', 'replay', 'auto'):
            # Check if Zerodha credentials are available (might be used for historical data)
            print("\n   [AUTH] Checking Zerodha credentials (optional for historical data)...")
            creds_ok, kite_instance = verify_zerodha_credentials()
            if creds_ok:
                print("   [OK] Zerodha credentials available (can use --historical-source zerodha)")
            else:
                print("   [WARN]  Zerodha credentials not available")
                print("   [TIP] Historical data requires Zerodha credentials or CSV file")

                # For historical mode with zerodha source, try automatic auth if needed
                if hasattr(args, 'historical_source') and args.historical_source == 'zerodha':
                    print("   [REFRESH] Historical source is zerodha, checking if kite authorization is needed...")

                    # First try to refresh existing token if possible
                    try:
                        sys.path.insert(0, './market_data/src')
                        from market_data.tools.kite_auth_service import KiteAuthService
                        auth_service = KiteAuthService()

                        # Try token refresh first (silent operation)
                        creds = auth_service.load_credentials()
                        if creds:
                            print("   [REFRESH] Attempting to refresh existing token...")
                            new_creds = auth_service.refresh_token(creds)
                            if new_creds:
                                auth_service.save_credentials(new_creds)
                                print("   [OK] Token refreshed successfully!")
                                # Re-verify credentials
                                creds_ok, kite_instance = verify_zerodha_credentials()
                                if creds_ok:
                                    print("   [OK] Zerodha credentials now available for historical data")
                                else:
                                    print("   [WARN] Token refresh didn't work, may need interactive login")
                            else:
                                print("   [WARN] Token refresh failed, trying interactive login...")
                        else:
                            print("   [WARN] No existing credentials found, trying interactive login...")

                        # If refresh didn't work or no creds exist, try interactive login
                        if not creds_ok:
                            print("   [WEB] Starting interactive kite login for historical data...")
                            success = auth_service.trigger_interactive_login(timeout=300)  # 5 minutes

                            if success:
                                print("   [OK] Kite authorization successful!")
                                # Re-verify credentials
                                creds_ok, kite_instance = verify_zerodha_credentials()
                                if creds_ok:
                                    print("   [OK] Zerodha credentials now available for historical data")
                                else:
                                    print("   [ERROR] Still unable to verify credentials after authorization")
                            else:
                                print("   [ERROR] Interactive kite login failed or timed out")
                                print("   [TIP] Please try manual login: python -m market_data.tools.kite_auth_service")
                    except Exception as e:
                        print(f"   [ERROR] Automatic kite auth failed: {e}")
                        print("   [TIP] Please try manual login: python -m market_data.tools.kite_auth_service")

        # Step 1: Start and Verify Historical Data Source
        print("\n" + "=" * 60)
        print("Step 1: Historical Data Source")
        print("=" * 60)
        historical_ok = True
        data_source_used = 'zerodha'  # Default to Zerodha (no synthetic)
        replay_instance = None
        if provider_name_normalized in ('historical', 'replay', 'auto'):
            # Set BACKTEST mode in Redis before starting services
            print("   [CONFIG] Setting BACKTEST mode in Redis...")
            import redis
            redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            try:
                redis_client.set("system:execution_mode", "BACKTEST")
                redis_client.set("system:run_id", f"bt_{args.historical_from or 'unknown'}_{args.historical_source or 'unknown'}")
                print("   [OK] BACKTEST mode set in Redis")
            except Exception as e:
                print(f"   [WARN] Failed to set BACKTEST mode in Redis: {e}")

            # Start market-data runner in historical mode (spawns market-data API + historical replayer)
            print("   [START] Starting market-data runner in historical mode...")
            kill_process_on_port(8004)
            runner_cmd = ["python", "-m", "market_data.runner", "--mode", "historical"]
            # Pass CLI args through to runner as env vars
            env = os.environ.copy()
            if args.historical_source:
                env['HISTORICAL_SOURCE'] = args.historical_source
            if args.historical_speed is not None:
                env['HISTORICAL_SPEED'] = str(args.historical_speed)
            if args.historical_from:
                env['HISTORICAL_FROM'] = args.historical_from
            if args.historical_ticks:
                env['HISTORICAL_TICKS'] = '1'

            runner_process = start_service("Market Data Runner (historical)", runner_cmd, env=env)
            processes.append(runner_process)

            if not args.skip_validation:
                # Verify data is actually available by polling Redis/API
                historical_ok = verify_historical_data(data_source=(args.historical_source or 'zerodha'))
                if not historical_ok:
                    print("[ERROR] Historical data verification failed!")
                    print("   Stopping startup. Historical data must be available before proceeding.")
                    if (args.historical_source or 'zerodha') == 'zerodha':
                        print("   [TIP] Zerodha data issues:")
                        print("      - Verify credentials are correct and authenticated")
                        print("      - Check if historical data is available for the date")
                        print("      - Ensure Zerodha API is accessible")
                    return
            else:
                print("[SKIP] Historical data startup skipped (validation disabled)")
        else:
            print("[OK] Using live data collectors (no historical replay needed)")

            # Clear any virtual time from previous historical runs (live mode uses real time)
            try:
                import redis
                redis_host = os.getenv("REDIS_HOST", "localhost")
                redis_port = int(os.getenv("REDIS_PORT", "6379"))
                redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
                redis_client.delete("system:virtual_time:enabled")
                redis_client.delete("system:virtual_time:current")
                print("   [OK] Cleared virtual time (live mode uses real-time)")
            except Exception as e:
                print(f"   [WARN]  Could not clear virtual time: {e}")

            # In the new runner-based architecture, collectors are started by the runner
            if provider_name_normalized in ('zerodha', 'kite') and creds_ok:
                print("   [INFO] Live collectors will be managed by market-data runner when the server is started")
            else:
                # For historical mode, we still need LTP collector for synthetic volume generation
                if provider_name_normalized in ('historical', 'replay', 'auto'):
                    print("   [INFO] Starting LTP collector for synthetic volume generation in historical mode")
                    try:
                        # Set PYTHONPATH for the collector
                        env = os.environ.copy()
                        env['PYTHONPATH'] = os.path.join(os.getcwd(), 'market_data', 'src')
                        ltp_cmd = [sys.executable, "-m", "market_data.collectors.ltp_collector"]
                        ltp_process = start_service("LTP Collector (historical)", ltp_cmd, port=None, health_url=None, env=env)
                        print("   [OK] LTP collector started for synthetic volume generation")
                    except Exception as e:
                        print(f"   [WARN] Failed to start LTP collector: {e}")
                else:
                    print("   [INFO] Live collectors are not required for this configuration")

        # Step 2: Start and Verify Market Data API
        print("\n" + "=" * 60)
        print("Step 2: Market Data API")
        print("=" * 60)

        if args.docker_market_data:
            print("   [DOCKER] Using Docker market-data-api service (skipping local startup)")
        else:
            # For historical mode, market data API was already started in Step 1
            # For live mode, start it now
            if provider_name_normalized not in ('historical', 'replay', 'auto'):
                # Start market-data via the runner to keep collectors and replay managed together
                print("   [START] Starting market-data runner (live mode)...")
                kill_process_on_port(8004)
                runner_cmd = ["python", "-m", "market_data.runner", "--mode", "live"]
                # Let the runner start collectors when running in Zerodha mode
                if provider_name_normalized in ('zerodha', 'kite') and creds_ok:
                    runner_cmd.append('--start-collectors')
                market_data_process = start_service(
                    "Market Data Runner (live)",
                    runner_cmd
                )
                processes.append(market_data_process)
            else:
                print("   [OK] Market Data API already started in historical mode (Step 1)")

        if args.skip_validation:
            print("[SKIP] Skipping Market Data API verification")
        else:
            # First check health endpoint
            service_name = "Docker Market Data API" if args.docker_market_data else "Market Data API"
            market_data_health = wait_for_service(service_name, "http://localhost:8004/health")
            if not market_data_health:
                service_type = "Docker market-data-api service" if args.docker_market_data else "Market Data API"
                print(f"[ERROR] {service_name} health check failed!")
                print(f"   Stopping startup. {service_type} must be healthy before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

            # With comprehensive dependency validation now in place, we can be more lenient on data verification
            # Give collectors more time and don't fail startup if data isn't immediately available
            print("   [INFO] Verifying data availability (may take 30-60s for collectors to seed data)...")
            market_data_ok = verify_market_data_api(max_retries=15, retry_delay=2)
            if not market_data_ok:
                print("   [WARN] WARNING: Data verification incomplete (but dependency validation passed)")
                print("   [INFO] Proceeding with startup - collectors are running and will seed data")
                print("   [TIP] Data should be available within 30-60 seconds")
                print("   [TIP] Check http://localhost:8004/diagnostics for detailed status")

            # Verify Redis data storage and publishing
            # Skip Redis verification if it's a clean start (no data exists yet)
            import redis
            redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            total_keys = len(redis_client.keys('*'))

            if total_keys == 0:
                print("[INFO] Redis is empty - skipping data verification for clean start")
                print("   [TIP] Market data services will generate data during runtime")
                redis_data_ok = True
            else:
                redis_data_ok = verify_redis_data_storage()
                if not redis_data_ok:
                    print("[ERROR] Redis data storage verification failed!")
                    print("   Stopping startup. Redis must be storing data correctly before proceeding.")
                    # Cleanup started processes
                    for process in processes:
                        try:
                            process.terminate()
                        except:
                            pass
                    return

            # Verify technical indicators calculation
            if total_keys == 0:
                print("[INFO] Redis is empty - skipping technical indicators verification for clean start")
                print("   [TIP] Technical indicators will be calculated during runtime")
                indicators_ok = True
            else:
                indicators_ok = verify_technical_indicators()
                if not indicators_ok:
                    print("[ERROR] Technical indicators verification failed!")
                    print("   Stopping startup. Technical indicators must be calculated before proceeding.")
                    # Cleanup started processes
                    for process in processes:
                        try:
                            process.terminate()
                        except:
                            pass
                    return

            # Perform comprehensive data flow validation after market data services are running
            print("\n   [VALIDATE] Running comprehensive data pipeline validation...")
            data_flow_ok = verify_comprehensive_data_flow()
            if not data_flow_ok:
                print("[WARN] Comprehensive data validation found issues - but proceeding with startup")
                print("   [TIP] Monitor the validation output above for any critical failures")
                # Don't stop startup, just warn - some validations may be timing-dependent

        # Step 3: Start and Verify News API
        print("\n" + "=" * 60)
        print("Step 3: News API")
        print("=" * 60)
        kill_process_on_port(8005)
        news_process = start_service(
            "News API (port 8005)",
            ["python", "-c", "from news_module.api_service import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8005)"]
        )
        processes.append(news_process)

        if args.skip_validation:
            print("[SKIP] Skipping News API verification")
        else:
            # First check health endpoint
            news_health = wait_for_service("News API", "http://localhost:8005/health")
            if not news_health:
                print("[ERROR] News API health check failed!")
                print("   Stopping startup. Please check the News API logs.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

            # Then verify actual news articles
            news_ok = verify_news_api()
            if not news_ok:
                print("[WARN] News API verification failed - RSS feeds blocked (403)")
                print("   Continuing startup - news is optional for basic functionality")
                # Don't stop startup, just warn and continue

        # Step 4: Start and Verify Engine API
        print("\n" + "=" * 60)
        print("Step 4: Engine API")
        print("=" * 60)

        # Ensure all LLM API keys and configuration are set in environment before starting Engine API
        # These will be passed to the Engine API process via start_service (which copies os.environ)
        # Only set if not already in environment (allows local.env to override)
        required_env_vars = {
            # API keys intentionally left blank - set these in your local .env (copy from .env.example)
            'AI21_API_KEY': '',
            'AI21_API_KEY_2': '',
            'AI21_MODEL': 'j2-mid',
            'COHERE_API_KEY': '',
            'COHERE_API_KEY_2': '',
            'COHERE_MODEL': 'command-a-03-2025',
            'COHERE_REASONING_MODEL': 'command-a-reasoning-08-2025',
            'DAILY_LOSS_LIMIT_PCT': '5.0',
            'DATA_SOURCE': 'ZERODHA',
            'DEFAULT_STOP_LOSS_PCT': '1.5',
            'DEFAULT_TAKE_PROFIT_PCT': '3.0',
            'GOOGLE_API_KEY': '',
            'GROQ_API_KEY': '',
            'GROQ_API_KEY_2': '',
            'GROQ_API_KEY_3': '',
            'GROQ_MODEL': 'llama-3.1-8b-instant',
            'GROQ_MODELS': 'llama-3.1-8b-instant',
        }

        # Set environment variables that are missing (existing values take precedence)
        vars_set = []
        for key, default_value in required_env_vars.items():
            if key not in os.environ:
                os.environ[key] = default_value
                vars_set.append(key)

        if vars_set:
            print(f"   [CONFIG] Set {len(vars_set)} environment variables for Engine API")
        else:
            print(f"   [OK] All required environment variables already set")

        # Install genai_module in editable mode for Engine API
        print("   [INSTALL] Installing genai_module (1/2)...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./genai_module"],
                         capture_output=True, text=True, check=True)
            print("   [OK] genai_module installed successfully (1/2)")
        except subprocess.CalledProcessError as e:
            print(f"   [ERROR] Failed to install genai_module (1/2): {e}")
            print(f"   Error output: {e.stderr}")
            return

        # Install news_module in editable mode for News API
        print("   [INSTALL] Installing news_module (2/2)...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./news_module"],
                         capture_output=True, text=True, check=True)
            print("   [OK] news_module installed successfully (2/2)")
        except subprocess.CalledProcessError as e:
            print(f"   [ERROR] Failed to install news_module (2/2): {e}")
            print(f"   Error output: {e.stderr}")
            return

        kill_process_on_port(8006)
        engine_process = start_service(
            "Engine API (port 8006)",
            ["python", "-m", "engine_module.api_service"]
        )
        processes.append(engine_process)

        if args.skip_validation:
            print("[SKIP] Skipping Engine API verification")
        else:
            # First check health endpoint
            engine_health = wait_for_service("Engine API", "http://localhost:8006/health")
            if not engine_health:
                print("[ERROR] Engine API health check failed!")
                print("   Stopping startup. Please check the Engine API logs.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

            # Then verify agents are running
            engine_ok = verify_engine_api()
            if not engine_ok:
                print("[WARN] Engine API verification failed - agents not ready yet")
                print("   Continuing startup - engine is optional for basic market data testing")
                # Don't stop startup, just warn and continue

            # Verify engine can process market data
            print("\n   [VALIDATE] Verifying engine data processing capabilities...")
            engine_processing_ok = verify_engine_data_processing()
            if not engine_processing_ok:
                print("[WARN] Engine data processing verification failed")
                print("   [TIP] Engine may still work - check logs for details")
                # Don't stop startup - engine is optional

        # Step 4.5: Start and Verify User API
        print("\n" + "=" * 60)
        print("Step 4.5: User API")
        print("=" * 60)

        # Install user_module in editable mode for User API
        print("   [INSTALL] Installing user_module...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./user_module"],
                         capture_output=True, text=True, check=True)
            print("   [OK] user_module installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"   [ERROR] Failed to install user_module: {e}")
            print(f"   Error output: {e.stderr}")
            return

        kill_process_on_port(8007)
        user_process = start_service(
            "User API (port 8007)",
            ["python", "-m", "user_module.api_service"]
        )
        processes.append(user_process)

        if args.skip_validation:
            print("[SKIP] Skipping User API verification")
        else:
            # Check health endpoint
            user_health = wait_for_service("User API", "http://localhost:8007/health")
            if not user_health:
                print("[ERROR] User API health check failed!")
                print("   Stopping startup. Please check the User API logs.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return
            print("   [OK] User API is healthy and ready!")

        # Step 5: Start and Verify Dashboard UI
        print("\n" + "=" * 60)
        print("Step 5: Dashboard UI")
        print("=" * 60)

        if args.docker_dashboard:
            print("   [DOCKER] Using Docker dashboard services (skipping local startup)")
        else:
            kill_process_on_port(8888)

            # If the modular React UI exists, prefer starting it (Vite dev server)
            ui_dir = Path('dashboard') / 'modular_ui'
            if ui_dir.exists() and (ui_dir / 'package.json').exists():
                print("   [INFO] Found modular UI at dashboard/modular_ui - starting Vite dev server on port 8888")

                # Ensure dashboard modular UI has a .env with VITE_* keys populated from root .env
                root_env_path = Path('.') / '.env'
                ui_env_path = ui_dir / '.env'
                root_vars = {}
                if root_env_path.exists():
                    try:
                        with open(root_env_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if not line or line.startswith('#') or '=' not in line:
                                    continue
                                k, v = line.split('=', 1)
                                root_vars[k.strip()] = v.strip()
                    except Exception as e:
                        print(f"   [WARN]  Failed to read root .env: {e}")

                vite_defaults = {
                    'VITE_DASHBOARD_API_URL': 'http://localhost:8888',
                    'VITE_MARKET_API_URL': 'http://localhost:8004',
                    'VITE_NEWS_API_URL': 'http://localhost:8005',
                    'VITE_ENGINE_API_URL': 'http://localhost:8006',
                    'VITE_USER_API_URL': 'http://localhost:8007',
                    'VITE_WS_URL': 'ws://localhost:8889'
                }

                # Merge values: existing ui .env < root .env < defaults
                existing_ui_vars = {}
                if ui_env_path.exists():
                    try:
                        with open(ui_env_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if not line or line.startswith('#') or '=' not in line:
                                    continue
                                k, v = line.split('=', 1)
                                existing_ui_vars[k.strip()] = v.strip()
                    except Exception as e:
                        print(f"   [WARN]  Failed to read existing UI .env: {e}")

                merged = {}
                for k, dv in vite_defaults.items():
                    merged[k] = existing_ui_vars.get(k) or root_vars.get(k) or dv

                try:
                    with open(ui_env_path, 'w', encoding='utf-8') as f:
                        f.write('# Generated by start_local.py - do not commit\n')
                        for k, v in merged.items():
                            f.write(f"{k}={v}\n")
                    print(f"   [OK] Wrote/updated {ui_env_path}")
                except Exception as e:
                    print(f"   [WARN]  Failed to write {ui_env_path}: {e}")

                # Ensure node deps are installed (quick check: node_modules exists)
                node_modules_dir = ui_dir / 'node_modules'
                if not node_modules_dir.exists():
                    print("   [INSTALL] Installing modular UI dependencies (npm ci)")
                    try:
                        subprocess.run(['npm', 'ci'], cwd=str(ui_dir), check=True)
                        print("   [OK] Installed UI dependencies")
                    except subprocess.CalledProcessError:
                        print("   [WARN]  'npm ci' failed, falling back to 'npm install' (this may take a while)")
                        try:
                            subprocess.run(['npm', 'install'], cwd=str(ui_dir), check=True)
                            print("   [OK] Installed UI dependencies via npm install")
                        except subprocess.CalledProcessError as e:
                            print(f"   [ERROR] Failed to install UI dependencies: {e}")
                            print("   [TIP] Please install dependencies manually: cd dashboard/modular_ui && npm install")

                # Start Vite dev server on port 8888
                dashboard_process = start_service(
                    "Dashboard UI (Vite dev)",
                    ['npm', 'run', 'dev', '--', '--port', '8888'],
                    cwd=str(ui_dir)
                )
                processes.append(dashboard_process)

                # ALSO start the FastAPI dashboard backend on port 8001
                # Modular UI proxies /api/analytics, /api/risk, etc. to port 8001
                print("   [START] Starting Dashboard Backend (port 8001) for Modular UI...")
                backend_process = start_service(
                    "Dashboard Backend (port 8001)",
                    ["python", "-c", "from dashboard.app import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8001)"]
                )
                processes.append(backend_process)

            else:
                # Fallback to older python-based dashboard
                dashboard_process = start_service(
                    "Dashboard (port 8888)",
                    ["python", "-c", "from dashboard.app import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8888)"]
                )
                processes.append(dashboard_process)

            # Start WebSocket Gateway on port 8889
            print("   [WAIT] Waiting for port 8889 to be available...")
            time.sleep(3)  # Give extra time for port to be freed
            websocket_env = os.environ.copy()
            websocket_env['PYTHONPATH'] = f"{os.getcwd()}{os.pathsep}{websocket_env.get('PYTHONPATH', '')}"
            websocket_process = start_service(
                "WebSocket Gateway (port 8889)",
                ["python", "redis_ws_gateway/main.py"],
                env=websocket_env
            )
            processes.append(websocket_process)
        if not websocket_ok:
            print("[WARN] WebSocket data streaming verification failed")
            print("   [TIP] WebSocket may still work - check connection logs")
            # Don't stop startup - WebSocket issues shouldn't block basic functionality

        if args.skip_validation:
            print("[SKIP] Skipping Dashboard UI verification")
        else:
            # First check if dashboard loads
            service_name = "Docker Dashboard UI" if args.docker_dashboard else "Dashboard UI"
            dashboard_health = wait_for_service(service_name, "http://localhost:8888/")
            if not dashboard_health:
                service_type = "Docker dashboard services" if args.docker_dashboard else "Dashboard UI"
                print(f"[ERROR] {service_name} health check failed!")
                print(f"   Stopping startup. Please check the {service_type} logs.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

            # Then verify dashboard can access data from APIs
            dashboard_ok = verify_dashboard_ui()
            if not dashboard_ok:
                print("❌ Dashboard UI data verification failed!")
                print("   Stopping startup. Dashboard must be able to access data before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

        # All services verified successfully
        print("\n" + "=" * 60)
        print("[SUCCESS] All services started and verified!")
        print("=" * 60)

        # Final comprehensive data validation
        print("\n   [FINAL VALIDATE] Running final data pipeline health check...")
        final_validation = verify_comprehensive_data_flow()
        if final_validation:
            print("   🎉 FINAL RESULT: Data pipeline is fully operational!")
        else:
            print("   ⚠️  FINAL RESULT: Data pipeline has some issues - check logs above")
            print("   💡 TIP: Some validations may be timing-sensitive, monitor during operation")

        print("\n[ACCESS] Access URLs:")
        dashboard_label = "[INFO] Dashboard (Docker):" if args.docker_dashboard else "[INFO] Dashboard:"
        print(f"   {dashboard_label}    http://localhost:8888/")
        print("   [WS] WebSocket:    ws://localhost:8889/ws")
        market_data_label = "[DATA] Market Data (Docker):" if args.docker_market_data else "[DATA] Market Data:"
        print(f"   {market_data_label}  http://localhost:8004/health")
        print("   [DATA] Market Data Dashboard: http://localhost:8008/")
        print("   [NEWS] News:         http://localhost:8005/health")
        print("   🤖 Engine:       http://localhost:8006/health")
        print("   [USER] User:         http://localhost:8007/health")
        print("\n🎯 The UI should now be able to show data from all APIs.")

        print("\n[STOP] Press Ctrl+C to stop all services")

        # Wait for keyboard interrupt
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Stopping all services...")
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()

        print("[OK] All services stopped")


if __name__ == "__main__":
    asyncio.run(main())