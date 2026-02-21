#!/usr/bin/env python3
"""Minimal Kite connectivity check using official KiteConnect flow.

Usage:
  python -m market_data.tools.kite_connectivity_check
"""

from __future__ import annotations

import json
import socket
import ssl
from pathlib import Path
from typing import Tuple

from kiteconnect import KiteConnect


def _load_creds() -> Tuple[str, str]:
    path = Path("credentials.json")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    api_key = str(payload.get("api_key") or "")
    token = str(payload.get("access_token") or (payload.get("data") or {}).get("access_token") or "")
    if not api_key or not token:
        raise RuntimeError("credentials.json missing api_key/access_token")
    return api_key, token


def _check_tcp_tls(host: str = "api.kite.trade", port: int = 443) -> None:
    with socket.create_connection((host, port), timeout=8):
        pass
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=8) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            print(f"tls: OK ({ssock.version()})")


def main() -> int:
    print("kite-connectivity-check: start")
    try:
        _check_tcp_tls()
        print("tcp: OK")
    except Exception as exc:
        print(f"tcp/tls: FAIL: {type(exc).__name__}: {exc}")
        return 2

    api_key, access_token = _load_creds()
    kite = KiteConnect(api_key=api_key, timeout=10)
    kite.set_access_token(access_token)

    checks = [
        ("profile", lambda: kite.profile()),
        ("instruments_nfo", lambda: kite.instruments("NFO")),
        (
            "historical_data",
            lambda: kite.historical_data(
                instrument_token=13235458,
                from_date="2026-02-13 09:15:00",
                to_date="2026-02-13 09:20:00",
                interval="minute",
                continuous=True,
                oi=True,
            ),
        ),
    ]

    failed = False
    for name, fn in checks:
        try:
            out = fn()
            size = len(out) if isinstance(out, list) else 1
            print(f"{name}: OK (size={size})")
        except Exception as exc:
            failed = True
            print(f"{name}: FAIL: {type(exc).__name__}: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

