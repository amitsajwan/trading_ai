#!/usr/bin/env python3
"""Generate a point-in-time runtime snapshot for customer/support use.

Writes: trading_ai/.run/CURRENT_DATA_REFERENCE.md
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.request import urlopen

import redis


API_BASE = "http://127.0.0.1:8004"
DASH_BASE = "http://127.0.0.1:8002"
INSTRUMENT = "BANKNIFTY26MARFUT"
REDIS_HOST = "localhost"
REDIS_PORT = 6380


def get_json(url: str, timeout: int = 8) -> Tuple[int, Dict[str, Any] | list[Any]]:
    with urlopen(url, timeout=timeout) as resp:
        return int(resp.status), json.loads(resp.read().decode("utf-8"))


def main() -> int:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

    lines: list[str] = []
    lines.append("# Current Data Reference")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(
        "Snapshot note: values below are point-in-time and can change quickly during historical replay."
    )
    lines.append("")

    lines.append("## Runtime")
    mode_status, mode_body = get_json(f"{API_BASE}/api/v1/system/mode")
    lines.append(f"- mode: {mode_body.get('mode')} (status={mode_status})")
    lines.append(f"- api_health: {get_json(f'{API_BASE}/health')[0]}")
    lines.append(f"- dashboard_health: {get_json(f'{DASH_BASE}/api/health')[0]}")
    lines.append("")

    lines.append("## Canonical Redis Keys (historical)")
    checks = [
        ("ohlc_1m", f"historical:ohlc_sorted:{INSTRUMENT}:1m", "zcard"),
        ("ohlc_5m", f"historical:ohlc_sorted:{INSTRUMENT}:5m", "zcard"),
        ("ohlc_15m", f"historical:ohlc_sorted:{INSTRUMENT}:15m", "zcard"),
        ("ind_1m", f"historical:indicators:{INSTRUMENT}:1m:*", "scan"),
        ("ind_5m", f"historical:indicators:{INSTRUMENT}:5m:*", "scan"),
        ("ind_15m", f"historical:indicators:{INSTRUMENT}:15m:*", "scan"),
        ("depth_buy", f"historical:depth:{INSTRUMENT}:buy", "exists"),
        ("options_chain", f"historical:options:{INSTRUMENT}:chain", "exists"),
    ]
    for name, key, kind in checks:
        if kind == "zcard":
            lines.append(f"- {name}: key=`{key}`, zcard={int(r.zcard(key) or 0)}")
        elif kind == "scan":
            count = sum(1 for _ in r.scan_iter(match=key))
            lines.append(f"- {name}: pattern=`{key}`, count={count}")
        else:
            lines.append(f"- {name}: key=`{key}`, exists={1 if r.exists(key) else 0}")
    lines.append("")

    lines.append("## Non-canonical keys (expected absent)")
    for pattern in [
        f"indicators:{INSTRUMENT}:1m:*",
        f"indicators:{INSTRUMENT}:5m:*",
        f"indicators:{INSTRUMENT}:15m:*",
        f"historical:ohlc_sorted:{INSTRUMENT}:5min",
        f"historical:ohlc_sorted:{INSTRUMENT}:15min",
    ]:
        if "*" in pattern:
            count = sum(1 for _ in r.scan_iter(match=pattern))
            lines.append(f"- `{pattern}` -> {count}")
        else:
            lines.append(f"- `{pattern}` -> exists={1 if r.exists(pattern) else 0}")
    lines.append("")

    lines.append("## API/Data Checks")
    _, ind_1 = get_json(f"{API_BASE}/api/v1/technical/indicators/{INSTRUMENT}?timeframe=1m")
    _, ind_5 = get_json(f"{API_BASE}/api/v1/technical/indicators/{INSTRUMENT}?timeframe=5min")
    _, ind_15 = get_json(f"{API_BASE}/api/v1/technical/indicators/{INSTRUMENT}?timeframe=15min")
    _, depth = get_json(f"{API_BASE}/api/v1/market/depth/{INSTRUMENT}")
    _, opt = get_json(f"{API_BASE}/api/v1/options/chain/{INSTRUMENT}")
    _, ohlc_5 = get_json(f"{API_BASE}/api/v1/market/ohlc/{INSTRUMENT}?timeframe=5min&limit=5")
    _, ohlc_15 = get_json(f"{API_BASE}/api/v1/market/ohlc/{INSTRUMENT}?timeframe=15min&limit=5")

    i1 = ind_1.get("indicators", {}) if isinstance(ind_1, dict) else {}
    i5 = ind_5.get("indicators", {}) if isinstance(ind_5, dict) else {}
    i15 = ind_15.get("indicators", {}) if isinstance(ind_15, dict) else {}
    lines.append(
        f"- indicators_1m: keys={len(i1)}, bars_available={ind_1.get('bars_available')}, macd={i1.get('macd_value')}"
    )
    lines.append(
        f"- indicators_5m: keys={len(i5)}, bars_available={ind_5.get('bars_available')}, macd={i5.get('macd_value')}"
    )
    lines.append(
        f"- indicators_15m: keys={len(i15)}, bars_available={ind_15.get('bars_available')}, macd={i15.get('macd_value')}"
    )
    lines.append(
        f"- depth: buy_levels={len(depth.get('buy', []))}, sell_levels={len(depth.get('sell', []))}, stale={depth.get('depth_is_stale')}"
    )
    lines.append(f"- options: strikes={len(opt.get('strikes', []))}")
    lines.append(f"- ohlc_5min_api: bars={len(ohlc_5) if isinstance(ohlc_5, list) else 0}")
    lines.append(f"- ohlc_15min_api: bars={len(ohlc_15) if isinstance(ohlc_15, list) else 0}")
    lines.append("")

    lines.append("## Event-driven flow")
    lines.append("- Source (live websocket OR historical replay) emits ticks/candles")
    lines.append("- Writers persist to mode-prefixed Redis keys")
    lines.append("- API/Dashboard read Redis and publish WS/STOMP topics")
    lines.append("- Canonical path: source -> Redis -> API/WS consumers")
    lines.append("")

    out_path = Path("trading_ai/.run/CURRENT_DATA_REFERENCE.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
