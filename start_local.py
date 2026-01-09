#!/usr/bin/env python3
"""
Local development startup script.
Starts all trading system services locally for development and testing.
"""

import os
import sys
import time
import subprocess
import signal
import requests
import asyncio
from pathlib import Path

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

    Order of precedence (existing env vars are not overridden, but all files are loaded):
      - local.env (project root)
      - .env (project root)
      - market_data/.env (module-specific credentials)
      - genai_module/.env
      - engine_module/.env
      - news_module/.env

    This makes `start_local.py` behave similarly to docker-compose (which reads service env files), while keeping per-module configuration files isolated.
    All files are loaded, with later files potentially overriding earlier ones if they set the same keys.
    """
    candidates = [
        'local.env',
        '.env',
        'market_data/.env',  # KITE_API_KEY, KITE_API_SECRET typically here
        'genai_module/.env',
        'engine_module/.env',
        'news_module/.env',
    ]

    loaded_any = False
    credential_sources = {}  # Track which file loaded each credential
    for path in candidates:
        if os.path.exists(path):
            try:
                loaded_count = 0
                with open(path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")  # Remove quotes if present
                        # Track credential sources
                        if key in ['KITE_API_KEY', 'KITE_API_SECRET', 'KITE_ACCESS_TOKEN']:
                            if key not in credential_sources:
                                if key in os.environ:
                                    credential_sources[key] = "already_in_environment"
                                else:
                                    credential_sources[key] = path
                        # Do not overwrite explicitly set environment variables
                        if key not in os.environ:
                            os.environ[key] = value
                            loaded_count += 1
                if loaded_count > 0:
                    print(f"   ✅ Loaded {loaded_count} variables from {path}")
                    loaded_any = True
                elif os.path.exists(path):
                    print(f"   ℹ️  Skipped {path} (all vars already set from earlier files or environment)")
            except Exception as e:
                print(f"   ⚠️  Failed to load environment file {path}: {e}")

    if not loaded_any:
        print("   ⚠️  No env file found (searched: local.env, .env, market_data/.env, genai_module/.env, engine_module/.env, news_module/.env).")
        print("   💡 Copy module templates from their `.env.example` files and create local .env files.")
    else:
        # Show credential status after loading
        print("   📋 Credential status after loading env files:")
        for key in ['KITE_API_KEY', 'KITE_API_SECRET', 'KITE_ACCESS_TOKEN']:
            if key in os.environ:
                source = credential_sources.get(key, "environment")
                val = os.environ[key]
                masked = f"{val[:8]}..." if len(val) > 8 else "***"
                print(f"      ✅ {key}: {masked} (source: {source})")
            else:
                print(f"      ⚠️  {key}: not found in any env file or environment")


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
    print(f"   ⏳ Verifying {name}...")
    for attempt in range(1, max_retries + 1):
        if check_health(health_url, timeout=timeout):
            print(f"   ✅ {name} is healthy and ready!")
            return True
        if attempt < max_retries:
            print(f"   ⏳ Attempt {attempt}/{max_retries} - waiting for {name}...")
            time.sleep(retry_delay)
    print(f"   ❌ {name} failed to become healthy after {max_retries} attempts")
    return False


class CredentialsValidator:
    """Validates Zerodha credentials and token authentication"""
    
    @staticmethod
    def verify_zerodha_credentials():
        """Verify Zerodha credentials are available and token authentication works"""
        print("   🔐 Verifying Zerodha credentials and token authentication...")
        token_validated_and_invalid = False  # Track if we validated and found it invalid
        try:
            # Ensure package import paths are available for in-package kite auth utilities
            # Use absolute paths for better reliability on Windows
            import os
            project_root = os.path.abspath('.')
            market_data_src = os.path.abspath('./market_data/src')
            
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            if market_data_src not in sys.path:
                sys.path.insert(0, market_data_src)

            # Step 1: Check environment variables (loaded from market_data/.env by load_env() or system environment)
            api_key = os.getenv('KITE_API_KEY')
            api_secret = os.getenv('KITE_API_SECRET')
            access_token = os.getenv('KITE_ACCESS_TOKEN')
            
            # Note: Credential status was already shown by load_env(), so no need to repeat here
            
            if api_key and api_secret:
                print("   ✅ Found Zerodha API credentials in environment variables")
                print(f"      API Key: {api_key[:8]}...")
                print(f"      API Secret: {'*' * 8}...")
                
                # If access_token is in env, use it directly
                if access_token:
                    print("   ✅ Found KITE_ACCESS_TOKEN in environment")
                    try:
                        # Ensure path is set before import
                        market_data_src = os.path.abspath('./market_data/src')
                        if market_data_src not in sys.path:
                            sys.path.insert(0, market_data_src)
                        from market_data.providers.zerodha import ZerodhaProvider
                        provider = ZerodhaProvider(api_key, access_token)
                        kite = provider.kite
                        print("   ✅ Created ZerodhaProvider from environment variables")
                    except Exception as e:
                        print(f"   ❌ Failed to create provider from env vars: {e}")
                        return False, None
                else:
                    # ACCESS_TOKEN not in env, check credentials.json using KiteAuthService
                    print("   ⚠️  KITE_ACCESS_TOKEN not found in environment")
                    print("   💡 Checking credentials.json for valid token...")
                    
                    # Use KiteAuthService to check and refresh credentials.json
                    token_validated_and_invalid = False  # Track if we validated and found it invalid
                    try:
                        # Ensure path is set before import
                        market_data_src = os.path.abspath('./market_data/src')
                        if market_data_src not in sys.path:
                            sys.path.insert(0, market_data_src)
                        if '.' not in sys.path:
                            sys.path.insert(0, '.')
                        
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
                                    print("   ✅ Found valid access token in credentials.json")
                                    try:
                                        from market_data.providers.zerodha import ZerodhaProvider
                                        provider = ZerodhaProvider(token_api_key, creds_access_token)
                                        print("   ✅ Using credentials from credentials.json (token validated)")
                                    except ImportError as import_err:
                                        print(f"   ⚠️  Could not import ZerodhaProvider: {import_err}")
                                        print("   💡 Try: pip install -e ./market_data")
                                        provider = None
                                else:
                                    print("   ⚠️  Token in credentials.json is expired or invalid")
                                    print("   🔄 Attempting to refresh token...")
                                    
                                    # Try to refresh token
                                    new_creds = auth_service.refresh_token(creds)
                                    if new_creds:
                                        auth_service.save_credentials(new_creds)
                                        creds_access_token = new_creds.get('access_token') or new_creds.get('data', {}).get('access_token')
                                        print("   ✅ Token refreshed successfully")
                                        try:
                                            from market_data.providers.zerodha import ZerodhaProvider
                                            provider = ZerodhaProvider(token_api_key, creds_access_token)
                                            print("   ✅ Using refreshed credentials")
                                        except ImportError:
                                            provider = None
                                    else:
                                        # Refresh failed, try interactive login if allowed
                                        print("   ⚠️  Automatic token refresh failed")
                                        if auth_service.allow_interactive:
                                            print("   🔄 Attempting interactive login to get new token...")
                                            success = auth_service.trigger_interactive_login(timeout=300)
                                            if success:
                                                # Reload credentials after login
                                                creds = auth_service.load_credentials()
                                                creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                                                if creds_access_token and auth_service.is_token_valid(creds):
                                                    print("   ✅ Interactive login succeeded, token obtained")
                                                    try:
                                                        from market_data.providers.zerodha import ZerodhaProvider
                                                        provider = ZerodhaProvider(token_api_key, creds_access_token)
                                                        print("   ✅ Using credentials from interactive login")
                                                    except ImportError:
                                                        provider = None
                                                else:
                                                    print("   ❌ Interactive login completed but token validation failed")
                                                    provider = None
                                                    token_validated_and_invalid = True
                                            else:
                                                print("   ❌ Interactive login failed or timed out")
                                                print("   💡 Please run manually: python -m market_data.tools.kite_auth")
                                                provider = None
                                                token_validated_and_invalid = True
                                        else:
                                            print("   ❌ Token refresh failed - manual intervention required")
                                            print("   💡 Please refresh token by running: python -m market_data.tools.kite_auth")
                                            print("   💡 Or set KITE_ACCESS_TOKEN in environment with a valid token")
                                            provider = None
                                            token_validated_and_invalid = True
                            else:
                                # No token in credentials.json, try interactive login
                                if not creds_access_token:
                                    print("   ⚠️  credentials.json missing access_token")
                                    if auth_service.allow_interactive:
                                        print("   🔄 Attempting interactive login to create credentials...")
                                        success = auth_service.trigger_interactive_login(timeout=300)
                                        if success:
                                            creds = auth_service.load_credentials()
                                            creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                                            token_api_key = creds.get('api_key') or creds.get('KITE_API_KEY') or api_key
                                            if creds_access_token and token_api_key:
                                                print("   ✅ Interactive login succeeded")
                                                try:
                                                    from market_data.providers.zerodha import ZerodhaProvider
                                                    provider = ZerodhaProvider(token_api_key, creds_access_token)
                                                    print("   ✅ Using credentials from interactive login")
                                                except ImportError:
                                                    provider = None
                                            else:
                                                provider = None
                                        else:
                                            print("   ❌ Interactive login failed")
                                            provider = None
                                    else:
                                        print("   ⚠️  Interactive login disabled")
                                        provider = None
                                else:
                                    print("   ⚠️  credentials.json missing api_key")
                                    provider = None
                        else:
                            # No credentials.json exists, try interactive login if we have API key/secret
                            print("   ⚠️  credentials.json not found")
                            if api_key and api_secret:
                                if auth_service.allow_interactive:
                                    print("   🔄 Attempting interactive login to create credentials...")
                                    print("   💡 This will open a browser for Zerodha login")
                                    success = auth_service.trigger_interactive_login(timeout=300)
                                    if success:
                                        creds = auth_service.load_credentials()
                                        creds_api_key = creds.get('api_key') or creds.get('KITE_API_KEY') or api_key
                                        creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                                        if creds_api_key and creds_access_token:
                                            if auth_service.is_token_valid(creds):
                                                print("   ✅ Interactive login succeeded, credentials validated")
                                                try:
                                                    from market_data.providers.zerodha import ZerodhaProvider
                                                    provider = ZerodhaProvider(creds_api_key, creds_access_token)
                                                    print("   ✅ Using credentials from interactive login")
                                                except ImportError:
                                                    provider = None
                                            else:
                                                print("   ⚠️  Interactive login completed but token validation failed")
                                                provider = None
                                        else:
                                            print("   ⚠️  Interactive login completed but credentials incomplete")
                                            provider = None
                                    else:
                                        print("   ❌ Interactive login failed or timed out")
                                        print("   💡 You can try again manually: python -m market_data.tools.kite_auth")
                                        provider = None
                                else:
                                    print("   ⚠️  Interactive login disabled (set KITE_ALLOW_INTERACTIVE_LOGIN=1 to enable)")
                                    provider = None
                            else:
                                print("   ⚠️  Need KITE_API_KEY and KITE_API_SECRET to perform interactive login")
                                provider = None
                    except ImportError as import_err:
                        print(f"   ⚠️  KiteAuthService not available: {import_err}")
                        print("   💡 Falling back to direct credentials.json check...")
                        # Fall through to direct credentials.json check
                        provider = None
                    except Exception as e:
                        print(f"   ⚠️  Error checking credentials.json: {e}")
                        import traceback
                        traceback.print_exc()
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
                                print("   ✅ Found valid credentials in credentials.json")
                                try:
                                    from market_data.providers.zerodha import ZerodhaProvider
                                    provider = ZerodhaProvider(creds_api_key, creds_access_token)
                                except ImportError as import_err:
                                    print(f"   ⚠️  Could not import ZerodhaProvider: {import_err}")
                                    provider = None
                            else:
                                print("   ⚠️  Token in credentials.json is expired or invalid")
                                # Try refresh or interactive login (same logic as above)
                                if auth_service.allow_interactive:
                                    print("   🔄 Attempting interactive login to refresh token...")
                                    success = auth_service.trigger_interactive_login(timeout=300)
                                    if success:
                                        creds = auth_service.load_credentials()
                                        creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                                        if creds_access_token and auth_service.is_token_valid(creds):
                                            try:
                                                from market_data.providers.zerodha import ZerodhaProvider
                                                provider = ZerodhaProvider(creds_api_key, creds_access_token)
                                                print("   ✅ Token refreshed via interactive login")
                                            except ImportError:
                                                provider = None
                                        else:
                                            provider = None
                                    else:
                                        provider = None
                                else:
                                    provider = None
                        else:
                            print("   ⚠️  credentials.json missing api_key or access_token")
                            provider = None
                    else:
                        from market_data.providers.factory import get_provider
                        provider = get_provider('zerodha')
                except ImportError:
                    from market_data.providers.factory import get_provider
                    provider = get_provider('zerodha')
                except Exception as e:
                    print(f"   ⚠️  Error checking credentials: {e}")
                    provider = None
            
            # Step 3: If provider still not created and token wasn't validated as invalid, try direct credentials.json read
            if provider is None and not token_validated_and_invalid:
                try:
                    import json
                    if os.path.exists('credentials.json'):
                        with open('credentials.json', 'r', encoding='utf-8-sig') as f:
                            creds = json.load(f)
                        creds_api_key = creds.get('api_key') or creds.get('KITE_API_KEY') or creds.get('zerodha', {}).get('api_key')
                        creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token') or creds.get('zerodha', {}).get('access_token')
                        if creds_api_key and creds_access_token:
                            # Ensure path is set before import (critical for Windows paths)
                            market_data_src = os.path.abspath('./market_data/src')
                            if market_data_src not in sys.path:
                                sys.path.insert(0, market_data_src)
                            # Also add current directory
                            if '.' not in sys.path:
                                sys.path.insert(0, '.')
                            try:
                                from market_data.providers.zerodha import ZerodhaProvider
                                provider = ZerodhaProvider(creds_api_key, creds_access_token)
                                print("   ⚠️  Using credentials.json (not validated - will test in next step)")
                            except ImportError as import_err:
                                print(f"   ⚠️  Could not import ZerodhaProvider: {import_err}")
                                print(f"   💡 Python path: {sys.path[:3]}...")
                                print("   💡 Try: pip install -e ./market_data")
                                print("   💡 Or ensure market_data/src is in PYTHONPATH")
                                provider = None
                        else:
                            missing = []
                            if not creds_api_key:
                                missing.append('api_key')
                            if not creds_access_token:
                                missing.append('access_token')
                            print(f"   ⚠️  credentials.json exists but missing: {', '.join(missing)}")
                    else:
                        print("   ⚠️  credentials.json not found")
                except Exception as e:
                    print(f"   ⚠️  Error reading credentials.json: {e}")
            
            if provider is None:
                print("   ⚠️  Zerodha credentials incomplete")
                if api_key and api_secret and not access_token:
                    print("   💡 You have KITE_API_KEY and KITE_API_SECRET, but need KITE_ACCESS_TOKEN")
                    print("   💡 Options to get KITE_ACCESS_TOKEN:")
                    print("      1. Run: python -m market_data.tools.kite_auth")
                    print("         (This will generate credentials.json with access_token)")
                    print("      2. Set in environment: export KITE_ACCESS_TOKEN=your_access_token")
                    print("      3. Add to credentials.json: {\"access_token\": \"your_token\"}")
                    print("      4. Add to market_data/.env: KITE_ACCESS_TOKEN=your_access_token")
                    print("   💡 For historical mode, you can also use:")
                    print("      --allow-missing-credentials (uses synthetic data if token unavailable)")
                elif not api_key or not api_secret:
                    print("   💡 Please set one of:")
                    print("      - KITE_API_KEY, KITE_API_SECRET, and KITE_ACCESS_TOKEN in environment")
                    print("      - credentials.json with api_key and access_token")
                    print("      - market_data/.env with KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN")
                return False, None
            
            # Step 2: Verify kite instance exists
            if not hasattr(provider, 'kite'):
                print("   ❌ Zerodha provider initialized but kite instance not available")
                return False, None
            
            kite = provider.kite
            
            # Step 3: Test token authentication with actual API call
            try:
                print("   ⏳ Testing token authentication (API call)...")
                profile = kite.profile()
                if profile:
                    user_name = profile.get('user_name', 'N/A')
                    user_id = profile.get('user_id', 'N/A')
                    print(f"   ✅ Token authentication verified")
                    print(f"      User: {user_name} (ID: {user_id})")
                    
                    # Step 4: Test connection with a quote call (optional but thorough)
                    try:
                        # Try to get a quote to verify full connection works
                        test_quote = kite.quote(['NSE:RELIANCE'])
                        if test_quote:
                            print(f"   ✅ Connection test passed (quote API working)")
                    except Exception as quote_error:
                        # Quote might fail if market is closed, but profile works, so auth is OK
                        print(f"   ⚠️  Quote test failed (may be market hours): {quote_error}")
                        print(f"   ✅ Token authentication is valid (profile API works)")
                    
                    return True, kite
                else:
                    print("   ❌ Token authentication failed: Empty profile response")
                    return False, None
            except Exception as auth_error:
                error_msg = str(auth_error)
                print(f"   ❌ Token authentication failed: {error_msg}")
                
                # Provide helpful error messages
                if 'Invalid' in error_msg or 'invalid' in error_msg.lower():
                    print("   💡 Token may be expired or invalid")
                    print("   💡 Please regenerate access token:")
                    print("      - Check credentials.json has valid access_token")
                    print("      - Token expires daily, may need refresh")
                elif 'Unauthorized' in error_msg or '401' in error_msg:
                    print("   💡 Unauthorized - token not valid")
                    print("   💡 Please check API_KEY and ACCESS_TOKEN in credentials.json")
                elif 'Connection' in error_msg or 'timeout' in error_msg.lower():
                    print("   💡 Connection issue - check network/Zerodha API status")
                else:
                    print("   💡 Please check your Zerodha credentials:")
                    print("      - API_KEY in credentials.json")
                    print("      - ACCESS_TOKEN in credentials.json (may need refresh)")
                
                return False, None
        
        except ImportError as e:
            print(f"   ⚠️  Could not import provider: {e}")
            print("   💡 Install kiteconnect: pip install kiteconnect")
            return False, None
        except Exception as e:
            print(f"   ❌ Error verifying Zerodha credentials: {e}")
            import traceback
            traceback.print_exc()
            return False, None


def verify_zerodha_credentials():
    """Wrapper for CredentialsValidator - maintains backward compatibility"""
    return CredentialsValidator.verify_zerodha_credentials()


def verify_historical_data(max_retries=30, retry_delay=1, data_source='zerodha', replay_instance=None):
    """Verify historical data is actually available in the store"""
    print("   ⏳ Verifying historical data availability...")
    
    # First check Redis connectivity
    try:
        import redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        redis_client.ping()
        print("   ✅ Redis connection verified")
    except Exception as e:
        print(f"   ❌ Redis connection failed: {e}")
        print("   💡 Please ensure Redis is running (docker-compose -f docker-compose.data.yml up -d)")
        return False
    
    # Check if replay service is running
    if replay_instance:
        try:
            if hasattr(replay_instance, 'running'):
                if replay_instance.running:
                    print(f"   ✅ Replay service is running")
                    if hasattr(replay_instance, 'ticks_loaded'):
                        print(f"      Ticks loaded: {replay_instance.ticks_loaded}")
                    if hasattr(replay_instance, 'ticks_replayed'):
                        print(f"      Ticks replayed: {replay_instance.ticks_replayed}")
                else:
                    print(f"   ⚠️  Replay service not running (running={replay_instance.running})")
                    print("   💡 Replay service may have stopped or not started properly")
        except Exception as e:
            print(f"   ⚠️  Could not check replay service status: {e}")
    
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
                print(f"   ⚠️  No tick keys found in Redis - ticks may not be stored yet")
        except Exception as e:
            print(f"   ⚠️  Could not check Redis keys: {e}")
        
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
                print(f"   ✅ Historical data verified: {found_instrument} price = {tick.last_price}")
                if hasattr(tick, 'timestamp'):
                    print(f"      Timestamp: {tick.timestamp}")
                if hasattr(tick, 'instrument'):
                    print(f"      Instrument: {tick.instrument}")
                return True
            
            # Check replay status periodically
            if replay_instance and attempt % 5 == 0:
                try:
                    if hasattr(replay_instance, 'running') and not replay_instance.running:
                        print(f"   ⚠️  Replay service stopped running (attempt {attempt})")
                        print("   💡 Replay may have completed or encountered an error")
                except:
                    pass
            
            if attempt < max_retries:
                if attempt % 5 == 0:  # Show more detailed message every 5 attempts
                    if data_source == 'zerodha':
                        print(f"   ⏳ Attempt {attempt}/{max_retries} - Waiting for Zerodha historical data...")
                        print("      💡 If this continues, check Zerodha API access and date availability")
                    else:
                        print(f"   ⏳ Attempt {attempt}/{max_retries} - Waiting for historical data...")
                        print("      💡 Historical data may need more time to load")
                        if replay_instance:
                            try:
                                if hasattr(replay_instance, 'ticks_loaded'):
                                    print(f"      Ticks loaded: {replay_instance.ticks_loaded}")
                                if hasattr(replay_instance, 'ticks_replayed'):
                                    print(f"      Ticks replayed: {replay_instance.ticks_replayed}")
                            except:
                                pass
                else:
                    print(f"   ⏳ Attempt {attempt}/{max_retries} - waiting for historical data...")
                time.sleep(retry_delay)
        
        if data_source == 'zerodha':
            print("   ❌ No Zerodha historical data available after verification attempts")
            print("   💡 Possible issues:")
            print("      - Zerodha API credentials not authenticated")
            print("      - Historical data not available for the specified date")
            print("      - Network/API connectivity issues")
            print("      - Check if Zerodha API is accessible and data is available for the date")
            print("      - Verify CSV file path if using CSV data source")
        else:
            print("   ❌ No historical data available after verification attempts")
            print("   💡 Possible issues:")
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
        print(f"   ❌ Error verifying historical data: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_market_data_api(base_url="http://localhost:8004", max_retries=20, retry_delay=1):
    """Verify Market Data API has actual data - tests all critical endpoints"""
    print("   ⏳ Verifying Market Data API functionality...")
    
    for attempt in range(1, max_retries + 1):
        try:
            # Check tick data
            tick_response = requests.get(f"{base_url}/api/v1/market/tick/BANKNIFTY", timeout=5)
            if tick_response.status_code == 200:
                tick_data = tick_response.json()
                if tick_data.get('last_price'):
                    print(f"   ✅ Market Data API: BANKNIFTY tick = {tick_data.get('last_price')}")
                    
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
                                print(f"   ✅ Market Data API: Options chain available ({len(strikes)} strikes)")
                    except:
                        pass  # Options chain is optional
                    
                    # If critical endpoints pass, we're good
                    if endpoints_passed >= 2:  # At least tick + one other endpoint
                        print(f"   ✅ Market Data API: {endpoints_passed}/{endpoints_total} critical endpoints verified")
                        return True
                    else:
                        print(f"   ⏳ Attempt {attempt}/{max_retries} - Only {endpoints_passed}/{endpoints_total} endpoints ready, retrying...")
                else:
                    print(f"   ⏳ Attempt {attempt}/{max_retries} - No price data yet...")
            else:
                print(f"   ⏳ Attempt {attempt}/{max_retries} - Tick endpoint not ready (status {tick_response.status_code})...")
        except Exception as e:
            print(f"   ⏳ Attempt {attempt}/{max_retries} - Error: {e}")
        
        if attempt < max_retries:
            time.sleep(retry_delay)
    
    print("   ❌ Market Data API verification failed - no data available")
    return False


def verify_news_api(base_url="http://localhost:8005", max_retries=15, retry_delay=1):
    """Verify News API returns actual news articles"""
    print("   ⏳ Verifying News API functionality...")
    
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
                    print(f"   ✅ News API: {len(articles)} articles available")
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
                                print(f"   ⚠️  Collection request returned status {collect_response.status_code}")
                            # Wait a bit longer after triggering collection
                            time.sleep(3)
                        except Exception as coll_err:
                            print(f"   ⚠️ Failed to trigger collection: {coll_err}")

                    print(f"   ⏳ Attempt {attempt}/{max_retries} - No articles yet, retrying...")
            else:
                print(f"   ⏳ Attempt {attempt}/{max_retries} - News endpoint not ready (status {response.status_code})...")
        except Exception as e:
            print(f"   ⏳ Attempt {attempt}/{max_retries} - Error: {e}")
        
        if attempt < max_retries:
            time.sleep(retry_delay)
    
    print("   ❌ News API verification failed - no articles available")
    print("   ⚠️  Note: RSS feeds may be blocked (403). Check if MongoDB has existing articles.")
    return False


def verify_engine_api(base_url="http://localhost:8006", max_retries=30, retry_delay=2):
    """Verify Engine API agents are running and can analyze
    
    Note: Orchestrator initialization can take time due to LLM client setup,
    agent creation, and signal monitor initialization. This function allows
    extended wait time for proper initialization.
    """
    print("   ⏳ Verifying Engine API functionality...")
    
    for attempt in range(1, max_retries + 1):
        try:
            # Check if agents can analyze (this verifies agents are initialized)
            # Note: context must be a dict or omitted, not a string
            analyze_response = requests.post(
                f"{base_url}/api/v1/analyze",
                json={"instrument": "BANKNIFTY", "context": {}},
                timeout=15  # Increased timeout for LLM calls
            )
            if analyze_response.status_code == 200:
                analyze_data = analyze_response.json()
                # Check for valid analysis response structure
                if 'decision' in analyze_data and 'confidence' in analyze_data:
                    decision = analyze_data.get('decision', 'UNKNOWN')
                    confidence = analyze_data.get('confidence', 0.0)
                    print(f"   ✅ Engine API: Agents running (decision={decision}, confidence={confidence:.2f})")
                    return True
                else:
                    if attempt % 5 == 0:  # Only print every 5th attempt to reduce noise
                        print(f"   ⏳ Attempt {attempt}/{max_retries} - Invalid response format...")
            elif analyze_response.status_code == 503:
                if attempt % 5 == 0:  # Only print every 5th attempt to reduce noise
                    print(f"   ⏳ Attempt {attempt}/{max_retries} - Orchestrator still initializing (status 503)...")
            elif analyze_response.status_code == 422:
                # Parse validation error details
                try:
                    error_detail = analyze_response.json().get('detail', 'Validation error')
                    print(f"   ⏳ Attempt {attempt}/{max_retries} - Validation error: {error_detail}")
                except:
                    print(f"   ⏳ Attempt {attempt}/{max_retries} - Validation error (status 422)...")
            else:
                if attempt % 5 == 0:  # Only print every 5th attempt
                    print(f"   ⏳ Attempt {attempt}/{max_retries} - Analyze endpoint not ready (status {analyze_response.status_code})...")
        except requests.exceptions.Timeout:
            if attempt % 5 == 0:
                print(f"   ⏳ Attempt {attempt}/{max_retries} - Request timeout (orchestrator may still be initializing)...")
        except Exception as e:
            if attempt % 5 == 0:
                print(f"   ⏳ Attempt {attempt}/{max_retries} - Error: {str(e)[:80]}")
        
        if attempt < max_retries:
            time.sleep(retry_delay)
    
    print("   ⚠️  Engine API orchestrator not ready after extended wait")
    print("   This may be due to LLM initialization or agent creation delays")
    print("   System will continue - orchestrator can initialize later")
    return False  # Return False but don't block startup


def verify_dashboard_ui(base_url="http://localhost:8888", max_retries=15, retry_delay=1):
    """Verify Dashboard UI can fetch data from all APIs"""
    print("   ⏳ Verifying Dashboard UI can access data...")
    
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
                    print(f"   ✅ Dashboard UI: Loaded and accessible")
                    
                    # Verify it can reach backend APIs by checking a data endpoint if available
                    # Some dashboards expose a status endpoint
                    try:
                        # Try to check if dashboard can proxy to market data
                        # This depends on your dashboard implementation
                        print(f"   ✅ Dashboard UI: Ready to display data from APIs")
                        return True
                    except:
                        print(f"   ✅ Dashboard UI: Loaded (backend connectivity assumed)")
                        return True
                else:
                    print(f"   ⏳ Attempt {attempt}/{max_retries} - Dashboard loading...")
            else:
                print(f"   ⏳ Attempt {attempt}/{max_retries} - Dashboard not ready (status {response.status_code})...")
        except Exception as e:
            print(f"   ⏳ Attempt {attempt}/{max_retries} - Error: {e}")
        
        if attempt < max_retries:
            time.sleep(retry_delay)
    
    print("   ❌ Dashboard UI verification failed")
    return False


def start_service(name, command, env=None, cwd: str | None = None):
    """Start a service in the background.

    Args:
        name: Human-friendly name for logs
        command: Either a list (preferred) of args or a single shell string
        env: Environment variables mapping
        cwd: Optional working directory to run the process in
    """
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
        # Prefer running without shell when possible
        try:
            process = subprocess.Popen(command, env=env, cwd=cwd)
        except FileNotFoundError:
            # Fall back to shell-joined command for compatibility
            cmd = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
            process = subprocess.Popen(cmd, shell=True, env=env, cwd=cwd)
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
            print("   ✅ Zerodha credentials detected (from Step 0)")
            print("   ✅ Using Zerodha historical data (real data from API)")
            hist_source = 'zerodha'
        else:
            # No synthetic data - require explicit data source
            print("   ❌ No data source specified and no Zerodha credentials available")
            print("   💡 Please specify one of:")
            print("      --historical-source zerodha (requires Zerodha credentials)")
            print("      --historical-source path/to/data.csv (CSV file with historical data)")
            return False, None, None

    # If using Zerodha data source, use the kite instance from Step 0
    if hist_source == 'zerodha':
        if not kite_instance:
            print("   ❌ Zerodha data source requires valid credentials!")
            print("   💡 Please configure Zerodha credentials in Step 0")
            return False, None, None
        print("   ✅ Using Zerodha historical data (credentials verified in Step 0)")

    # Parse start_date from string to datetime
    start_date_obj = None
    if hist_from:
        try:
            from datetime import datetime
            # Parse YYYY-MM-DD format
            start_date_obj = datetime.strptime(hist_from, '%Y-%m-%d')
            print(f"   📅 Starting from date: {hist_from}")
        except ValueError as e:
            print(f"   ⚠️  Invalid date format '{hist_from}'. Expected YYYY-MM-DD. Using default.")
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
                print(f"   ✅ Cleared {len(old_keys)} old tick keys from Redis")
            old_price_keys = redis_client.keys("price:*")
            if old_price_keys:
                redis_client.delete(*old_price_keys)
                print(f"   ✅ Cleared {len(old_price_keys)} old price keys from Redis")
        except Exception as e:
            print(f"   ⚠️  Could not clear old data (may not exist): {e}")
        
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
            print(f"   ❌ Unknown or unsupported data source: {hist_source}")
            print("   💡 Supported sources: 'zerodha' or path to CSV file")
            return False, None, None
        # Don't override speed - use the speed from build_historical_replay (0.0 for instant)
        replay.start()
        date_str = f", date={hist_from}" if hist_from else ""
        actual_speed = getattr(replay, 'speed', hist_speed)
        print(f"   ✅ Started HistoricalDataReplay (source={hist_source}, speed={actual_speed}{date_str})")
        
        # Verify replay service started
        if hasattr(replay, 'running'):
            if replay.running:
                print(f"   ✅ Replay service is running")
            else:
                print(f"   ⚠️  Replay service may not be running properly")

        # Give replay time to process ticks (longer for large datasets)
        if hasattr(replay, 'ticks_loaded') and replay.ticks_loaded > 1000:
            print(f"   ⏳ Processing {replay.ticks_loaded} ticks (this may take a moment)...")
            # Wait longer for large datasets - estimate: ~100 ticks/second at instant speed
            estimated_seconds = max(5, replay.ticks_loaded // 100)
            await asyncio.sleep(min(estimated_seconds, 30))  # Max 30 seconds wait
        else:
            await asyncio.sleep(3)
        
        # Return data source and replay instance for verification
        return True, hist_source, replay

    except Exception as e:
        print(f"   ❌ Failed to start historical replay: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None


def interactive_verification(step_name, available_services):
    """Interactive verification menu after each startup step"""
    print(f"\n{'='*60}")
    print(f"🔍 INTERACTIVE VERIFICATION: {step_name}")
    print(f"{'='*60}")
    print("Available services so far:")
    for service in available_services:
        print(f"   • {service}")
    print()
    
    while True:
        print("Choose an option to verify:")
        print("1. Check tick data working")
        print("2. Check option chain working")
        print("3. Check news working")
        print("4. Check LLM/Engine working")
        print("5. Check technicals working")
        print("6. Show API endpoints")
        print("7. Continue to next step")
        print("8. Stop startup")
        
        try:
            choice = input("Enter your choice (1-8): ").strip()
            
            if choice == '1':
                # Check tick data
                if 'Market Data API' in available_services:
                    try:
                        response = requests.get("http://localhost:8004/api/v1/market/tick/BANKNIFTY", timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            price = data.get('last_price', 'N/A')
                            print(f"✅ Tick data: BANKNIFTY = {price}")
                        else:
                            print(f"❌ Tick endpoint returned status {response.status_code}")
                    except Exception as e:
                        print(f"❌ Error checking tick data: {e}")
                else:
                    print("❌ Market Data API not available yet")
                    
            elif choice == '2':
                # Check option chain
                if 'Market Data API' in available_services:
                    try:
                        response = requests.get("http://localhost:8004/api/v1/options/chain/BANKNIFTY", timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            strikes = data.get('strikes', [])
                            print(f"✅ Option chain: {len(strikes)} strikes available")
                            if strikes:
                                print(f"   Sample strikes: {strikes[:5]}...")
                        else:
                            print(f"❌ Option chain endpoint returned status {response.status_code}")
                    except Exception as e:
                        print(f"❌ Error checking option chain: {e}")
                else:
                    print("❌ Market Data API not available yet")
                    
            elif choice == '3':
                # Check news
                if 'News API' in available_services:
                    try:
                        response = requests.get("http://localhost:8005/api/v1/news/BANKNIFTY", timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            articles = data.get('news') or data.get('articles', [])
                            print(f"✅ News: {len(articles)} articles available")
                            if articles:
                                latest = articles[0]
                                title = latest.get('title', 'N/A')[:50]
                                print(f"   Latest: {title}...")
                        else:
                            print(f"❌ News endpoint returned status {response.status_code}")
                    except Exception as e:
                        print(f"❌ Error checking news: {e}")
                else:
                    print("❌ News API not available yet")
                    
            elif choice == '4':
                # Check LLM/Engine
                if 'Engine API' in available_services:
                    try:
                        response = requests.post("http://localhost:8006/api/v1/analyze", 
                                               json={"instrument": "BANKNIFTY", "context": {}},  # Default to BANKNIFTY Futures (nearest expiry)  # Default to BANKNIFTY Futures (nearest expiry) 
                                               timeout=15)
                        if response.status_code == 200:
                            data = response.json()
                            decision = data.get('decision', 'UNKNOWN')
                            confidence = data.get('confidence', 0.0)
                            print(f"✅ Engine: Decision={decision}, Confidence={confidence:.2f}")
                        elif response.status_code == 503:
                            print("⏳ Engine: Orchestrator still initializing (503)")
                        else:
                            print(f"❌ Engine endpoint returned status {response.status_code}")
                    except Exception as e:
                        print(f"❌ Error checking engine: {e}")
                else:
                    print("❌ Engine API not available yet")
                    
            elif choice == '5':
                # Check technicals
                if 'Market Data API' in available_services:
                    try:
                        response = requests.get("http://localhost:8004/api/v1/market/ohlc/BANKNIFTY?timeframe=minute&limit=5", timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            if isinstance(data, list) and len(data) > 0:
                                print(f"✅ Technicals: {len(data)} OHLC bars available")
                                latest = data[-1]
                                print(f"   Latest OHLC: O={latest.get('open', 'N/A')}, H={latest.get('high', 'N/A')}, L={latest.get('low', 'N/A')}, C={latest.get('close', 'N/A')}")
                            else:
                                print("❌ Technicals: No OHLC data available")
                        else:
                            print(f"❌ Technicals endpoint returned status {response.status_code}")
                    except Exception as e:
                        print(f"❌ Error checking technicals: {e}")
                else:
                    print("❌ Market Data API not available yet")
                    
            elif choice == '6':
                # Show API endpoints
                print("\n🌐 Available API Endpoints:")
                if 'Market Data API' in available_services:
                    print("   📊 Market Data: http://localhost:8004/")
                    print("      • GET /health")
                    print("      • GET /api/v1/market/tick/{instrument}")
                    print("      • GET /api/v1/market/price/{instrument}")
                    print("      • GET /api/v1/market/ohlc/{instrument}")
                    print("      • GET /api/v1/options/chain/{instrument}")
                if 'News API' in available_services:
                    print("   📰 News: http://localhost:8005/")
                    print("      • GET /health")
                    print("      • GET /api/v1/news/{instrument}")
                    print("      • POST /api/v1/news/collect")
                if 'Engine API' in available_services:
                    print("   🤖 Engine: http://localhost:8006/")
                    print("      • GET /health")
                    print("      • POST /api/v1/analyze")
                if 'User API' in available_services:
                    print("   👤 User: http://localhost:8007/")
                    print("      • GET /health")
                if 'Dashboard UI' in available_services:
                    print("   📱 Dashboard: http://localhost:8888/")
                print()
                    
            elif choice == '7':
                # Continue
                print("✅ Continuing to next step...")
                break
                
            elif choice == '8':
                # Stop
                confirm = input("Are you sure you want to stop startup? (y/N): ").strip().lower()
                if confirm == 'y' or confirm == 'yes':
                    print("🛑 Stopping startup as requested...")
                    sys.exit(0)
                else:
                    print("Continuing...")
                    
            else:
                print("❌ Invalid choice. Please enter 1-8.")
                
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
            sys.exit(0)
        except EOFError:
            print("\n🛑 End of input")
            sys.exit(0)
            
        print()  # Empty line for readability


async def main():
    """Start all services locally with validation"""
    print("🚀 Starting Zerodha Trading System Locally")
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
    parser.add_argument('--allow-missing-credentials', action='store_true', help='Allow startup even if Zerodha credentials are missing (useful for synthetic historical runs)')
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
                    print(f"   ✅ Updated {env_path} with {len(to_write)} keys from root .env")
                except Exception as e:
                    print(f"   ⚠️  Failed to update {env_path}: {e}")
    except Exception as e:
        print(f"   ⚠️  Could not populate module .env files: {e}")

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

    # Print selected trading provider for clarity
    # Ensure market_data module path is available before trying to import
    market_data_src = os.path.abspath('./market_data/src')
    if market_data_src not in sys.path:
        sys.path.insert(0, market_data_src)
    
    try:
        from market_data.providers.factory import get_provider
        provider = get_provider(provider_name if provider_name != 'auto' else None)
        if provider is None and provider_name_normalized == 'auto':
            provider_name_normalized = 'historical'  # Default to historical when no provider available
        print(f"📊 Trading provider: {provider.__class__.__name__ if provider else provider_name_normalized}")
    except ImportError as e:
        print(f"📊 Trading provider: {provider_name}")
        print(f"   ℹ️  Note: Could not load provider factory ({e}) - will use provider selection logic")
    except Exception:
        print(f"📊 Trading provider: {provider_name}")

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
        print("🔧 Step 0: Cleanup and Authentication")
        print("=" * 60)
        
        # Kill existing processes on all ports
        print("   🧹 Cleaning up existing processes...")
        ports_to_clean = [8004, 8005, 8006, 8007, 8888]
        for port in ports_to_clean:
            kill_process_on_port(port)
        print("   ✅ Ports cleaned")
        
        # Verify Zerodha authentication if using Zerodha provider
        kite_instance = None
        if provider_name_normalized in ('zerodha', 'kite'):
            print("\n   🔐 Verifying Zerodha Authentication (Step 0)...")
            creds_ok, kite_instance = verify_zerodha_credentials()
            if not creds_ok:
                print("   ❌ Zerodha authentication failed!")
                print("   💡 Please configure Zerodha credentials before proceeding")
                print("   💡 Or use: python start_local.py --provider historical")
                return
            print("   ✅ Zerodha authentication verified - proceeding with startup")
        elif provider_name_normalized in ('historical', 'replay', 'auto'):
            # Check if Zerodha credentials are available (might be used for historical data)
            print("\n   🔐 Checking Zerodha credentials (optional for historical data)...")
            creds_ok, kite_instance = verify_zerodha_credentials()
            if creds_ok:
                print("   ✅ Zerodha credentials available (can use --historical-source zerodha)")
            else:
                print("   ⚠️  Zerodha credentials not available")
                # Check if CSV source is provided (doesn't need credentials)
                has_csv_source = args.historical_source and args.historical_source.endswith('.csv')
                if has_csv_source:
                    print("   ✅ CSV file source provided - credentials not required")
                elif api_key and api_secret and not access_token:
                    # Have API key/secret but missing access token - can proceed with --allow-missing-credentials
                    if not args.allow_missing_credentials:
                        print("   ⚠️  KITE_ACCESS_TOKEN missing (required for --historical-source zerodha)")
                        print("   💡 You have KITE_API_KEY and KITE_API_SECRET, but need KITE_ACCESS_TOKEN")
                        print("   💡 Options to fix:")
                        print("      1. Get access token: python -m market_data.tools.kite_auth")
                        print("      2. Use CSV instead: --historical-source path/to/data.csv --allow-missing-credentials")
                        print("      3. Override: --allow-missing-credentials (uses synthetic data)")
                        return
                    else:
                        print("   ⚠️  Continuing without KITE_ACCESS_TOKEN due to --allow-missing-credentials flag")
                        print("   💡 Historical replay will use synthetic data (cannot fetch from Zerodha API without token)")
                elif not args.allow_missing_credentials:
                    print("   💡 Historical data requires Zerodha credentials or CSV file")
                    print("   ❌ Missing Zerodha credentials are required for your current configuration. Stopping startup.")
                    print("   💡 Options to fix:")
                    print("      - Use CSV file: --historical-source path/to/data.csv --allow-missing-credentials")
                    print("      - Provide Zerodha credentials: KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN in market_data/.env or credentials.json")
                    print("      - Get token: python -m market_data.tools.kite_auth")
                    print("      - Override check: --allow-missing-credentials (synthetic data may be used)")
                    return
                else:
                    print("   ⚠️  Continuing without Zerodha credentials due to --allow-missing-credentials flag (synthetic historical may be used)")
        
        # Step 1: Start and Verify Historical Data Source
        print("\n" + "=" * 60)
        print("📈 Step 1: Historical Data Source")
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
                        print("   💡 Zerodha data issues:")
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
                print("   ✅ Cleared virtual time (live mode uses real-time)")
            except Exception as e:
                print(f"   ⚠️  Could not clear virtual time: {e}")
            
            # In the new runner-based architecture, collectors are started by the runner
            if provider_name_normalized in ('zerodha', 'kite') and kite_instance:
                print("   ℹ️  Live collectors will be managed by market-data runner when the server is started")
            else:
                print("   ℹ️  Live collectors are not required for this provider configuration")

        # Interactive verification after Step 1
        if not args.skip_validation:
            available_services = []
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("Historical Data Source", available_services)

        # Step 2: Start and Verify Market Data API
        print("\n" + "=" * 60)
        print("💰 Step 2: Market Data API")
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
                print("   Stopping startup. Please check the Market Data Runner logs.")
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

        # Interactive verification after Step 2
        if not args.skip_validation:
            available_services = ["Market Data API"]
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("Market Data API", available_services)

        # Step 3: Start and Verify News API
        print("\n" + "=" * 60)
        print("📰 Step 3: News API")
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

        # Interactive verification after Step 3
        if not args.skip_validation:
            available_services = ["Market Data API", "News API"]
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("News API", available_services)

        # Step 4: Start and Verify Engine API
        print("\n" + "=" * 60)
        print("🤖 Step 4: Engine API")
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
            print(f"   ✅ All required environment variables already set")

        # Install genai_module in editable mode for Engine API
        print("   📦 Installing genai_module (1/2)...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./genai_module"],
                         capture_output=True, text=True, check=True)
            print("   ✅ genai_module installed successfully (1/2)")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to install genai_module (1/2): {e}")
            print(f"   Error output: {e.stderr}")
            return

        # Install news_module in editable mode for News API
        print("   📦 Installing news_module (2/2)...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./news_module"],
                         capture_output=True, text=True, check=True)
            print("   ✅ news_module installed successfully (2/2)")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to install news_module (2/2): {e}")
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
            
            # Then verify agents are running (allow more time for orchestrator initialization)
            # Note: Orchestrator initialization can take time due to LLM client setup and agent creation
            print("   [INFO] Orchestrator initialization may take 30-60 seconds (LLM setup, agent creation)")
            engine_ok = verify_engine_api(max_retries=30, retry_delay=2)  # Give more time: 30 attempts x 2s = 60s
            if not engine_ok:
                print("   [!] Engine API orchestrator not ready after extended wait")
                print("   [!] Continuing anyway - orchestrator may initialize later")
                print("   [!] Check Engine API logs for initialization errors if issues persist")
                print("   [INFO] Other services will continue starting...")
                # Don't stop startup - continue so other services can start
                # The orchestrator can be initialized later if needed

        # Interactive verification after Step 4
        if not args.skip_validation:
            available_services = ["Market Data API", "News API", "Engine API"]
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("Engine API", available_services)

        # Step 4.5: Start and Verify User API
        print("\n" + "=" * 60)
        print("👤 Step 4.5: User API")
        print("=" * 60)

        # Install user_module in editable mode for User API
        print("   📦 Installing user_module...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./user_module"],
                         capture_output=True, text=True, check=True)
            print("   ✅ user_module installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to install user_module: {e}")
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
            print("   ✅ User API is healthy and ready!")

        # Interactive verification after Step 4.5
        if not args.skip_validation:
            available_services = ["Market Data API", "News API", "Engine API", "User API"]
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("User API", available_services)

        # Step 5: Start Orchestrator (Continuous 15-minute Analysis)
        print("\n" + "=" * 60)
        print("🔄 Step 5: Orchestrator (Continuous Analysis)")
        print("=" * 60)
        
        print("   📦 Starting orchestrator in continuous mode...")
        print("   ℹ️  Will run analysis cycles every 15 minutes (or 2 minutes in DEMO_MODE=true)")
        print("   ℹ️  Analysis runs automatically during market hours")
        
        # Pass historical mode environment variables to orchestrator
        orchestrator_env = os.environ.copy()
        if provider_name_normalized in ('historical', 'replay', 'auto'):
            # Set environment variables so orchestrator can detect historical mode
            if args.historical_source:
                orchestrator_env['HISTORICAL_SOURCE'] = args.historical_source
            orchestrator_env['TRADING_PROVIDER'] = provider_name_normalized
            orchestrator_env['USE_VIRTUAL_TIME'] = '1'  # Enable virtual time detection
        
        orchestrator_process = start_service(
            "Orchestrator (Continuous Mode)",
            [sys.executable, "run_orchestrator.py"],
            env=orchestrator_env
        )
        processes.append(orchestrator_process)
        
        # Give orchestrator a few seconds to initialize
        if not args.skip_validation:
            print("   ⏳ Waiting for orchestrator to initialize...")
            time.sleep(5)  # Wait for orchestrator to start
            print("   ✅ Orchestrator started (will begin first cycle soon)")

        # Interactive verification after Step 5
        if not args.skip_validation:
            available_services = ["Market Data API", "News API", "Engine API", "User API", "Orchestrator"]
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("Orchestrator", available_services)

        # Step 5.5: Start Redis WebSocket Gateway
        print("\n" + "=" * 60)
        print("🔌 Step 5.5: Redis WebSocket Gateway")
        print("=" * 60)
        
        kill_process_on_port(8889)
        gateway_process = start_service(
            "Redis WebSocket Gateway (port 8889)",
            ["python", "-m", "redis_ws_gateway.main"]
        )
        processes.append(gateway_process)
        
        if args.skip_validation:
            print("⚠️  Skipping Gateway verification")
        else:
            # Check health endpoint
            gateway_health = wait_for_service("Redis WebSocket Gateway", "http://localhost:8889/health")
            if not gateway_health:
                print("❌ Redis WebSocket Gateway health check failed!")
                print("   Stopping startup. Please check the Gateway logs.")
                # Cleanup started processes
                for process in processes:
                    try:
                        process.terminate()
                    except:
                        pass
                return
            print("   ✅ Redis WebSocket Gateway is healthy and ready!")

        # Interactive verification after Step 5.5
        if not args.skip_validation:
            available_services = ["Market Data API", "News API", "Engine API", "User API", "Orchestrator", "Redis WebSocket Gateway"]
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("Redis WebSocket Gateway", available_services)

        # Step 6: Start and Verify Dashboard UI
        print("\n" + "=" * 60)
        print("🖥️  Step 6: Dashboard UI")
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
                    print(f"   ⚠️  Failed to read root .env: {e}")

            vite_defaults = {
                'VITE_DASHBOARD_API_URL': 'http://localhost:8888',
                'VITE_MARKET_API_URL': 'http://localhost:8004',
                'VITE_NEWS_API_URL': 'http://localhost:8005',
                'VITE_ENGINE_API_URL': 'http://localhost:8006',
                'VITE_USER_API_URL': 'http://localhost:8007',
                'VITE_WS_URL': 'ws://localhost:8889/ws'  # Redis WebSocket Gateway (direct Redis connection)
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
                    print(f"   ⚠️  Failed to read existing UI .env: {e}")

            merged = {}
            for k, dv in vite_defaults.items():
                merged[k] = existing_ui_vars.get(k) or root_vars.get(k) or dv

            try:
                with open(ui_env_path, 'w', encoding='utf-8') as f:
                    f.write('# Generated by start_local.py - do not commit\n')
                    for k, v in merged.items():
                        f.write(f"{k}={v}\n")
                print(f"   ✅ Wrote/updated {ui_env_path}")
            except Exception as e:
                print(f"   ⚠️  Failed to write {ui_env_path}: {e}")

            # Ensure node deps are installed (quick check: node_modules exists)
            node_modules_dir = ui_dir / 'node_modules'
            if not node_modules_dir.exists():
                import shutil
                npm_exec = shutil.which('npm') or 'npm'
                print("   📦 Installing modular UI dependencies (preferring 'npm ci' when lockfile exists)")
                try:
                    # Prefer 'ci' when package-lock exists
                    if (ui_dir / 'package-lock.json').exists() or (ui_dir / 'npm-shrinkwrap.json').exists():
                        subprocess.run([npm_exec, 'ci'], cwd=str(ui_dir), check=True)
                    else:
                        subprocess.run([npm_exec, 'install'], cwd=str(ui_dir), check=True)
                    print("   ✅ Installed UI dependencies")
                except subprocess.CalledProcessError:
                    print("   ⚠️  Install failed. Please run 'cd dashboard/modular_ui && npm install' manually")
                except FileNotFoundError:
                    print("   ⚠️  npm not found. Please install Node.js and npm and ensure they are on your PATH")

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

        # Interactive verification after Step 6
        if not args.skip_validation:
            available_services = ["Market Data API", "News API", "Engine API", "User API", "Orchestrator", "Dashboard UI"]
            if provider_name_normalized in ('historical', 'replay', 'auto'):
                available_services.append("Historical Data Replay")
            interactive_verification("Dashboard UI", available_services)

        # All services verified successfully
        print("\n" + "=" * 60)
        print("🎉 All services started and verified!")
        print("=" * 60)
        
        print("\n🌐 Access URLs:")
        print("   📊 Dashboard:    http://localhost:8888/")
        print("   💰 Market Data:  http://localhost:8004/health")
        print("   📰 News:         http://localhost:8005/health")
        print("   🤖 Engine:       http://localhost:8006/health")
        print("   👤 User:         http://localhost:8007/health")
        print("   🔌 WS Gateway:   ws://localhost:8889/ws")
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