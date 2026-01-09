"""Stepwise startup script for manual testing of key steps with early exit on failure.

Usage: python scripts/stepwise_start.py
"""
import time
import requests
from pathlib import Path
import os
import sys

# Import helpers from start_local
sys.path.insert(0, '.')
from start_local import verify_zerodha_credentials, verify_historical_data, start_service, kill_process_on_port


def test_step0():
    print('\n=== Step 0: Environment and credentials ===')
    ok, info = verify_zerodha_credentials()
    if ok:
        print('Step 0: OK')
        return True
    else:
        print('Step 0: FAILED -', info)
        return False


def test_step1():
    print('\n=== Step 1: Historical data source ===')
    # Start market-data runner in historical mode
    kill_process_on_port(8004)
    proc = start_service('Market Data Runner (historical)', ['python', '-m', 'market_data.runner', '--mode', 'historical'], cwd='.')
    time.sleep(2)
    try:
        ok = verify_historical_data()
    except Exception as e:
        print('verify_historical_data raised:', e)
        ok = False
    if ok:
        print('Step 1: OK')
        return True, proc
    else:
        print('Step 1: FAILED')
        return False, proc


def test_step_user_api():
    print('\n=== Step 4.5: User API startup ===')
    kill_process_on_port(8007)
    proc = start_service('User API (port 8007)', ['python', '-m', 'user_module.api_service'])
    # Wait for health
    for i in range(15):
        try:
            r = requests.get('http://localhost:8007/health', timeout=2)
            if r.status_code == 200:
                print('User API healthy')
                return True, proc
        except Exception:
            pass
        time.sleep(1)
    print('User API failed to become healthy')
    return False, proc


def test_step_dashboard():
    print('\n=== Step 5: Dashboard UI startup ===')
    # Decide whether to start modular UI or python dashboard
    ui_dir = Path('dashboard') / 'modular_ui'
    if ui_dir.exists():
        # Start Vite dev server
        kill_process_on_port(8888)
        # Ensure npm exists and dependencies installed
        import shutil, subprocess
        if shutil.which('npm') is None:
            print('npm not found in PATH - cannot start Vite dev server. Please install Node.js and npm.')
            return False, None
        node_modules = ui_dir / 'node_modules'
        if not node_modules.exists():
            import shutil
            if shutil.which('npm') is None:
                print('npm not found in PATH - please install Node.js and npm, then run `cd dashboard/modular_ui && npm install`')
                return False, None

            print('node_modules not present in modular UI - attempting to run `npm install` automatically')
            try:
                npm_exec = shutil.which('npm') or 'npm'
                subprocess.run([npm_exec, 'install'], cwd=str(ui_dir), check=True)
                print('   ✅ Installed UI dependencies via npm install')
            except subprocess.CalledProcessError as e:
                print('   ❌ Automatic `npm install` failed. Please run `cd dashboard/modular_ui && npm install` manually')
                print(f'   Error: {e}')
                return False, None
            except FileNotFoundError as e:
                print('   ❌ npm executable not found during install attempt. Ensure Node.js/npm are installed and on PATH.')
                return False, None

        proc = start_service('Dashboard UI (Vite dev)', ['npm', 'run', 'dev', '--', '--port', '8888'], cwd=str(ui_dir))
        # Wait for base URL
        for i in range(30):
            try:
                r = requests.get('http://localhost:8888/', timeout=2)
                if r.status_code == 200:
                    print('Dashboard UI healthy')
                    return True, proc
            except Exception:
                pass
            time.sleep(1)
        print('Dashboard UI failed to become healthy')
        return False, proc
    else:
        kill_process_on_port(8888)
        proc = start_service('Dashboard (port 8888)', ['python', '-c', 'from dashboard.app import app; import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8888)'])
        for i in range(15):
            try:
                r = requests.get('http://localhost:8888/', timeout=2)
                if r.status_code == 200:
                    print('Dashboard healthy')
                    return True, proc
            except Exception:
                pass
            time.sleep(1)
        print('Dashboard failed to become healthy')
        return False, proc


if __name__ == '__main__':
    # Step 0
    if not test_step0():
        print('Aborting: Step 0 failed')
        sys.exit(1)

    # Step 1
    s1_ok, s1_proc = test_step1()
    if not s1_ok:
        print('Aborting: Step 1 failed')
        if s1_proc:
            try:
                s1_proc.terminate()
            except Exception:
                pass
        sys.exit(1)

    # Step 4.5: start user api
    u_ok, u_proc = test_step_user_api()
    if not u_ok:
        print('Aborting: User API failed to start')
        if s1_proc:
            try:
                s1_proc.terminate()
            except Exception:
                pass
        sys.exit(1)

    # Step 5: dashboard
    d_ok, d_proc = test_step_dashboard()
    if not d_ok:
        print('Aborting: Dashboard failed to start')
        # cleanup
        if u_proc:
            try:
                u_proc.terminate()
            except Exception:
                pass
        if s1_proc:
            try:
                s1_proc.terminate()
            except Exception:
                pass
        sys.exit(1)

    print('\nAll steps passed!')
    print('You may Ctrl+C to stop started processes and cleanup')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nStopping processes...')
        for p in [d_proc, u_proc, s1_proc]:
            try:
                p.terminate()
            except Exception:
                pass
        print('Stopped')
