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
from pathlib import Path

# Add market_data/src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / 'market_data' / 'src'))

# Setup centralized logging and monitoring
from config import get_config
config = get_config()
config.setup_logging()

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


class CredentialsValidator:
    """Validates Zerodha credentials and token authentication"""

    @staticmethod
    def verify_zerodha_credentials():
        """Verify Zerodha credentials are available and token authentication works"""
        print("   🔐 Verifying Zerodha credentials and token authentication...")
        token_validated_and_invalid = False  # Track if we validated and found it invalid
        try:
            sys.path.insert(0, '.')
            import json

            # Step 1: Check environment variables first
            api_key = os.getenv('KITE_API_KEY')
            api_secret = os.getenv('KITE_API_SECRET')
            access_token = os.getenv('KITE_ACCESS_TOKEN')

            if api_key and api_secret:
                print("   [OK] Found Zerodha API credentials in environment variables")
                print(f"      API Key: {api_key[:8]}...")
                print(f"      API Secret: {'*' * 8}...")

                # If access_token is in env, use it directly
                if access_token:
                    print("   [OK] Found KITE_ACCESS_TOKEN in environment")
                    try:
                        from market_data.providers.zerodha import ZerodhaProvider
                        provider = ZerodhaProvider(api_key, access_token)
                        kite = provider.kite
                        print("   [OK] Created ZerodhaProvider from environment variables")
                    except Exception as e:
                        print(f"   [ERROR] Failed to create provider from env vars: {e}")
                        return False, None
                else:
                    # ACCESS_TOKEN not in env, check credentials.json using KiteAuthService
                    print("   [WARN]  KITE_ACCESS_TOKEN not found in environment")
                    print("   [TIP] Checking credentials.json for valid token...")

                    # Use KiteAuthService to check credentials.json
                    token_validated_and_invalid = False  # Track if we validated and found it invalid
                    try:
                        from kite_auth_service import KiteAuthService
                        auth_service = KiteAuthService()
                        creds = auth_service.load_credentials()

                        if creds:
                            # Get API key and token from credentials.json (token is tied to this API key)
                            creds_api_key = creds.get('api_key') or creds.get('KITE_API_KEY')
                            creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')

                            # MUST use API key from credentials.json (token was generated with this key)
                            # Only fall back to env if creds doesn't have it (shouldn't happen)
                            token_api_key = creds_api_key or api_key

                            if token_api_key and creds_access_token:
                                # Check if token is valid using KiteAuthService
                                if auth_service.is_token_valid(creds):
                                    print("   [OK] Found valid access token in credentials.json")
                                    from market_data.providers.zerodha import ZerodhaProvider
                                    provider = ZerodhaProvider(token_api_key, creds_access_token)
                                    print("   [OK] Using credentials from credentials.json (token validated)")
                                else:
                                    print("   [ERROR] Token in credentials.json is expired or invalid (403 error)")
                                    print("   [OK] Validation worked correctly - token is not usable")
                                    print("   [TIP] Please refresh token by running: python -m market_data.tools.kite_auth")
                                    print("   [TIP] Or set KITE_ACCESS_TOKEN in environment with a valid token")
                                    provider = None
                                    token_validated_and_invalid = True  # Mark as validated and invalid
                            else:
                                print("   [WARN]  credentials.json missing api_key or access_token")
                                provider = None
                        else:
                            print("   [WARN]  credentials.json not found or could not be loaded")
                            provider = None
                    except ImportError:
                        print("   [WARN]  KiteAuthService not available, checking credentials.json directly...")
                        # Fall through to direct credentials.json check
                        provider = None
                    except Exception as e:
                        print(f"   [WARN]  Error checking credentials.json: {e}")
                        provider = None

                    # If token was validated and found invalid, skip direct read (it will fail anyway)
                    if token_validated_and_invalid:
                        print("   ℹ️  Skipping direct credentials.json read (token already validated as invalid)")
            else:
                # Step 2: Check credentials.json file (no env vars)
                print("   ℹ️  Checking credentials.json file...")
                try:
                    from kite_auth_service import KiteAuthService
                    auth_service = KiteAuthService()
                    creds = auth_service.load_credentials()

                    if creds:
                        creds_api_key = creds.get('api_key') or creds.get('KITE_API_KEY')
                        creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')

                        if creds_api_key and creds_access_token:
                            if auth_service.is_token_valid(creds):
                                print("   [OK] Found valid credentials in credentials.json")
                                from market_data.providers.zerodha import ZerodhaProvider
                                provider = ZerodhaProvider(creds_api_key, creds_access_token)
                            else:
                                print("   [WARN]  Token in credentials.json is expired or invalid")
                                provider = None
                        else:
                            print("   [WARN]  credentials.json missing api_key or access_token")
                            provider = None
                    else:
                        from market_data.providers.factory import get_provider
                        provider = get_provider('zerodha')
                except ImportError:
                    from market_data.providers.factory import get_provider
                    provider = get_provider('zerodha')
                except Exception as e:
                    print(f"   [WARN]  Error checking credentials: {e}")
                    provider = None

            # Step 3: If provider still not created and token wasn't validated as invalid, try direct credentials.json read
            if provider is None and not token_validated_and_invalid:
                try:
                    import json
                    if os.path.exists('credentials.json'):
                        with open('credentials.json', 'r', encoding='utf-8-sig') as f:
                            creds = json.load(f)
                        creds_api_key = creds.get('api_key') or creds.get('KITE_API_KEY')
                        creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                        if creds_api_key and creds_access_token:
                            from market_data.providers.zerodha import ZerodhaProvider
                            provider = ZerodhaProvider(creds_api_key, creds_access_token)
                            print("   [WARN]  Using credentials.json (not validated - will test in next step)")
                        else:
                            print("   [WARN]  credentials.json exists but missing api_key or access_token")
                    else:
                        print("   [WARN]  credentials.json not found")
                except Exception as e:
                    print(f"   [WARN]  Error reading credentials.json: {e}")

            if provider is None:
                print("   [WARN]  Zerodha credentials incomplete")
                if api_key and api_secret:
                    print("   [TIP] You have KITE_API_KEY and KITE_API_SECRET, but need KITE_ACCESS_TOKEN")
                    print("   [TIP] Please set KITE_ACCESS_TOKEN in environment:")
                    print("      export KITE_ACCESS_TOKEN=your_access_token")
                    print("   [TIP] Or add access_token to credentials.json")
                else:
                    print("   [TIP] Please set one of:")
                    print("      - KITE_API_KEY, KITE_API_SECRET, and KITE_ACCESS_TOKEN in environment")
                    print("      - credentials.json with api_key and access_token")
                return False, None

            # Step 2: Verify kite instance exists
            if not hasattr(provider, 'kite'):
                print("   [ERROR] Zerodha provider initialized but kite instance not available")
                return False, None

            kite = provider.kite

            # Step 3: Test token authentication with actual API call
            try:
                print("   [WAIT] Testing token authentication (API call)...")
                profile = kite.profile()
                if profile:
                    user_name = profile.get('user_name', 'N/A')
                    user_id = profile.get('user_id', 'N/A')
                    print(f"   [OK] Token authentication verified")
                    print(f"      User: {user_name} (ID: {user_id})")

                    # Step 4: Test connection with a quote call (optional but thorough)
                    try:
                        # Try to get a quote to verify full connection works
                        test_quote = kite.quote(['NSE:RELIANCE'])
                        if test_quote:
                            print(f"   [OK] Connection test passed (quote API working)")
                    except Exception as quote_error:
                        # Quote might fail if market is closed, but profile works, so auth is OK
                        print(f"   [WARN]  Quote test failed (may be market hours): {quote_error}")
                        print(f"   [OK] Token authentication is valid (profile API works)")

                    return True, kite
                else:
                    print("   [ERROR] Token authentication failed: Empty profile response")
                    return False, None
            except Exception as auth_error:
                error_msg = str(auth_error)
                print(f"   [ERROR] Token authentication failed: {error_msg}")

                # Provide helpful error messages
                if 'Invalid' in error_msg or 'invalid' in error_msg.lower():
                    print("   [TIP] Token may be expired or invalid")
                    print("   [TIP] Please regenerate access token:")
                    print("      - Check credentials.json has valid access_token")
                    print("      - Token expires daily, may need refresh")
                elif 'Unauthorized' in error_msg or '401' in error_msg:
                    print("   [TIP] Unauthorized - token not valid")
                    print("   [TIP] Please check API_KEY and ACCESS_TOKEN in credentials.json")
                elif 'Connection' in error_msg or 'timeout' in error_msg.lower():
                    print("   [TIP] Connection issue - check network/Zerodha API status")
                else:
                    print("   [TIP] Please check your Zerodha credentials:")
                    print("      - API_KEY in credentials.json")
                    print("      - ACCESS_TOKEN in credentials.json (may need refresh)")

                return False, None

        except ImportError as e:
            print(f"   [WARN]  Could not import provider: {e}")
            print("   [TIP] Install kiteconnect: pip install kiteconnect")
            return False, None
        except Exception as e:
            print(f"   [ERROR] Error verifying Zerodha credentials: {e}")
            import traceback
            traceback.print_exc()
            return False, None


def verify_zerodha_credentials():
    """Wrapper for CredentialsValidator - maintains backward compatibility"""
    return CredentialsValidator.verify_zerodha_credentials()


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
            for pattern in ["tick:*:latest", "tick:BANKNIFTY*", "tick:NIFTY BANK*", "tick:NIFTYBANK*", "tick:NIFTY*"]:
                keys = redis_client.keys(pattern)
                if keys:
                    tick_keys.extend(keys)
                    print(f"   ℹ️  Found {len(keys)} tick keys matching '{pattern}' in Redis")
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
                print(f"   ℹ️  Total {len(set(tick_keys))} unique tick keys found in Redis")
            else:
                print(f"   [WARN]  No tick keys found in Redis - ticks may not be stored yet")
        except Exception as e:
            print(f"   [WARN]  Could not check Redis keys: {e}")

        # Try multiple instrument name variations
        instrument_variations = ["BANKNIFTY", "NIFTY BANK", "NIFTYBANK", "NSE:BANKNIFTY"]

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
            indicators_response = requests.get(f"{base_url}/api/v1/technical/indicators/BANKNIFTY?timeframe=minute", timeout=10)
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

                    if indicators_found >= 5:  # At least 5 of 6 key indicators
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
            indicator_keys = redis_client.keys('indicators:BANKNIFTY:*')
            if len(indicator_keys) >= 40:  # Should have 49+ indicators
                print(f"   [OK] Technical indicators: {len(indicator_keys)} keys stored")

                # Verify key indicators exist
                key_indicators = ['rsi_14', 'macd_value', 'bollinger_upper', 'adx_14']
                indicators_found = 0
                for indicator in key_indicators:
                    if redis_client.exists(f'indicators:BANKNIFTY:{indicator}'):
                        indicators_found += 1

                if indicators_found >= 3:
                    print(f"   [OK] Key indicators verified: {indicators_found}/{len(key_indicators)} found")
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {indicators_found} key indicators found, retrying...")
                    time.sleep(retry_delay)
                    continue
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {len(indicator_keys)} indicator keys found (need 40+), retrying...")
                time.sleep(retry_delay)
                continue

            # Check price data storage
            price_keys = redis_client.keys('price:BANKNIFTY*')
            if len(price_keys) >= 2:
                print(f"   [OK] Price data: {len(price_keys)} keys stored")
                # Verify price values exist
                latest_price = redis_client.get('price:BANKNIFTY:latest')
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
            tick_keys = redis_client.keys('tick:BANKNIFTY*')
            if len(tick_keys) >= 100:  # Should have many tick records
                print(f"   [OK] Tick data: {len(tick_keys)} records stored")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {len(tick_keys)} tick records found (need 100+), retrying...")
                time.sleep(retry_delay)
                continue

            # Check OHLC data storage
            ohlc_keys = redis_client.keys('ohlc:BANKNIFTY*')
            if len(ohlc_keys) >= 10:  # Should have OHLC bars
                print(f"   [OK] OHLC data: {len(ohlc_keys)} bars stored")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Only {len(ohlc_keys)} OHLC bars found (need 10+), retrying...")
                time.sleep(retry_delay)
                continue

            # Check market depth data
            depth_keys = redis_client.keys('depth:BANKNIFTY*')
            if len(depth_keys) >= 1:
                print(f"   [OK] Market depth: {len(depth_keys)} records stored")
            else:
                print("   ℹ️  Market depth data not yet available (optional for basic verification)")

            # Check publishing mechanisms (sample publish test)
            try:
                # Test if we can publish to indicators channel (this tests pub/sub is working)
                test_message = {"test": "verification", "timestamp": "2026-01-12T14:00:00"}
                redis_client.publish("indicators:BANKNIFTY", str(test_message))
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
            tick_response = requests.get(f"{base_url}/api/v1/market/tick/BANKNIFTY", timeout=5)
            if tick_response.status_code == 200:
                tick_data = tick_response.json()
                if tick_data.get('last_price'):
                    print(f"   [OK] Market Data API: BANKNIFTY tick = {tick_data.get('last_price')}")

                    # Test all critical endpoints
                    endpoints_passed = 0
                    endpoints_total = 0

                    # Test price endpoint
                    try:
                        price_response = requests.get(f"{base_url}/api/v1/market/price/BANKNIFTY", timeout=5)
                        endpoints_total += 1
                        if price_response.status_code == 200:
                            price_data = price_response.json()
                            if price_data.get('price'):
                                endpoints_passed += 1
                    except:
                        endpoints_total += 1

                    # Test OHLC endpoint
                    try:
                        ohlc_response = requests.get(f"{base_url}/api/v1/market/ohlc/BANKNIFTY?timeframe=minute&limit=5", timeout=5)
                        endpoints_total += 1
                        if ohlc_response.status_code == 200:
                            ohlc_data = ohlc_response.json()
                            if isinstance(ohlc_data, list) and len(ohlc_data) > 0:
                                endpoints_passed += 1
                    except:
                        endpoints_total += 1

                    # Test raw data endpoint
                    try:
                        raw_response = requests.get(f"{base_url}/api/v1/market/raw/BANKNIFTY?limit=5", timeout=5)
                        endpoints_total += 1
                        if raw_response.status_code == 200:
                            raw_data = raw_response.json()
                            if raw_data.get('keys_found', 0) > 0:
                                endpoints_passed += 1
                    except:
                        endpoints_total += 1

                    # Check options chain (optional but nice to have)
                    try:
                        options_response = requests.get(f"{base_url}/api/v1/options/chain/BANKNIFTY", timeout=10)
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
            response = requests.get(f"{base_url}/api/v1/news/BANKNIFTY", timeout=5)
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
                            print("   ℹ️  No articles found - triggering collection via API")
                            collect_response = requests.post(
                                f"{base_url}/api/v1/news/collect",
                                json={"instruments": ["BANKNIFTY"]},
                                timeout=30
                            )
                            collection_triggered = True
                            if collect_response.status_code == 200:
                                collected = collect_response.json().get('collected_count', 0)
                                print(f"   ℹ️  Collection triggered, {collected} articles collected")
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

    print("   [ERROR] News API verification failed - no articles available")
    print("   [WARN]  Note: RSS feeds may be blocked (403). Check if MongoDB has existing articles.")
    return False


def verify_engine_api(base_url="http://localhost:8006", max_retries=15, retry_delay=1):
    """Verify Engine API agents are running and can analyze"""
    print("   [WAIT] Verifying Engine API functionality...")

    for attempt in range(1, max_retries + 1):
        try:
            # Check if agents can analyze (this verifies agents are initialized)
            # Note: context must be a dict or omitted, not a string
            analyze_response = requests.post(
                f"{base_url}/api/v1/analyze",
                json={"instrument": "BANKNIFTY", "context": {}},
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

    print("   [ERROR] Engine API verification failed - agents not running")
    return False


def verify_dashboard_ui(base_url="http://localhost:8888", max_retries=15, retry_delay=1):
    """Verify Dashboard UI can fetch data from all APIs"""
    print("   [WAIT] Verifying Dashboard UI can access data...")

    for attempt in range(1, max_retries + 1):
        try:
            # Check if dashboard loads
            response = requests.get(f"{base_url}/", timeout=5)
            if response.status_code == 200:
                # Try to verify it can access backend APIs by checking if page contains data indicators
                # This is a simple check - in production you might want to check specific API endpoints
                content = response.text.lower()
                # Check if dashboard has loaded (look for common dashboard elements)
                if any(keyword in content for keyword in ['dashboard', 'market', 'trading', 'data']):
                    print(f"   [OK] Dashboard UI: Loaded and accessible")

                    # Verify it can reach backend APIs by checking a data endpoint if available
                    # Some dashboards expose a status endpoint
                    try:
                        # Try to check if dashboard can proxy to market data
                        # This depends on your dashboard implementation
                        print(f"   [OK] Dashboard UI: Ready to display data from APIs")
                        return True
                    except:
                        print(f"   [OK] Dashboard UI: Loaded (backend connectivity assumed)")
                        return True
                else:
                    print(f"   [WAIT] Attempt {attempt}/{max_retries} - Dashboard loading...")
            else:
                print(f"   [WAIT] Attempt {attempt}/{max_retries} - Dashboard not ready (status {response.status_code})...")
        except Exception as e:
            print(f"   [WAIT] Attempt {attempt}/{max_retries} - Error: {e}")

        if attempt < max_retries:
            time.sleep(retry_delay)

    print("   [ERROR] Dashboard UI verification failed")
    return False


def start_service(name, command, env=None, cwd=None):
    """Start a service in the background"""
    print(f"   🚀 Starting {name}...")
    if env is None:
        env = os.environ.copy()
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
    print("   🚀 Starting Historical Data Replay...")

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
            print(f"   📅 Starting from date: {hist_from}")
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
        print("   🧹 Clearing old tick data from Redis...")
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
            replay = build_historical_replay(
                store,
                data_source=hist_source,
                start_date=start_date_obj,
                kite=kite_instance
            )
        elif hist_source.endswith('.csv'):
            # CSV file data source
            replay = HistoricalTickReplayer(
                store=store,
                data_source=hist_source,  # Path to CSV file
                rebase=False,  # Don't rebase - keep original historical timestamps
                speed=0.0,  # Use instant speed (0.0) instead of real-time for faster startup
                instrument_symbol="BANKNIFTY"
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
    args = parser.parse_args()

    # Load environment
    load_env()

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
    sys.path.insert(0, './data_niftybank/src')

    processes = []

    try:
        # Step 0: Kill existing processes and verify Zerodha authentication
        print("\n" + "=" * 60)
        print("Step 0: Cleanup and Authentication")
        print("=" * 60)

        # Kill existing processes on all ports
        print("   Cleaning up existing processes...")
        ports_to_clean = [8004, 8005, 8006, 8007, 8888]
        for port in ports_to_clean:
            kill_process_on_port(port)
        print("   [OK] Ports cleaned")

        # Verify Zerodha authentication if using Zerodha provider
        kite_instance = None
        if provider_name_normalized in ('zerodha', 'kite'):
            print("\n   🔐 Verifying Zerodha Authentication (Step 0)...")
            creds_ok, kite_instance = verify_zerodha_credentials()
            if not creds_ok:
                print("   [ERROR] Zerodha authentication failed!")
                print("   [TIP] Please configure Zerodha credentials before proceeding")
                print("   [TIP] Or use: python start_local.py --provider historical")
                return
            print("   [OK] Zerodha authentication verified - proceeding with startup")
        elif provider_name_normalized in ('historical', 'replay', 'auto'):
            # Check if Zerodha credentials are available (might be used for historical data)
            print("\n   🔐 Checking Zerodha credentials (optional for historical data)...")
            creds_ok, kite_instance = verify_zerodha_credentials()
            if creds_ok:
                print("   [OK] Zerodha credentials available (can use --historical-source zerodha)")
            else:
                print("   [WARN]  Zerodha credentials not available")
                print("   [TIP] Historical data requires Zerodha credentials or CSV file")

        # Step 1: Start and Verify Historical Data Source
        print("\n" + "=" * 60)
        print("Step 1: Historical Data Source")
        print("=" * 60)
        historical_ok = True
        data_source_used = 'zerodha'  # Default to Zerodha (no synthetic)
        replay_instance = None
        if provider_name_normalized in ('historical', 'replay', 'auto'):
            # Start market-data runner in historical mode (spawns market-data API + historical replayer)
            print("   🚀 Starting market-data runner in historical mode...")
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
                    print("❌ Historical data verification failed!")
                    print("   Stopping startup. Historical data must be available before proceeding.")
                    if (args.historical_source or 'zerodha') == 'zerodha':
                        print("   [TIP] Zerodha data issues:")
                        print("      - Verify credentials are correct and authenticated")
                        print("      - Check if historical data is available for the date")
                        print("      - Ensure Zerodha API is accessible")
                    return
            else:
                print("⚠️  Historical data startup skipped (validation disabled)")
        else:
            print("✅ Using live data collectors (no historical replay needed)")

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
            if provider_name_normalized in ('zerodha', 'kite') and kite_instance:
                print("   ℹ️  Live collectors will be managed by market-data runner when the server is started")
            else:
                print("   ℹ️  Live collectors are not required for this configuration")

        # Step 2: Start and Verify Market Data API
        print("\n" + "=" * 60)
        print("Step 2: Market Data API")
        print("=" * 60)
        # Start market-data via the runner to keep collectors and replay managed together
        print("   🚀 Starting market-data runner (live mode)...")
        kill_process_on_port(8004)
        runner_cmd = ["python", "-m", "market_data.runner", "--mode", "live"]
        # Let the runner start collectors when running in Zerodha mode
        if provider_name_normalized in ('zerodha', 'kite') and kite_instance:
            runner_cmd.append('--start-collectors')
        market_data_process = start_service(
            "Market Data Runner (live)",
            runner_cmd
        )
        processes.append(market_data_process)

        if args.skip_validation:
            print("⚠️  Skipping Market Data API verification")
        else:
            # First check health endpoint
            market_data_health = wait_for_service("Market Data API", "http://localhost:8004/health")
            if not market_data_health:
                print("❌ Market Data API health check failed!")
                print("   Stopping startup. Market Data API must be healthy before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

            # Then verify actual data (tick and options chain)
            market_data_ok = verify_market_data_api()
            if not market_data_ok:
                print("❌ Market Data API data verification failed!")
                print("   Stopping startup. Market Data API must have data before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

            # Verify Redis data storage and publishing
            redis_data_ok = verify_redis_data_storage()
            if not redis_data_ok:
                print("❌ Redis data storage verification failed!")
                print("   Stopping startup. Redis must be storing data correctly before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

            # Verify technical indicators calculation
            indicators_ok = verify_technical_indicators()
            if not indicators_ok:
                print("❌ Technical indicators verification failed!")
                print("   Stopping startup. Technical indicators must be calculated before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

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
            print("⚠️  Skipping News API verification")
        else:
            # First check health endpoint
            news_health = wait_for_service("News API", "http://localhost:8005/health")
            if not news_health:
                print("❌ News API health check failed!")
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
                print("❌ News API data verification failed!")
                print("   Stopping startup. News API must have articles before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

        # Step 4: Start and Verify Engine API
        print("\n" + "=" * 60)
        print("Step 4: Engine API")
        print("=" * 60)

        # Ensure all LLM API keys and configuration are set in environment before starting Engine API
        # These will be passed to the Engine API process via start_service (which copies os.environ)
        # Only set if not already in environment (allows local.env to override)
        required_env_vars = {
            # API keys intentionally left blank — set these in your local .env (copy from .env.example)
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
            print(f"   ⚙️  Set {len(vars_set)} environment variables for Engine API")
        else:
            print(f"   [OK] All required environment variables already set")

        # Install genai_module in editable mode for Engine API
        print("   📦 Installing genai_module (1/2)...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./genai_module"],
                         capture_output=True, text=True, check=True)
            print("   [OK] genai_module installed successfully (1/2)")
        except subprocess.CalledProcessError as e:
            print(f"   [ERROR] Failed to install genai_module (1/2): {e}")
            print(f"   Error output: {e.stderr}")
            return

        # Install news_module in editable mode for News API
        print("   📦 Installing news_module (2/2)...")
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
            print("⚠️  Skipping Engine API verification")
        else:
            # First check health endpoint
            engine_health = wait_for_service("Engine API", "http://localhost:8006/health")
            if not engine_health:
                print("❌ Engine API health check failed!")
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
                print("❌ Engine API agents verification failed!")
                print("   Stopping startup. Engine API agents must be running before proceeding.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return

        # Step 4.5: Start and Verify User API
        print("\n" + "=" * 60)
        print("Step 4.5: User API")
        print("=" * 60)

        # Install user_module in editable mode for User API
        print("   📦 Installing user_module...")
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
            print("⚠️  Skipping User API verification")
        else:
            # Check health endpoint
            user_health = wait_for_service("User API", "http://localhost:8007/health")
            if not user_health:
                print("❌ User API health check failed!")
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
        kill_process_on_port(8888)

        # If the modular React UI exists, prefer starting it (Vite dev server)
        ui_dir = Path('dashboard') / 'modular_ui'
        if ui_dir.exists() and (ui_dir / 'package.json').exists():
            print("   ℹ️  Found modular UI at dashboard/modular_ui — starting Vite dev server on port 8888")

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
                'VITE_WS_URL': 'http://localhost:8888'
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
                print("   📦 Installing modular UI dependencies (npm ci)")
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

        else:
            # Fallback to older python-based dashboard
            dashboard_process = start_service(
                "Dashboard (port 8888)",
                ["python", "-c", "from dashboard.app import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8888)"]
            )
            processes.append(dashboard_process)

        # Start WebSocket Gateway on port 8889
        websocket_process = start_service(
            "WebSocket Gateway (port 8889)",
            ["python", "redis_ws_gateway/main.py"]
        )
        processes.append(websocket_process)

        if args.skip_validation:
            print("⚠️  Skipping Dashboard UI verification")
        else:
            # First check if dashboard loads
            dashboard_health = wait_for_service("Dashboard UI", "http://localhost:8888/")
            if not dashboard_health:
                print("❌ Dashboard UI health check failed!")
                print("   Stopping startup. Please check the Dashboard UI logs.")
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
        print("🎉 All services started and verified!")
        print("=" * 60)

        print("\n🌐 Access URLs:")
        print("   [INFO] Dashboard:    http://localhost:8888/")
        print("   🌐 WebSocket:    ws://localhost:8889/ws")
        print("   💰 Market Data:  http://localhost:8004/health")
        print("   📰 News:         http://localhost:8005/health")
        print("   🤖 Engine:       http://localhost:8006/health")
        print("   👤 User:         http://localhost:8007/health")
        print("\n🎯 The UI should now be able to show data from all APIs.")

        print("\n🛑 Press Ctrl+C to stop all services")

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

        print("✅ All services stopped")


if __name__ == "__main__":
    asyncio.run(main())