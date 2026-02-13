"""Unified runtime helpers for market_data.

Provides:
- process helpers used by runner
- mode-aware historical replay runner
- credential resolution for Zerodha integrations
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from kiteconnect import KiteConnect

PYTHON = sys.executable


def _sanitize_for_console(s: str) -> str:
    """Make string safe for consoles that cannot handle Unicode (replace non-ascii)."""
    try:
        return s.encode("ascii", "replace").decode("ascii")
    except Exception:
        return "".join((c if ord(c) < 128 else "?" for c in s))


def start_process(name: str, cmd: list[str], env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None) -> subprocess.Popen:
    """Start a subprocess with a normalized PYTHONPATH and optional env."""
    try:
        print(_sanitize_for_console(f"   [START] Starting {name} -> {cmd}"))
    except Exception:
        try:
            print(f"   [START] Starting {name}")
        except Exception:
            pass

    if env is None:
        env = os.environ.copy()

    pythonpath = env.get("PYTHONPATH", "")
    to_add = ["./market_data/src"]
    for p in to_add:
        if p not in pythonpath:
            pythonpath = f"{pythonpath}{os.pathsep}{p}" if pythonpath else p
    env["PYTHONPATH"] = pythonpath

    proc = subprocess.Popen(cmd, env=env, cwd=cwd or os.getcwd())
    time.sleep(1)
    return proc


def wait_for_http(url: str, timeout: int = 30, retry_delay: int = 1) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            import requests

            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(retry_delay)
    return False


def wait_for_historical_ready(redis_client, timeout: int = 60, poll_interval: int = 1) -> bool:
    """Poll Redis for the historical readiness key set by the historical runner."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if redis_client.get("system:historical:data_ready"):
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False


def check_zerodha_credentials(prompt_login: bool = False, prompt_login_timeout: int = 300) -> Tuple[bool, Optional[str]]:
    """Check if Zerodha credentials or a valid token are available.

    If `prompt_login` is True and credentials are missing/invalid, this function
    will try to run an interactive login using `AuthStartup.trigger_interactive_login`.

    Returns (True, None) if credentials are valid, otherwise (False, message).
    """
    try:
        # Try new centralized auth startup module first
        try:
            from market_data.tools.auth_startup import AuthStartup

            auth = AuthStartup()
            success, message = auth.startup_check()
            if success:
                return True, None
            if prompt_login:
                if auth.trigger_interactive_login(timeout=prompt_login_timeout):
                    return True, None
            return False, message
        except ImportError:
            pass  # Fall back to legacy approach

        # Legacy fallback: use KiteAuthService
        from market_data.tools.kite_auth_service import KiteAuthService

        svc = KiteAuthService()
        creds = svc.load_credentials()
        if creds and svc.is_token_valid(creds):
            return True, None

        api_key = os.getenv("KITE_API_KEY")
        access_token = os.getenv("KITE_ACCESS_TOKEN")
        if api_key and access_token:
            test_creds = {"api_key": api_key, "data": {"access_token": access_token}}
            if svc.is_token_valid(test_creds):
                return True, None

        if prompt_login:
            try:
                success = svc.trigger_interactive_login(timeout=prompt_login_timeout)
                if success:
                    creds = svc.load_credentials()
                    if creds and svc.is_token_valid(creds):
                        return True, None
            except Exception as e:
                return False, f"Interactive login failed: {e}"

        return False, "No valid credentials found in credentials.json or environment"
    except Exception as e:
        return False, str(e)


def build_collector_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build env for collectors, including Kite credentials if available."""
    env = (base_env or os.environ.copy()).copy()
    if not env.get("KITE_API_KEY") or not env.get("KITE_ACCESS_TOKEN"):
        try:
            from market_data.tools.kite_auth_service import KiteAuthService

            auth_svc = KiteAuthService()
            creds = auth_svc.load_credentials()
            if creds:
                env["KITE_API_KEY"] = creds.get("api_key", "")
                env["KITE_ACCESS_TOKEN"] = creds.get("access_token", "") or creds.get("data", {}).get("access_token", "")
        except Exception:
            pass
    return env


@dataclass
class HistoricalReplayConfig:
    source: str
    speed: float
    start_date: Optional[str]
    ticks: bool


def resolve_historical_replay_config(
    historical_source: Optional[str] = None,
    historical_speed: Optional[float] = None,
    historical_from: Optional[str] = None,
    historical_ticks: Optional[bool] = None,
) -> HistoricalReplayConfig:
    """Resolve historical replay config from args and env."""
    source = historical_source or os.getenv("HISTORICAL_SOURCE") or "synthetic"
    speed = float(historical_speed or os.getenv("HISTORICAL_SPEED") or 1.0)
    start_date = historical_from or os.getenv("HISTORICAL_FROM")
    ticks = bool(historical_ticks if historical_ticks is not None else os.getenv("HISTORICAL_TICKS", "0") in ("1", "true", "yes"))
    return HistoricalReplayConfig(source=source, speed=speed, start_date=start_date, ticks=ticks)


def _parse_start_date(start_date: Optional[str]) -> Optional[datetime]:
    if not start_date:
        return None
    try:
        # Interpret YYYY-MM-DD as the trading session start (09:15) by default.
        # This avoids synthetic replays starting at midnight.
        d = datetime.strptime(start_date, "%Y-%m-%d")
        return d.replace(hour=9, minute=15, second=0, microsecond=0)
    except Exception:
        return None


def _resolve_kite_instance_for_historical() -> Optional["KiteConnect"]:
    """Resolve a KiteConnect instance for real Zerodha historical replay.

    Fail-fast policy: when the user asked for real Zerodha data, we should not
    silently fall back to synthetic/mock data.

    Returns:
        KiteConnect instance

    Raises:
        RuntimeError if kiteconnect isn't installed or credentials are missing/invalid.
    """
    try:
        from kiteconnect import KiteConnect
    except Exception as e:
        raise RuntimeError(
            "kiteconnect package is required for Zerodha historical replay. "
            "Install it in the active venv (pip install kiteconnect). "
            f"Import error: {e}"
        )

    # Optional auth precheck (helps produce actionable messages).
    try:
        from market_data.tools.auth_startup import AuthStartup

        auth = AuthStartup()
        success, message = auth.startup_check()
        if not success:
            print(f"   [WARNING] Auth check failed: {message}")
    except Exception:
        pass

    try:
        from market_data.tools.kite_auth_service import KiteAuthService

        auth_service = KiteAuthService()
        creds = auth_service.load_credentials()
    except Exception as e:
        creds = None
        print(f"   [WARNING] Could not load credentials via KiteAuthService: {e}")

    if not creds:
        project_root = Path(__file__).resolve().parents[3]
        cred_path = project_root / "credentials.json"
        if cred_path.exists():
            with open(cred_path, "r", encoding="utf-8-sig") as f:
                creds = json.load(f)

    api_key = (creds or {}).get("api_key") or os.getenv("KITE_API_KEY")
    access_token = (
        (creds or {}).get("access_token")
        or (creds or {}).get("data", {}).get("access_token")
        or os.getenv("KITE_ACCESS_TOKEN")
    )

    if not api_key or not access_token:
        raise RuntimeError(
            "Missing Zerodha credentials for historical replay. "
            "Provide credentials.json or set KITE_API_KEY and KITE_ACCESS_TOKEN. "
            "You can generate credentials using: python -m market_data.tools.kite_auth"
        )

    try:
        kite_instance = KiteConnect(api_key=api_key)
        kite_instance.set_access_token(access_token)
        print("   [OK] KiteConnect instance created for historical data")
        return kite_instance
    except Exception as e:
        raise RuntimeError(f"Failed to create KiteConnect instance: {e}")


async def monitor_for_ticks(redis_client, timeout: int = 60, interval: int = 1) -> bool:
    """Poll Redis for tick keys (mode-aware) and set a readiness key when data appears."""

    # Prefer mode-prefixed patterns (e.g., historical:tick:*:latest) to match
    # the RedisMarketStore key format. Fall back to unprefixed keys for legacy
    # callers or mocked stores.
    prefixed_pattern = None
    try:
        from redis_key_manager import get_redis_pattern

        prefixed_pattern = get_redis_pattern("tick:*:latest")
    except Exception:
        prefixed_pattern = None

    raw_pattern = "tick:*:latest"
    deadline = asyncio.get_event_loop().time() + timeout

    while asyncio.get_event_loop().time() < deadline:
        try:
            keys = []
            if prefixed_pattern:
                keys = redis_client.keys(prefixed_pattern) or []
            if not keys:
                keys = redis_client.keys(raw_pattern) or []

            if keys:
                redis_client.set("system:historical:data_ready", "1")
                return True
        except Exception:
            pass
        await asyncio.sleep(interval)
    return False


async def run_historical_replay(config: HistoricalReplayConfig) -> None:
    """Run historical replay in-process using the resolved config."""
    from market_data.api import build_store, build_historical_replay

    try:
        import redis
    except Exception as e:
        raise RuntimeError(f"Redis dependency missing: {e}")

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

    store = build_store(redis_client=redis_client)

    start_date_obj = _parse_start_date(config.start_date)
    if config.start_date and not start_date_obj:
        print(f"   [WARNING] Invalid date format '{config.start_date}'. Expected YYYY-MM-DD. Using default.")

    kite_instance = None
    if config.source == "zerodha":
        # Fail-fast: do not fall back to synthetic.
        kite_instance = _resolve_kite_instance_for_historical()

    print(
        f"Starting historical replay (source={config.source}, speed={config.speed}, from={config.start_date}, ticks={config.ticks})"
    )

    instrument_symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26JANFUT")
    replay = build_historical_replay(
        store=store,
        data_source=config.source,
        start_date=start_date_obj,
        kite=kite_instance,
        speed=config.speed,
        instrument_symbol=instrument_symbol,
    )

    if not replay:
        print("   [ERROR] Failed to create replay instance")
        return

    replay.start()
    print("Historical replay started")

    try:
        redis_client.set("system:historical:running", "1")
    except Exception:
        pass

    # Fail-fast if no data shows up.
    # For real Zerodha, we expect ticks/ohlc to appear in Redis promptly.
    ready_timeout = int(os.getenv("HISTORICAL_READY_TIMEOUT", "60"))
    monitor_task = asyncio.create_task(monitor_for_ticks(redis_client, timeout=ready_timeout, interval=1))

    try:
        # Wait for readiness or premature replay stop.
        while True:
            if monitor_task.done():
                ok = bool(monitor_task.result())
                if not ok:
                    raise RuntimeError(
                        f"Historical replay did not produce any ticks in Redis within {ready_timeout}s. "
                        "For Zerodha, this usually means invalid credentials/token, market holiday, or wrong instrument."
                    )
                break

            # If the replayer stops before producing data, exit non-zero.
            try:
                if hasattr(replay, "running") and not getattr(replay, "running"):
                    raise RuntimeError("Historical replay stopped before producing any data")
            except Exception:
                pass

            await asyncio.sleep(0.5)

        # Keep process alive while replay runs; if it dies, treat as an error for real sources.
        while True:
            try:
                if hasattr(replay, "running") and not getattr(replay, "running"):
                    raise RuntimeError("Historical replay stopped unexpectedly")
            except Exception:
                pass
            await asyncio.sleep(1)
    finally:
        try:
            replay.stop()
        except Exception:
            pass
        try:
            redis_client.delete("system:historical:running")
            redis_client.delete("system:historical:data_ready")
        except Exception:
            pass
