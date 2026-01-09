#!/usr/bin/env python3
"""Market-data runner (supervisor) that spawns market-data server, collectors, and historical replayer as separate processes.

Usage examples:
  python -m market_data.runner --mode live --start-collectors
  python -m market_data.runner --mode historical --historical-source zerodha --historical-from 2026-01-07
"""
import argparse
import os
import subprocess
import sys
import time
import requests

PYTHON = sys.executable


def _sanitize_for_console(s: str) -> str:
    """Make string safe for consoles that cannot handle Unicode (replace non-ascii)."""
    try:
        return s.encode('ascii', 'replace').decode('ascii')
    except Exception:
        return ''.join((c if ord(c) < 128 else '?') for c in s)


def start_process(name, cmd, env=None):
    # Use ASCII-safe output for Windows compatibility with graceful fallback
    try:
        print(_sanitize_for_console(f"   [START] Starting {name} -> {cmd}"))
    except Exception:
        # Final fallback - minimal ASCII output
        try:
            print(f"   [START] Starting {name}")
        except Exception:
            pass
    if env is None:
        env = os.environ.copy()
    # Ensure module paths are set
    pythonpath = env.get('PYTHONPATH', '')
    to_add = ['./market_data/src']
    for p in to_add:
        if p not in pythonpath:
            if pythonpath:
                pythonpath += os.pathsep
            pythonpath += p
    env['PYTHONPATH'] = pythonpath

    # If cmd is a list, call it directly
    proc = subprocess.Popen(cmd, env=env)
    time.sleep(1)
    return proc


def wait_for_http(url, timeout=30, retry_delay=1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(retry_delay)
    return False


def wait_for_historical_ready(redis_client, timeout=60, poll_interval=1):
    """Poll Redis for the historical readiness key set by the historical runner."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if redis_client.get('system:historical:data_ready'):
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False


def check_zerodha_credentials(prompt_login: bool = False, prompt_login_timeout: int = 300):
    """Check if Zerodha credentials or a valid token are available.

    If `prompt_login` is True and credentials are missing/invalid, this function
    will try to run an interactive login using `KiteAuthService.trigger_interactive_login`.

    Returns (True, None) if credentials are valid, otherwise (False, message).
    """
    try:
        from market_data.tools.kite_auth_service import KiteAuthService
        svc = KiteAuthService()
        creds = svc.load_credentials()
        if creds and svc.is_token_valid(creds):
            return True, None

        # Also check environment variables directly
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        if api_key and access_token:
            test_creds = {'api_key': api_key, 'data': {'access_token': access_token}}
            if svc.is_token_valid(test_creds):
                return True, None

        # If prompt_login requested, attempt interactive login
        if prompt_login:
            try:
                success = svc.trigger_interactive_login(timeout=prompt_login_timeout)
                if success:
                    # Re-evaluate credentials
                    creds = svc.load_credentials()
                    if creds and svc.is_token_valid(creds):
                        return True, None
            except Exception as e:
                return False, f'Interactive login failed: {e}'

        # Not valid
        return False, 'No valid credentials found in credentials.json or environment'
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['live', 'historical'], default='live')
    parser.add_argument('--start-collectors', action='store_true')
    parser.add_argument('--prompt-login', action='store_true', help='If credentials missing, attempt interactive login (useful for Dev machines)')
    parser.add_argument('--historical-source', type=str, default=None)
    parser.add_argument('--historical-speed', type=float, default=1.0)
    parser.add_argument('--historical-from', type=str, default=None)
    parser.add_argument('--historical-ticks', action='store_true')
    parser.add_argument('--no-server', action='store_true', help='Do not start API server (useful for testing)')
    args = parser.parse_args()

    procs = []

    try:
        # Start the market-data API server (always)
        if not args.no_server:
            server_cmd = [PYTHON, '-m', 'market_data.api_service']
            server_proc = start_process('Market Data API', server_cmd)
            procs.append(('Market Data API', server_proc))

            # Wait for health
            ok = wait_for_http('http://127.0.0.1:8004/health', timeout=20)
            if not ok:
                print('[ERROR] Market Data API failed to become healthy in time')
                raise SystemExit(1)
            print(_sanitize_for_console('   [OK] Market Data API healthy'))

        if args.mode == 'live':
            if args.start_collectors:
                # Before starting collectors, validate Zerodha credentials unless using mock provider
                use_mock = os.getenv('USE_MOCK_KITE', '0') in ('1', 'true', 'yes')
                ok, msg = check_zerodha_credentials()

                # If not ok and prompt-login requested, try interactive login
                if not ok and args.prompt_login and not use_mock:
                    print('[INFO] Prompt-login requested; attempting interactive login...')
                    try:
                        from market_data.tools.kite_auth_service import KiteAuthService
                        svc = KiteAuthService()
                        success = svc.trigger_interactive_login(timeout=300)
                        if success:
                            print(_sanitize_for_console('   [OK] Interactive login succeeded; re-checking credentials...'))
                            ok, msg = check_zerodha_credentials()
                        else:
                            print('[WARN] Interactive login did not complete or failed')
                    except Exception as e:
                        print(f'[WARN] Interactive login failed: {e}')

                if not ok and not use_mock:
                    print('[ERROR] Cannot start collectors: Zerodha credentials not valid or missing')
                    print('   💡 Fix options:')
                    print('      - Ensure KITE_API_KEY and KITE_ACCESS_TOKEN are set in environment')
                    print('      - Run: python -m market_data.tools.kite_auth to generate credentials interactively')
                    print('      - Or set USE_MOCK_KITE=1 to use the mock provider for testing')
                    if msg:
                        print(f'[INFO] Details: {msg}')
                    raise SystemExit(1)

                ltp_cmd = [PYTHON, '-m', 'market_data.collectors.ltp_collector']
                depth_cmd = [PYTHON, '-m', 'market_data.collectors.depth_collector']
                ltp_proc = start_process('LTP Collector', ltp_cmd)
                depth_proc = start_process('Depth Collector', depth_cmd)
                procs.extend([('LTP Collector', ltp_proc), ('Depth Collector', depth_proc)])

                # Wait a little for collectors to seed data into Redis
                print('   [*] Waiting briefly for collectors to seed data (5s)...')
                time.sleep(5)

        elif args.mode == 'historical':
            # Start historical runner as a separate process using the market_data module
            env = os.environ.copy()
            if args.historical_source:
                env['HISTORICAL_SOURCE'] = args.historical_source
            env['HISTORICAL_SPEED'] = str(args.historical_speed)
            if args.historical_from:
                env['HISTORICAL_FROM'] = args.historical_from
            if args.historical_ticks:
                env['HISTORICAL_TICKS'] = '1'

            # Use market_data module to run historical replayer
            hist_cmd = [PYTHON, '-m', 'market_data.runner_historical']
            hist_proc = start_process('Historical Replay', hist_cmd, env=env)
            procs.append(('Historical Replay', hist_proc))

            print('   [*] Waiting for historical data to appear (polling Redis + API)...')
            # Prefer explicit Redis readiness key set by the historical runner
            try:
                import redis
                redis_host = os.getenv('REDIS_HOST', 'localhost')
                redis_port = int(os.getenv('REDIS_PORT', '6379'))
                redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

                # Prefer explicit Redis readiness key set by the historical runner
                if wait_for_historical_ready(redis_client, timeout=60, poll_interval=1):
                    print(_sanitize_for_console('   [OK] Historical data ready (Redis key set)'))
                else:
                    # Fallback to API tick endpoint
                    if wait_for_http('http://127.0.0.1:8004/api/v1/market/tick/BANKNIFTY', timeout=60):
                        print(_sanitize_for_console('   [OK] Historical data available via Market Data API'))
                    else:
                        print('[WARN] Historical data not found within timeout')
            except Exception:
                # If Redis/requests not available, fallback to HTTP check
                ok = wait_for_http('http://127.0.0.1:8004/api/v1/market/tick/BANKNIFTY', timeout=60)
                if not ok:
                    print('[WARN] Historical data not found at Market Data API within timeout')
                else:
                    print('   ✅ Historical data available via Market Data API')

        # Keep supervisor running until Ctrl+C
        print('\nSupervisor running. Press Ctrl+C to stop all spawned processes.')
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print('\n🛑 Stopping supervised processes...')
        for name, proc in procs:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(_sanitize_for_console(f'   [OK] Stopped {name}'))
            except Exception:
                try:
                    proc.kill()
                    print(_sanitize_for_console(f'   [OK] Killed {name}'))
                except Exception:
                    pass
        print(_sanitize_for_console('[OK] Supervisor exited'))


if __name__ == '__main__':
    main()
