"""Monitor script for the Trading Dashboard (http://localhost:8888)

Features:
- Polls /api/system-health (or configurable endpoint) at regular intervals
- Logs failures, recoveries and outage durations to logs/dashboard-monitor.log
- Optional --autorestart flag to try restarting the system when the dashboard is down

Usage:
  python scripts/monitor_dashboard.py [--interval SECONDS] [--endpoint PATH] [--port PORT] [--autorestart] [--instrument BTC]

"""

import argparse
import logging
import os
import sys
import time
import socket
import subprocess
from datetime import datetime, timedelta, timezone

try:
    import httpx
except Exception:
    print("httpx is required for monitor_dashboard.py (pip install httpx)")
    raise

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'dashboard-monitor.log')

logger = logging.getLogger('dashboard_monitor')
logger.setLevel(logging.INFO)
# Prefer RotatingFileHandler when available, fall back to FileHandler
try:
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
except Exception:
    fh = logging.FileHandler(LOG_FILE)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
# also log to stdout
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(formatter)
logger.addHandler(sh)


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def restart_system(python_exe: str, instrument: str):
    # Start the system with start_all.py in a new process
    start_cmd = [python_exe, os.path.join('scripts', 'start_all.py'), instrument, '--auto-kill']
    logger.info(f"Attempting to start system: {' '.join(start_cmd)}")
    try:
        # Use Popen so monitor doesn't block
        subprocess.Popen(start_cmd, cwd=os.getcwd(), stdin=subprocess.DEVNULL)
        logger.info("Restart command issued (non-blocking)")
    except Exception as e:
        logger.exception(f"Failed to start system: {e}")


def check_health(url: str, timeout: float = 2.0) -> (bool, str):
    try:
        r = httpx.get(url, timeout=timeout)
        if r.status_code == 200:
            return True, ''
        return False, f'HTTP {r.status_code}'
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=float, default=5.0, help='Polling interval in seconds')
    parser.add_argument('--endpoint', type=str, default='/api/health', help='Health endpoint path (use fast endpoint by default)')
    parser.add_argument('--port', type=int, default=8888, help='Dashboard port')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Dashboard host')
    # Autorestart enabled by default for resilience; use --no-autorestart to disable (handled below)
    parser.add_argument('--autorestart', action='store_true', default=True, help='Attempt to restart system if down')
    parser.add_argument('--no-autorestart', dest='autorestart', action='store_false', help='Disable autorestart behavior')
    parser.add_argument('--instrument', type=str, default='BTC', help='Instrument to start on restart')
    parser.add_argument('--restart-threshold', type=int, default=6, help='Number of consecutive failures before auto-restart attempt')
    parser.add_argument('--max-restarts', type=int, default=3, help='Max restart attempts within window')
    parser.add_argument('--restart-window-minutes', type=int, default=10, help='Time window in minutes for restart limit')
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}{args.endpoint}"
    python_exe = sys.executable

    logger.info(f"Starting dashboard monitor for {url} (interval={args.interval}s, autorestart={args.autorestart})")

    consecutive_failures = 0
    outage_start = None
    last_status = True
    consecutive_port_closed = 0  # require port closed on 2 consecutive checks before restart

    try:
        while True:
            healthy, message = check_health(url, timeout=min(2.0, args.interval / 2.0))
            now = datetime.now(timezone.utc)
            if healthy:
                if not last_status:
                    # recovered
                    outage_end = now
                    duration = outage_end - outage_start if outage_start else None
                    logger.warning(f"RECOVERED: Dashboard back up at {outage_end.isoformat()} (downtime={duration})")
                    outage_start = None
                    consecutive_failures = 0
                # else everything ok
            else:
                consecutive_failures += 1
                logger.error(f"HEALTH CHECK FAILED ({consecutive_failures}) - {message}")
                if outage_start is None:
                    outage_start = now
                    logger.warning(f"OUTAGE START: {outage_start.isoformat()}")

                if args.autorestart and consecutive_failures >= args.restart_threshold:
                    # double-check port is truly closed before restart AND require it to be closed for 2 consecutive checks
                    port_open = is_port_open(args.host, args.port)
                    if not port_open:
                        consecutive_port_closed += 1
                    else:
                        consecutive_port_closed = 0

                    if consecutive_port_closed >= 2:
                        # enforce restart limits within a time window
                        now_ts = datetime.utcnow()
                        # initialize restart history list if missing
                        if not hasattr(main, 'restart_history'):
                            main.restart_history = []

                        # prune old entries
                        window_start = now_ts - timedelta(minutes=args.restart_window_minutes)
                        main.restart_history = [t for t in main.restart_history if t >= window_start]

                        if len(main.restart_history) >= args.max_restarts:
                            logger.error(f"Restart limit reached ({len(main.restart_history)} in last {args.restart_window_minutes} min). Skipping restart.")
                        else:
                            logger.warning(f"Port {args.port} closed for {consecutive_port_closed} consecutive checks — attempting auto-restart (attempt {len(main.restart_history)+1})")
                            restart_system(python_exe, args.instrument)
                            main.restart_history.append(now_ts)
                            logger.info("Waiting 10s after restart to allow service to come up")
                            time.sleep(10)
                            consecutive_failures = 0
                            consecutive_port_closed = 0
                    else:
                        logger.info(f"Port {args.port} closed count={consecutive_port_closed}; waiting for confirmation before restarting")

            last_status = healthy
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info('Monitor stopped by user')
    except Exception:
        logger.exception('Monitor encountered an unexpected error')


if __name__ == '__main__':
    main()

