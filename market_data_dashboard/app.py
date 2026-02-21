#!/usr/bin/env python3
"""
Market Data Dashboard - Standalone Status and Visualization

This provides a web interface for monitoring market data status and visualization,
completely decoupled from engine/trading functionality.
"""

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import requests
import json
import asyncio
from datetime import datetime, timezone, timedelta
import os
import logging
from typing import Dict, Any, List, Optional, Tuple
import time
import redis
import uuid
import threading
import queue
import fnmatch

try:
    import sys
    # Ensure market_data src is importable for shared option math helpers
    MARKET_DATA_SRC = Path(__file__).parent.parent / "market_data" / "src"
    if MARKET_DATA_SRC.exists():
        sys.path.insert(0, str(MARKET_DATA_SRC))
    from market_data.options_calculations import (
        black_scholes_price,
        calculate_option_greeks,
        estimate_risk_free_rate,
    )
except Exception:
    black_scholes_price = None
    calculate_option_greeks = None
    estimate_risk_free_rate = None

try:
    from market_data.env_settings import redis_config as _redis_env_config, resolve_instrument_symbol
except Exception:
    _redis_env_config = None
    resolve_instrument_symbol = None

try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from redis_key_manager import get_redis_key
except Exception:
    def get_redis_key(key: str, *args, **kwargs):
        return key

# Redis configuration for virtual time
if _redis_env_config is not None:
    _r_cfg = _redis_env_config(decode_responses=True)
    REDIS_HOST = _r_cfg.get("host")
    REDIS_PORT = int(_r_cfg.get("port"))
else:
    REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("DEFAULT_REDIS_HOST") or "localhost"
    REDIS_PORT = int(os.getenv("REDIS_PORT") or os.getenv("DEFAULT_REDIS_PORT") or "6379")

_default_instrument_raw = (
    (resolve_instrument_symbol() if resolve_instrument_symbol else "")
    or os.getenv("INSTRUMENT_SYMBOL", "").strip()
    or os.getenv("INSTRUMENT_KEY", "").strip()
)
DEFAULT_INSTRUMENT = "" if _default_instrument_raw == "INSTRUMENT_NOT_SET" else _default_instrument_raw
_PLACEHOLDER_INSTRUMENTS = {"FALLBACK_TEST"}


def _is_placeholder_instrument(value: Any) -> bool:
    return str(value or "").strip().upper() in _PLACEHOLDER_INSTRUMENTS

def get_virtual_time_info():
    """Get virtual time status and current time."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
        enabled = r.get("system:virtual_time:enabled")
        current_time = r.get("system:virtual_time:current")
        
        if enabled and current_time:
            return {
                "enabled": True,
                "current_time": datetime.fromisoformat(current_time.decode('utf-8'))
            }
    except Exception as e:
        logger.warning(f"Could not get virtual time info: {e}")
    
    return {"enabled": False, "current_time": None}


def _parse_timestamp_flexible(value: Any) -> Optional[datetime]:
    """Parse various timestamp representations into a timezone-aware datetime (UTC)."""
    if value is None:
        return None

    # Numeric epoch support (seconds or milliseconds)
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:  # milliseconds
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None

        # Numeric epoch string support
        if raw.isdigit():
            try:
                num = int(raw)
                if num > 1e12:
                    num = num / 1000
                return datetime.fromtimestamp(num, tz=timezone.utc)
            except Exception:
                return None

        normalized = raw
        # "YYYY-MM-DD HH:MM:SS" -> ISO-like
        if " " in normalized and "T" not in normalized:
            normalized = normalized.replace(" ", "T", 1)
        # +0530 -> +05:30 (strict parser compatibility)
        if len(normalized) >= 5 and (normalized[-5] in "+-") and normalized[-3] != ":":
            if normalized[-4:].isdigit():
                normalized = f"{normalized[:-5]}{normalized[-5:-2]}:{normalized[-2:]}"
        normalized = normalized.replace("Z", "+00:00")

        try:
            dt = datetime.fromisoformat(normalized)
        except Exception:
            return None

        if dt.tzinfo is None:
            # Default naive timestamps to IST to match existing market time assumptions
            dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        return dt.astimezone(timezone.utc)

    return None


def _normalize_timestamp_string(value: Any) -> Any:
    """Normalize a timestamp-like value to ISO-8601 UTC string when parseable."""
    dt = _parse_timestamp_flexible(value)
    if not dt:
        return value
    return dt.isoformat().replace("+00:00", "Z")


def _normalize_timestamp_fields(payload: Any) -> Any:
    """Recursively normalize common timestamp/date fields in dict/list payloads."""
    if isinstance(payload, list):
        return [_normalize_timestamp_fields(item) for item in payload]

    if isinstance(payload, dict):
        normalized: Dict[str, Any] = {}
        for key, value in payload.items():
            key_l = str(key).lower()
            if isinstance(value, (dict, list)):
                normalized[key] = _normalize_timestamp_fields(value)
            elif any(
                token in key_l
                for token in ["timestamp", "_at", "date", "time"]
            ):
                normalized[key] = _normalize_timestamp_string(value)
            else:
                normalized[key] = value
        return normalized

    return payload

def filter_data_by_virtual_time(data, time_field="start_at"):
    """Filter data to only include records up to current virtual time."""
    virtual_time_info = get_virtual_time_info()
    
    if not virtual_time_info["enabled"] or not virtual_time_info["current_time"]:
        return data
    
    current_virtual_time = virtual_time_info["current_time"]
    
    # Filter data based on timestamp
    filtered_data = []
    for item in data:
        item_time_str = item.get(time_field) or item.get("timestamp")
        if item_time_str:
            item_time = _parse_timestamp_flexible(item_time_str)
            if item_time is None:
                # If we can't parse the timestamp, include the item
                filtered_data.append(item)
                continue

            compare_time = current_virtual_time
            if compare_time.tzinfo is None:
                compare_time = compare_time.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
            compare_time = compare_time.astimezone(timezone.utc)

            if item_time <= compare_time:
                filtered_data.append(item)
    
    return filtered_data


def _redis_sync_client() -> redis.Redis:
    """Create a short-timeout Redis client for HTTP request handlers."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _timeframe_aliases(timeframe: str) -> List[str]:
    tf = (timeframe or "").strip()
    if not tf:
        return ["1min"]
    out = [tf]
    tfl = tf.lower()
    # Support both "5min" and legacy "5m" style keys.
    if tfl.endswith("min"):
        out.append(tfl.replace("min", "m"))
    elif tfl.endswith("m") and not tfl.endswith("min"):
        # Best effort "5m" -> "5min"
        digits = tfl[:-1]
        if digits.isdigit():
            out.append(f"{digits}min")
    return list(dict.fromkeys(out))


def _ohlc_sorted_keys_to_try(
    instrument: str,
    timeframe: str,
    preferred_mode: Optional[str] = None,
    strict_mode: bool = False,
) -> List[str]:
    tfs = _timeframe_aliases(timeframe)
    prefixes = ["live", "historical", "paper", ""]
    if preferred_mode in {"live", "historical", "paper"}:
        if strict_mode:
            prefixes = [preferred_mode]
        else:
            prefixes = [preferred_mode] + [p for p in prefixes if p != preferred_mode]
    keys: List[str] = []
    for tf in tfs:
        for p in prefixes:
            if p:
                keys.append(f"{p}:ohlc_sorted:{instrument}:{tf}")
            else:
                keys.append(f"ohlc_sorted:{instrument}:{tf}")
    return keys


def _extract_key_mode(redis_key: Optional[str]) -> Optional[str]:
    """Extract mode prefix from Redis key (live/historical/paper)."""
    if not redis_key:
        return None
    if redis_key.startswith("live:"):
        return "live"
    if redis_key.startswith("historical:"):
        return "historical"
    if redis_key.startswith("paper:"):
        return "paper"
    return None


def _parse_ohlc_json_rows(rows: List[str], timeframe: str = "1min") -> List[Dict[str, Any]]:
    bars: List[Dict[str, Any]] = []
    for row in rows:
        if not row:
            continue
        try:
            bars.append(json.loads(row))
        except Exception:
            continue

    return _merge_ohlc_bars_by_timeframe(bars, timeframe)


def _read_ohlc_from_redis(
    instrument: str,
    timeframe: str,
    limit: int = 100,
    order: str = "asc",
    preferred_mode: Optional[str] = None,
    strict_mode: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Read OHLC bars from Redis sorted sets, trying multiple key patterns."""
    r = _redis_sync_client()

    keys = _ohlc_sorted_keys_to_try(
        instrument, timeframe, preferred_mode=preferred_mode, strict_mode=strict_mode
    )
    for key in keys:
        try:
            count = r.zcard(key)
            if not count:
                continue

            lim = max(int(limit or 0), 1)
            if (order or "asc").lower() == "desc":
                rows = r.zrevrange(key, 0, lim - 1)
                bars = _parse_ohlc_json_rows(rows, timeframe=timeframe)
                bars = list(reversed(bars))
                return bars, key

            # asc: return latest lim bars in ascending order
            start = -lim
            end = -1
            rows = r.zrange(key, start, end)
            bars = _parse_ohlc_json_rows(rows, timeframe=timeframe)
            return bars, key
        except Exception:
            continue

    return [], None


def _discover_instruments_from_redis(max_instruments: int = 25) -> List[str]:
    """Best-effort discovery of instruments present in Redis OHLC sorted-set keys.

    Looks for keys like:
      - live:ohlc_sorted:{instrument}:{timeframe}
      - historical:ohlc_sorted:{instrument}:{timeframe}
      - ohlc_sorted:{instrument}:{timeframe}
    """
    try:
        r = _redis_sync_client()
    except Exception:
        return []

    patterns = ["*:ohlc_sorted:*:*", "ohlc_sorted:*:*"]
    instruments: set[str] = set()
    for pat in patterns:
        cursor = 0
        while True:
            try:
                cursor, keys = r.scan(cursor=cursor, match=pat, count=500)
            except Exception:
                break

            for key in keys or []:
                try:
                    parts = str(key).split(":")
                    inst: Optional[str] = None
                    # live:ohlc_sorted:INST:TF
                    if len(parts) >= 4 and parts[1] == "ohlc_sorted":
                        inst = parts[2]
                    # ohlc_sorted:INST:TF
                    elif len(parts) >= 3 and parts[0] == "ohlc_sorted":
                        inst = parts[1]
                    if inst:
                        if _is_placeholder_instrument(inst):
                            continue
                        instruments.add(inst)
                        if len(instruments) >= int(max_instruments or 0):
                            return sorted(instruments)
                except Exception:
                    continue

            if cursor == 0:
                break

    return sorted(instruments)


def _extract_bar_timestamp(bar: Dict[str, Any]) -> Optional[str]:
    return bar.get("start_at") or bar.get("timestamp")


def _merge_ohlc_bars_by_timeframe(data: List[Dict[str, Any]], timeframe: str) -> List[Dict[str, Any]]:
    """Merge OHLC snapshots into one canonical bar per timeframe bucket."""
    if not data:
        return []

    tf = str(timeframe or "1min")

    def _num(v: Any) -> Optional[float]:
        try:
            if v is None or v == "":
                return None
            return float(v)
        except Exception:
            return None

    def _volume(v: Any) -> float:
        try:
            if v is None or v == "":
                return 0.0
            return float(v)
        except Exception:
            return 0.0

    def _parse_dt(raw_ts: Any) -> Optional[datetime]:
        if raw_ts is None:
            return None
        if isinstance(raw_ts, datetime):
            return raw_ts
        if isinstance(raw_ts, (int, float)):
            try:
                ts = float(raw_ts)
                if ts > 1e12:
                    ts = ts / 1000.0
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                return None
        if isinstance(raw_ts, str):
            s = raw_ts.strip()
            if not s:
                return None
            if " " in s and "T" not in s:
                s = s.replace(" ", "T", 1)
            s = s.replace("Z", "+00:00")
            if len(s) >= 5 and (s[-5] in "+-") and s[-3] != ":" and s[-4:].isdigit():
                s = f"{s[:-5]}{s[-5:-2]}:{s[-2:]}"
            try:
                dt = datetime.fromisoformat(s)
            except Exception:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_TZ)
            return dt
        return None

    buckets: Dict[str, Dict[str, Any]] = {}
    first_seen_order: List[str] = []

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue

        ts_raw = _extract_bar_timestamp(item)
        ts = _parse_dt(ts_raw)
        if ts is None:
            synthetic_key = f"__idx_{idx}"
            buckets[synthetic_key] = dict(item)
            first_seen_order.append(synthetic_key)
            continue

        bucket_dt = _bucket_start(ts, tf)
        bucket_key = bucket_dt.isoformat()

        if bucket_key not in buckets:
            row = dict(item)
            row["start_at"] = bucket_key
            buckets[bucket_key] = row
            first_seen_order.append(bucket_key)
            continue

        existing = buckets[bucket_key]

        e_high = _num(existing.get("high"))
        n_high = _num(item.get("high"))
        if e_high is not None and n_high is not None:
            existing["high"] = max(e_high, n_high)
        elif n_high is not None:
            existing["high"] = n_high

        e_low = _num(existing.get("low"))
        n_low = _num(item.get("low"))
        if e_low is not None and n_low is not None:
            existing["low"] = min(e_low, n_low)
        elif n_low is not None:
            existing["low"] = n_low

        # Prefer close/oi from the newest snapshot proxy (higher cumulative volume).
        e_vol = _volume(existing.get("volume"))
        n_vol = _volume(item.get("volume"))
        if n_vol >= e_vol:
            if "close" in item:
                existing["close"] = item.get("close")
            existing["volume"] = item.get("volume")
            if "oi" in item:
                existing["oi"] = item.get("oi")
            if "open_interest" in item:
                existing["open_interest"] = item.get("open_interest")
            if "timestamp" in item:
                existing["timestamp"] = item.get("timestamp")

        existing["start_at"] = bucket_key

    # Always return ascending by bucket timestamp for chart stability.
    parse_cache: Dict[str, datetime] = {}

    def _sort_key(k: str) -> datetime:
        if k in parse_cache:
            return parse_cache[k]
        if k.startswith("__idx_"):
            parse_cache[k] = datetime.min.replace(tzinfo=timezone.utc)
            return parse_cache[k]
        try:
            dt = datetime.fromisoformat(k.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.min.replace(tzinfo=timezone.utc)
        parse_cache[k] = dt
        return dt

    ordered_keys = sorted(first_seen_order, key=_sort_key)
    return [buckets[k] for k in ordered_keys if k in buckets]


def _determine_base_limit(timeframe: str, requested_limit: int) -> int:
    """Choose how many 1-min bars to request when aggregating higher timeframes."""
    tf = timeframe.lower()
    # Rough multiplier based on bar size
    if tf.endswith("min"):
        try:
            minutes = int(tf.replace("min", ""))
        except ValueError:
            minutes = 1
        multiplier = max(minutes, 1)
    elif tf.endswith("h"):
        try:
            hours = int(tf.replace("h", ""))
        except ValueError:
            hours = 1
        multiplier = max(hours * 60, 60)
    elif tf.endswith("d"):
        multiplier = 1440  # full trading day worth of minutes
    else:
        multiplier = 1

    # Ensure we request enough data but cap to avoid abuse
    base_limit = requested_limit if requested_limit and requested_limit > 0 else 100
    return min(max(base_limit * multiplier, base_limit, 300), 2000)


def _bucket_start(ts: datetime, timeframe: str) -> datetime:
    """Floor a timestamp to the start of the requested bucket."""
    tf = timeframe.lower()
    if tf.endswith("min") or (tf.endswith("m") and tf[:-1].isdigit()):
        try:
            minutes = int(tf.replace("min", "").replace("m", ""))
        except ValueError:
            minutes = 1
        minute_bucket = (ts.minute // minutes) * minutes
        return ts.replace(minute=minute_bucket, second=0, microsecond=0)
    if tf.endswith("h"):
        try:
            hours = int(tf.replace("h", ""))
        except ValueError:
            hours = 1
        hour_bucket = (ts.hour // hours) * hours
        return ts.replace(hour=hour_bucket, minute=0, second=0, microsecond=0)
    if tf.endswith("d"):
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(second=0, microsecond=0)


def aggregate_ohlc(data: List[Dict[str, Any]], timeframe: str) -> List[Dict[str, Any]]:
    """Aggregate 1-minute OHLC bars into a higher timeframe."""
    if timeframe == "1min":
        return data

    def _num(v: Any, default: float = 0.0) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    def _oi(v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    buckets: Dict[str, Dict[str, Any]] = {}

    for item in data:
        ts_str: Optional[str] = item.get("start_at") or item.get("timestamp")
        if not ts_str:
            continue

        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            continue

        bucket_start = _bucket_start(ts, timeframe)
        bucket_key = bucket_start.isoformat()

        if bucket_key not in buckets:
            latest_oi = _oi(item.get("oi") if item.get("oi") is not None else item.get("open_interest"))
            buckets[bucket_key] = {
                "instrument": item.get("instrument"),
                "timeframe": timeframe,
                "open": _num(item.get("open", item.get("last_price", 0))),
                "high": _num(item.get("high", item.get("last_price", 0))),
                "low": _num(item.get("low", item.get("last_price", 0))),
                "close": _num(item.get("close", item.get("last_price", 0))),
                "volume": _num(item.get("volume"), 0.0),
                "oi": latest_oi,
                "start_at": bucket_key
            }
        else:
            bucket = buckets[bucket_key]
            bucket["high"] = max(bucket["high"], _num(item.get("high", bucket["high"]), bucket["high"]))
            bucket["low"] = min(bucket["low"], _num(item.get("low", bucket["low"]), bucket["low"]))
            bucket["close"] = _num(item.get("close", bucket["close"]), bucket["close"])
            bucket["volume"] = _num(bucket.get("volume"), 0.0) + _num(item.get("volume"), 0.0)

            next_oi = _oi(item.get("oi") if item.get("oi") is not None else item.get("open_interest"))
            if next_oi is not None:
                bucket["oi"] = next_oi

    # Return buckets sorted by time
    ordered = [buckets[k] for k in sorted(buckets.keys())]
    return ordered


def _has_any_oi(data: List[Dict[str, Any]]) -> bool:
    """Return True when at least one bar carries OI/open_interest."""
    for item in data or []:
        v = item.get("oi")
        if v is None:
            v = item.get("open_interest")
        if v is not None and str(v) != "":
            return True
    return False


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _format_chart_labels(timestamps: List[Any], timeframe: str) -> List[str]:
    """Pre-format chart labels server-side for thin frontend rendering."""
    if not timestamps:
        return []

    market_tz = timezone(timedelta(hours=5, minutes=30))
    parsed_local: List[Optional[datetime]] = []
    valid_ms: List[float] = []

    for value in timestamps:
        dt = _parse_timestamp_flexible(value)
        if not dt:
            parsed_local.append(None)
            continue

        local_dt = dt.astimezone(market_tz)
        parsed_local.append(local_dt)
        valid_ms.append(local_dt.timestamp() * 1000.0)

    if not valid_ms:
        return ["Invalid Date" for _ in timestamps]

    span_ms = max(valid_ms) - min(valid_ms)
    tf = str(timeframe or "").strip().lower()
    include_date = tf == "1d" or span_ms >= 24 * 60 * 60 * 1000
    fmt = "%m-%d %H:%M" if include_date else "%H:%M"

    return [dt.strftime(fmt) if dt else "Invalid Date" for dt in parsed_local]


def _calculate_rsi_series(closes: List[float], period: int = 14) -> List[Optional[float]]:
    if not closes:
        return []
    if period <= 0 or len(closes) < period + 1:
        return [None] * len(closes)

    rsi: List[Optional[float]] = []
    gains = 0.0
    losses = 0.0

    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains += change
        else:
            losses -= change

    avg_gain = gains / period
    avg_loss = losses / period

    rsi.extend([None] * period)

    for i in range(period, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        rs = 100.0 if avg_loss == 0 else (avg_gain / avg_loss)
        rsi.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi


def _calculate_ema_series(values: List[float], period: int) -> List[Optional[float]]:
    if not values:
        return []
    if period <= 0:
        return [None] * len(values)

    ema: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return ema

    sma = sum(values[:period]) / period
    ema[period - 1] = sma
    multiplier = 2.0 / (period + 1)

    for i in range(period, len(values)):
        prev = ema[i - 1]
        if prev is None:
            prev = values[i - 1]
        ema[i] = (values[i] - prev) * multiplier + prev

    return ema


def _calculate_macd_series(
    closes: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    if not closes:
        return [], []

    ema_fast = _calculate_ema_series(closes, fast_period)
    ema_slow = _calculate_ema_series(closes, slow_period)

    macd: List[Optional[float]] = []
    for i in range(len(closes)):
        f = ema_fast[i] if i < len(ema_fast) else None
        s = ema_slow[i] if i < len(ema_slow) else None
        if f is None or s is None:
            macd.append(None)
        else:
            macd.append(float(f - s))

    non_null_macd = [v for v in macd if v is not None]
    signal_raw = _calculate_ema_series(non_null_macd, signal_period)
    aligned_signal: List[Optional[float]] = [None] * len(macd)

    first_macd_idx = next((i for i, v in enumerate(macd) if v is not None), -1)
    if first_macd_idx >= 0:
        for j, val in enumerate(signal_raw):
            if val is None:
                continue
            idx = first_macd_idx + j
            if idx < len(aligned_signal):
                aligned_signal[idx] = val

    return macd, aligned_signal


def _build_chart_payload_from_ohlc(
    instrument: str,
    timeframe: str,
    ohlc_data: List[Dict[str, Any]],
    req_limit: int,
    indicators_bars_needed: int = 120,
) -> Dict[str, Any]:
    if not ohlc_data:
        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "price_chart": {
                "timestamps": [],
                "labels": [],
                "prices": [],
                "volumes_millions": [],
                "oi": [],
                "volume_label": "Volume",
                "volume_axis_title": "Volume",
            },
            "indicators_chart": {
                "timestamps": [],
                "labels": [],
                "rsi": [],
                "macd": [],
                "signal": [],
                "rsi_period": 14,
                "macd_label": "MACD",
                "macd_signal_label": "MACD Signal",
                "has_macd": False,
            },
        }

    price_data = ohlc_data[-req_limit:]
    price_timestamps = [_extract_bar_timestamp(d) for d in price_data]
    price_labels = _format_chart_labels(price_timestamps, timeframe)
    prices = [_safe_float(d.get("close"), 0.0) or 0.0 for d in price_data]
    volumes_raw = [_safe_float(d.get("volume"), 0.0) or 0.0 for d in price_data]
    max_volume = max(volumes_raw) if volumes_raw else 0.0
    if max_volume >= 1_000_000.0:
        volume_scale = 1_000_000.0
        volume_suffix = "M"
    elif max_volume >= 1_000.0:
        volume_scale = 1_000.0
        volume_suffix = "K"
    else:
        volume_scale = 1.0
        volume_suffix = ""
    volumes_scaled = [v / volume_scale for v in volumes_raw]
    volume_label = f"Volume ({volume_suffix})" if volume_suffix else "Volume"
    oi_series = []
    for d in price_data:
        oi_val = d.get("oi") if d.get("oi") is not None else d.get("open_interest")
        oi_series.append(_safe_float(oi_val, None))

    ohlc_for_indicators = ohlc_data[-indicators_bars_needed:]
    closes = [_safe_float(d.get("close"), 0.0) or 0.0 for d in ohlc_for_indicators]
    indicator_timestamps_full = [_extract_bar_timestamp(d) for d in ohlc_for_indicators]

    rsi_period = 14 if len(closes) >= 15 else max(3, len(closes) - 1)
    rsi_values = _calculate_rsi_series(closes, rsi_period)

    if len(closes) >= 26:
        fast, slow, signal = 12, 26, 9
        adaptive = False
    elif len(closes) >= 4:
        fast = max(2, round(len(closes) * 0.35))
        slow = max(3, round(len(closes) * 0.7))
        signal = max(2, round(len(closes) * 0.2))
        adaptive = True
    else:
        fast = slow = signal = 0
        adaptive = False

    if len(closes) >= 4:
        macd_values, signal_values = _calculate_macd_series(closes, fast, slow, signal)
        macd_label = f"MACD ({fast}/{slow}, warm-up)" if adaptive else "MACD"
        macd_signal_label = f"Signal ({signal}, warm-up)" if adaptive else "MACD Signal"
    else:
        macd_values = [None] * len(closes)
        signal_values = [None] * len(closes)
        macd_label = "MACD (warming up)"
        macd_signal_label = "MACD Signal (warming up)"

    chart_points = min(50, len(ohlc_for_indicators))
    start_idx = max(0, len(ohlc_for_indicators) - chart_points)

    indicator_timestamps = indicator_timestamps_full[start_idx:]
    indicator_labels = _format_chart_labels(indicator_timestamps, timeframe)
    chart_rsi = rsi_values[start_idx:]
    chart_macd = macd_values[start_idx:]
    chart_signal = signal_values[start_idx:]
    has_macd = any(v is not None for v in chart_macd)

    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "price_chart": {
            "timestamps": price_timestamps,
            "labels": price_labels,
            "prices": prices,
            "volumes_millions": volumes_scaled,
            "oi": oi_series,
            "volume_label": volume_label,
            "volume_axis_title": volume_label,
        },
        "indicators_chart": {
            "timestamps": indicator_timestamps,
            "labels": indicator_labels,
            "rsi": chart_rsi,
            "macd": chart_macd,
            "signal": chart_signal,
            "rsi_period": rsi_period,
            "macd_label": macd_label,
            "macd_signal_label": macd_signal_label,
            "has_macd": has_macd,
        },
    }

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Market Data Dashboard",
    description="Standalone market data monitoring and visualization",
    version="1.0.0"
)

# Mount static files (optional - create directory if needed)
import os
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates))

# Market Data API configuration
MARKET_DATA_API_URL = os.getenv("MARKET_DATA_API_URL") or (
    f"http://{os.getenv('MARKET_DATA_API_HOST', 'localhost')}:"
    f"{os.getenv('MARKET_DATA_API_PORT', '8004')}"
)

# Lightweight in-memory caches to keep UI responsive when upstream API is slow.
_LAST_GOOD_INDICATORS: Dict[str, Dict[str, Any]] = {}
_LAST_GOOD_DEPTH: Dict[str, Dict[str, Any]] = {}
_LAST_GOOD_OPTIONS: Dict[str, Dict[str, Any]] = {}

PUBLIC_SCHEMA_VERSION = "v1"
PUBLIC_TOPICS: Tuple[str, ...] = ("mode", "tick", "ohlc", "indicators", "depth", "options")
PUBLIC_TIMEFRAMES: Tuple[str, ...] = ("1m", "5m", "15m")
PUBLIC_TIMEFRAME_ALIASES: Dict[str, List[str]] = {
    "1m": ["1m", "1min", "minute"],
    "5m": ["5m", "5min"],
    "15m": ["15m", "15min"],
}


def _get_current_mode_hint(timeout_seconds: float = 1.5) -> Optional[str]:
    """Best-effort mode lookup from upstream API (live/historical/paper)."""
    try:
        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/system/mode",
            timeout=timeout_seconds,
        )
        if response.status_code != 200:
            return None
        payload = response.json()
        mode = str(payload.get("mode") or "").strip().lower()
        if mode in {"live", "historical", "paper"}:
            return mode
    except Exception:
        return None
    return None


def _allow_synthetic_fallback(mode_hint: Optional[str]) -> bool:
    """Disable synthetic market data in live mode when strict mode is enabled."""
    strict_live_real_only = os.getenv("LIVE_STRICT_REAL_ONLY", "1").strip().lower() in {"1", "true", "yes", "on"}
    mode = str(mode_hint or _get_current_mode_hint() or "").strip().lower()
    if strict_live_real_only and mode == "live":
        return False
    return True


IST_TZ = timezone(timedelta(hours=5, minutes=30))


def _reference_price_for_options(instrument: str) -> Optional[float]:
    """Fetch latest price from Redis for synthetic options chain."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        keys = [
            f"ltp:{instrument}",
            f"live:ltp:{instrument}",
            get_redis_key(f"price:{instrument}:latest"),
            get_redis_key(f"price:{instrument.upper()}:latest"),
            f"price:{instrument}:latest",
        ]
        for key in keys:
            if not key:
                continue
            raw = r.get(key)
            if raw is None:
                continue
            try:
                # Structured JSON payload from LTP cache
                if isinstance(raw, str) and raw.startswith("{"):
                    obj = json.loads(raw)
                    cand = obj.get("last_price") or obj.get("close") or obj.get("price")
                    if cand:
                        return float(cand)
                # Fallback numeric
                cand = float(raw)
                return cand
            except Exception:
                continue
    except Exception:
        return None
    return None


def _current_time_for_mode(mode_hint: Optional[str] = None) -> datetime:
    """Return effective time (virtual when available)."""
    try:
        vt = get_virtual_time_info()
        if vt.get("enabled") and vt.get("current_time"):
            ct = vt["current_time"]
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=IST_TZ)
            return ct.astimezone(timezone.utc)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    if mode_hint == "historical":
        return now
    return now


def _next_weekly_expiry_from(now_dt: datetime) -> datetime:
    """Next Thursday 15:30 IST from given time."""
    ist_now = now_dt.astimezone(IST_TZ)
    days_ahead = (3 - ist_now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    expiry = ist_now + timedelta(days=days_ahead)
    expiry = expiry.replace(hour=15, minute=30, second=0, microsecond=0)
    return expiry.astimezone(timezone.utc)


def _build_synthetic_options_chain_black_scholes(
    instrument: str,
    mode_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Generate a synthetic options chain using Black-Scholes for historical/offline mode."""
    if not black_scholes_price:
        return None

    spot = _reference_price_for_options(instrument) or 50000.0
    now_dt = _current_time_for_mode(mode_hint)
    expiry_dt = _next_weekly_expiry_from(now_dt)
    time_to_expiry_years = max((expiry_dt - now_dt).total_seconds(), 1.0) / (365 * 24 * 3600)

    try:
        sigma_default = float(os.getenv("SYNTHETIC_OPTIONS_IV", "0.22"))
    except Exception:
        sigma_default = 0.22
    sigma = max(0.05, min(sigma_default, 1.5))

    try:
        step = int(os.getenv("SYNTHETIC_OPTIONS_STRIKE_STEP", "100"))
    except Exception:
        step = 100

    risk_free = estimate_risk_free_rate() if callable(estimate_risk_free_rate) else 0.06

    center = int(round(spot / step) * step)
    width = 7  # strikes on each side
    strikes: List[Dict[str, Any]] = []
    total_call_oi = 0
    total_put_oi = 0

    for offset in range(-width, width + 1):
        strike_price = center + offset * step
        distance = abs(offset) or 1
        ce_price = black_scholes_price(spot, strike_price, time_to_expiry_years, risk_free, sigma, "call")
        pe_price = black_scholes_price(spot, strike_price, time_to_expiry_years, risk_free, sigma, "put")

        greeks_ce = calculate_option_greeks(spot, strike_price, time_to_expiry_years, risk_free, sigma, "call") if callable(calculate_option_greeks) else {}
        greeks_pe = calculate_option_greeks(spot, strike_price, time_to_expiry_years, risk_free, sigma, "put") if callable(calculate_option_greeks) else {}

        base_oi = max(int(2200 - distance * 160), 150)
        ce_oi = int(base_oi * (0.55 if offset >= 0 else 0.45))
        pe_oi = int(base_oi * (0.55 if offset <= 0 else 0.45))
        total_call_oi += ce_oi
        total_put_oi += pe_oi

        strikes.append({
            "strike": strike_price,
            "ce_ltp": round(ce_price, 2) if ce_price is not None else None,
            "ce_oi": ce_oi,
            "ce_volume": max(int(ce_oi * 0.12), 20),
            "ce_iv": round(sigma * 100, 2),
            "ce_delta": greeks_ce.get("delta"),
            "ce_gamma": greeks_ce.get("gamma"),
            "ce_theta": greeks_ce.get("theta"),
            "ce_vega": greeks_ce.get("vega"),
            "pe_ltp": round(pe_price, 2) if pe_price is not None else None,
            "pe_oi": pe_oi,
            "pe_volume": max(int(pe_oi * 0.12), 20),
            "pe_iv": round(sigma * 100, 2),
            "pe_delta": greeks_pe.get("delta"),
            "pe_gamma": greeks_pe.get("gamma"),
            "pe_theta": greeks_pe.get("theta"),
            "pe_vega": greeks_pe.get("vega"),
        })

    if not strikes:
        return None

    pcr = (total_put_oi / total_call_oi) if total_call_oi > 0 else None
    max_pain = max(strikes, key=lambda s: (s.get("ce_oi", 0) + s.get("pe_oi", 0)))

    return {
        "instrument": instrument,
        "expiry": expiry_dt.date().isoformat(),
        "strikes": strikes,
        "timestamp": now_dt.isoformat().replace("+00:00", "Z"),
        "futures_price": spot,
        "pcr": pcr,
        "max_pain": max_pain.get("strike") if isinstance(max_pain, dict) else None,
        "status": "synthetic",
        "mode_hint": mode_hint or _get_current_mode_hint(),
        "note": "Synthetic chain (Black-Scholes) for historical/offline mode",
    }


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _options_chain_has_liquidity(strikes: Any) -> bool:
    """Return True if any strike has non-zero OI/volume on either side."""
    if not isinstance(strikes, list):
        return False

    def _num(v: Any) -> float:
        try:
            if v is None:
                return 0.0
            return float(v)
        except Exception:
            return 0.0

    for strike in strikes:
        if not isinstance(strike, dict):
            continue
        ce = strike.get("CE") if isinstance(strike.get("CE"), dict) else {}
        pe = strike.get("PE") if isinstance(strike.get("PE"), dict) else {}

        vals = [
            strike.get("ce_oi"),
            strike.get("ce_volume"),
            strike.get("pe_oi"),
            strike.get("pe_volume"),
            ce.get("oi"),
            ce.get("volume"),
            pe.get("oi"),
            pe.get("volume"),
        ]
        if any(_num(v) > 0 for v in vals):
            return True
    return False


def _normalize_options_contract(
    instrument: str,
    payload: Optional[Dict[str, Any]],
    *,
    expiry: Optional[str] = None,
    mode_hint: Optional[str] = None,
    default_status: str = "ok",
) -> Dict[str, Any]:
    """Force a stable options payload shape for API/UI/agents."""
    out: Dict[str, Any] = dict(payload or {})
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    inst = str(out.get("instrument") or instrument or "").strip() or instrument
    resolved_mode = str(out.get("mode_hint") or mode_hint or _get_current_mode_hint() or "unknown").lower()
    source = out.get("source") or resolved_mode

    futures_price = _coerce_float(out.get("futures_price"))
    underlying_price = _coerce_float(out.get("underlying_price"))
    ref_price = _reference_price_for_options(inst)
    if futures_price is None and underlying_price is not None:
        futures_price = underlying_price
    if underlying_price is None and futures_price is not None:
        underlying_price = futures_price
    if futures_price is None and underlying_price is None and ref_price is not None:
        futures_price = ref_price
        underlying_price = ref_price

    strikes = out.get("strikes")
    if not isinstance(strikes, list):
        strikes = []

    out["status"] = str(out.get("status") or default_status)
    out["source"] = str(source)
    out["mode_hint"] = resolved_mode
    out["timestamp"] = _normalize_timestamp_string(out.get("timestamp")) or now_iso
    out["instrument"] = inst
    out["expiry"] = out.get("expiry") or expiry
    out["underlying_price"] = underlying_price
    out["futures_price"] = futures_price
    out["pcr"] = _coerce_float(out.get("pcr"))
    out["max_pain"] = out.get("max_pain")
    out["strikes"] = strikes

    return _normalize_timestamp_fields(out)


def _normalize_depth_contract(
    instrument: str,
    payload: Optional[Dict[str, Any]],
    *,
    mode_hint: Optional[str] = None,
    default_status: str = "ok",
) -> Dict[str, Any]:
    """Force a stable depth payload shape for API/UI/agents."""
    out: Dict[str, Any] = dict(payload or {})
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    inst = str(out.get("instrument") or instrument or "").strip() or instrument
    resolved_mode = str(out.get("mode_hint") or mode_hint or _get_current_mode_hint() or "unknown").lower()
    source = out.get("source") or resolved_mode

    underlying_price = _coerce_float(out.get("underlying_price"))
    futures_price = _coerce_float(out.get("futures_price"))
    ref_price = _reference_price_for_options(inst)
    if underlying_price is None and futures_price is not None:
        underlying_price = futures_price
    if underlying_price is None and ref_price is not None:
        underlying_price = ref_price

    buy = out.get("buy")
    sell = out.get("sell")
    if not isinstance(buy, list):
        buy = []
    if not isinstance(sell, list):
        sell = []

    out["status"] = str(out.get("status") or default_status)
    out["source"] = str(source)
    out["mode_hint"] = resolved_mode
    out["timestamp"] = _normalize_timestamp_string(out.get("timestamp")) or now_iso
    out["instrument"] = inst
    out["underlying_price"] = underlying_price
    out["buy"] = buy
    out["sell"] = sell

    return _normalize_timestamp_fields(out)


# ============================================================================
# WebSocket: STOMP over WebSocket + Redis Pub/Sub Bridge
# ============================================================================


def _serialize_stomp_frame(command: str, headers: Optional[Dict[str, str]] = None, body: str = "") -> str:
    """Serialize a STOMP frame for WebSocket transport."""
    headers = headers or {}
    lines = [command]
    for k, v in headers.items():
        lines.append(f"{k}:{v}")
    lines.append("")  # header/body separator
    lines.append(body or "")
    return "\n".join(lines) + "\x00"


def _parse_stomp_frames(buffer: str) -> Tuple[List[Dict[str, Any]], str]:
    """Parse any complete STOMP frames from buffer.

    Returns (frames, remainder_buffer).
    Each frame is a dict: {command, headers, body}.
    """
    frames: List[Dict[str, Any]] = []
    if not buffer:
        return frames, buffer

    parts = buffer.split("\x00")
    remainder = parts[-1]
    for raw in parts[:-1]:
        raw = raw.lstrip("\n")  # ignore heartbeats/newlines
        if not raw.strip():
            continue

        if "\n" not in raw:
            continue

        command, rest = raw.split("\n", 1)
        if "\n\n" in rest:
            header_blob, body = rest.split("\n\n", 1)
        else:
            header_blob, body = rest, ""

        headers: dict[str, str] = {}
        for line in header_blob.split("\n"):
            if not line.strip():
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()

        frames.append({"command": command.strip(), "headers": headers, "body": body})

    return frames, remainder


def _stomp_destination_to_redis(destination: str) -> List[Tuple[str, str]]:
    """Map a STOMP destination to one or more Redis pub/sub subscriptions.

    Returns list of (kind, name) where kind is 'channel' or 'pattern'.
    """
    # Auth status
    if destination == "/topic/auth/status":
        return [("channel", "auth:status")]

    # OHLC
    if destination.startswith("/topic/market/ohlc/"):
        parts = destination.split("/")
        # /topic/market/ohlc/{instrument}
        if len(parts) == 5:
            instrument = parts[4]
            return [("pattern", f"market:ohlc:{instrument}:*")]
        # /topic/market/ohlc/{instrument}/{timeframe}
        if len(parts) >= 6:
            instrument = parts[4]
            timeframe = parts[5]
            return [("channel", f"market:ohlc:{instrument}:{timeframe}")]

    # Indicators (publisher uses type-specific suffix: indicators:{symbol}:{type})
    if destination.startswith("/topic/indicators/"):
        instrument = destination.split("/", 3)[-1]
        return [("pattern", f"indicators:{instrument}:*")]

    # Ticks (publisher uses suffix: market:tick:{symbol}:{type})
    if destination.startswith("/topic/market/tick/"):
        instrument = destination.split("/", 4)[-1]
        return [("pattern", f"market:tick:{instrument}:*")]

    # Debug/raw access (exact Redis channel)
    if destination.startswith("/topic/raw/"):
        channel = destination.split("/", 3)[-1]
        return [("channel", channel)]

    return []


@app.websocket("/ws")
async def websocket_stomp(ws: WebSocket):
    """WebSocket endpoint that supports STOMP and bridges Redis pub/sub to browser."""
    requested_subprotocols = ws.scope.get("subprotocols") or []
    selected_subprotocol = next(
        (
            protocol
            for protocol in ("v12.stomp", "v11.stomp", "v10.stomp", "stomp")
            if protocol in requested_subprotocols
        ),
        None,
    )

    if selected_subprotocol:
        await ws.accept(subprotocol=selected_subprotocol)
    else:
        await ws.accept()

    conn_id = str(uuid.uuid4())
    mode: Optional[str] = None  # 'stomp' or 'legacy'
    stomp_connected = False
    message_seq = 0
    buffer = ""

    # NOTE: redis.asyncio pubsub is unreliable in some Windows setups.
    # Use sync Redis pubsub in a background thread and forward into this async WS.
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    loop = asyncio.get_running_loop()
    stop_event = threading.Event()
    ctrl_q: "queue.SimpleQueue[tuple[str, str]]" = queue.SimpleQueue()

    # STOMP subscriptions (internal_id -> {stomp_id, destination, kind, name})
    stomp_subs: Dict[str, Dict[str, str]] = {}
    # Legacy subscriptions (name -> {destination, kind, name})
    legacy_subs: Dict[str, Dict[str, str]] = {}

    async def _send_stomp_message(stomp_subscription_id: str, destination: str, payload: Dict[str, Any]):
        nonlocal message_seq
        message_seq += 1
        frame = _serialize_stomp_frame(
            "MESSAGE",
            headers={
                "subscription": stomp_subscription_id,
                "destination": destination,
                "message-id": f"{conn_id}:{message_seq}",
                "content-type": "application/json",
            },
            body=json.dumps(payload, ensure_ascii=False),
        )
        await ws.send_text(frame)

    def _channel_matches_pattern(channel_name: Any, pattern_glob: str) -> bool:
        """Return True if a Redis channel name matches a glob-style pattern.

        Redis PSUBSCRIBE patterns use glob semantics (e.g., market:ohlc:FOO:*).
        redis-py asyncio may not always provide msg['pattern'] consistently, so
        we defensively match against the channel string ourselves.
        """
        if not pattern_glob:
            return False
        try:
            ch = channel_name.decode("utf-8") if isinstance(channel_name, (bytes, bytearray)) else str(channel_name)
            return fnmatch.fnmatchcase(ch, pattern_glob)
        except Exception:
            return False

    async def _handle_redis_message(msg: Dict[str, Any]) -> None:
        """Handle a single Redis pub/sub message and forward to the WS client."""
        try:
            if not msg:
                return

            msg_type = msg.get("type")
            if msg_type not in {"message", "pmessage"}:
                return

            channel = msg.get("channel")
            data = msg.get("data")

            if not channel:
                return

            channel = channel.decode("utf-8") if isinstance(channel, (bytes, bytearray)) else str(channel)

            # Attempt JSON decode
            decoded: Any
            if isinstance(data, (bytes, bytearray)):
                try:
                    data = data.decode("utf-8")
                except Exception:
                    data = str(data)
            if isinstance(data, str):
                try:
                    decoded = json.loads(data)
                except Exception:
                    decoded = data
            else:
                decoded = data

            payload = {
                "type": "message",
                "channel": channel,
                "data": decoded,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if mode == "legacy":
                for sub in list(legacy_subs.values()):
                    kind = sub.get("kind")
                    name = sub.get("name")
                    if kind == "channel" and name == channel:
                        await ws.send_text(json.dumps(payload, ensure_ascii=False))
                    elif kind == "pattern" and _channel_matches_pattern(channel, name):
                        await ws.send_text(json.dumps(payload, ensure_ascii=False))
                return

            for sub in list(stomp_subs.values()):
                kind = sub.get("kind")
                name = sub.get("name")
                if kind == "channel" and name == channel:
                    await _send_stomp_message(sub.get("stomp_id", ""), sub.get("destination", ""), payload)
                elif kind == "pattern" and _channel_matches_pattern(channel, name):
                    await _send_stomp_message(sub.get("stomp_id", ""), sub.get("destination", ""), payload)
        except Exception as e:
            logger.warning("WS forward error (%s): %s", conn_id, e)

    def _redis_thread() -> None:
        """Blocking Redis pubsub loop running in a background thread."""
        try:
            while not stop_event.is_set():
                # Apply any pending control commands
                while True:
                    try:
                        action, name = ctrl_q.get_nowait()
                    except Exception:
                        break
                    try:
                        if action == "subscribe":
                            pubsub.subscribe(name)
                        elif action == "psubscribe":
                            pubsub.psubscribe(name)
                        elif action == "unsubscribe":
                            pubsub.unsubscribe(name)
                        elif action == "punsubscribe":
                            pubsub.punsubscribe(name)
                    except Exception:
                        continue

                msg = pubsub.get_message(timeout=1.0)
                if msg:
                    try:
                        asyncio.run_coroutine_threadsafe(_handle_redis_message(msg), loop)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Redis WS thread ended (%s): %s", conn_id, e)

    t = threading.Thread(target=_redis_thread, name=f"ws-redis-{conn_id}", daemon=True)
    t.start()

    async def _legacy_subscribe(channels: list[str]):
        # Best-effort mapping from old dashboard channel list to actual Redis channels.
        for ch in channels:
            # already includes timeframe?
            if ch.startswith("market:ohlc:") and ch.count(":") == 2:
                # old: market:ohlc:{instrument} -> subscribe to all TF
                ctrl_q.put(("psubscribe", f"{ch}:*"))
                legacy_subs[ch] = {"destination": ch, "kind": "pattern", "name": f"{ch}:*"}
                continue
            if ch.startswith("indicators:") and ch.count(":") == 1:
                # old: indicators:{instrument} -> indicators:{instrument}:*
                pat = f"{ch}:*"
                ctrl_q.put(("psubscribe", pat))
                legacy_subs[ch] = {"destination": ch, "kind": "pattern", "name": pat}
                continue
            if ch.startswith("market:tick:") and ch.count(":") == 2:
                # old: market:tick:{instrument} -> market:tick:{instrument}:*
                pat = f"{ch}:*"
                ctrl_q.put(("psubscribe", pat))
                legacy_subs[ch] = {"destination": ch, "kind": "pattern", "name": pat}
                continue

            ctrl_q.put(("subscribe", ch))
            legacy_subs[ch] = {"destination": ch, "kind": "channel", "name": ch}

        await ws.send_text(json.dumps({"type": "subscribed", "channels": channels}, ensure_ascii=False))

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()

            text = msg.get("text")
            if text is None:
                continue

            # Detect protocol mode on first message
            if mode is None:
                if text.lstrip().startswith("{"):
                    mode = "legacy"
                else:
                    mode = "stomp"

            if mode == "legacy":
                try:
                    data = json.loads(text)
                except Exception:
                    continue
                if data.get("action") == "subscribe":
                    channels = data.get("channels") or []
                    await ws.send_text(json.dumps({"type": "connected"}, ensure_ascii=False))
                    await _legacy_subscribe(channels)
                continue

            # STOMP
            buffer += text
            frames, buffer = _parse_stomp_frames(buffer)
            for frame in frames:
                command = frame.get("command")
                headers: dict[str, str] = frame.get("headers") or {}
                body: str = frame.get("body") or ""

                if command == "CONNECT":
                    stomp_connected = True
                    await ws.send_text(
                        _serialize_stomp_frame(
                            "CONNECTED",
                            headers={"version": "1.2", "heart-beat": "0,0"},
                            body="",
                        )
                    )
                    continue

                # Some clients send STOMP instead of CONNECT
                if command == "STOMP":
                    stomp_connected = True
                    await ws.send_text(
                        _serialize_stomp_frame(
                            "CONNECTED",
                            headers={"version": "1.2", "heart-beat": "0,0"},
                            body="",
                        )
                    )
                    continue

                if not stomp_connected:
                    # If client starts with SUBSCRIBE without CONNECT, be tolerant.
                    stomp_connected = True
                    await ws.send_text(
                        _serialize_stomp_frame(
                            "CONNECTED",
                            headers={"version": "1.2", "heart-beat": "0,0"},
                            body="",
                        )
                    )

                if command == "SUBSCRIBE":
                    destination = headers.get("destination", "")
                    sub_id = headers.get("id") or str(uuid.uuid4())

                    mapped = _stomp_destination_to_redis(destination)
                    if not mapped:
                        await ws.send_text(
                            _serialize_stomp_frame(
                                "ERROR",
                                headers={"message": f"Unknown destination: {destination}"},
                                body="",
                            )
                        )
                        continue

                    # One STOMP subscription can map to multiple Redis subscriptions.
                    # All MESSAGE frames must include the original STOMP subscription id.
                    for kind, name in mapped:
                        internal_id = str(uuid.uuid4())
                        stomp_subs[internal_id] = {
                            "stomp_id": sub_id,
                            "destination": destination,
                            "kind": kind,
                            "name": name,
                        }
                        if kind == "pattern":
                            ctrl_q.put(("psubscribe", name))
                        else:
                            ctrl_q.put(("subscribe", name))

                    receipt = headers.get("receipt")
                    if receipt:
                        await ws.send_text(_serialize_stomp_frame("RECEIPT", headers={"receipt-id": receipt}))
                    continue

                if command == "UNSUBSCRIBE":
                    sub_id = headers.get("id", "")
                    to_remove = [k for k, v in stomp_subs.items() if v.get("stomp_id") == sub_id]
                    for key in to_remove:
                        sub = stomp_subs.pop(key, None)
                        if not sub:
                            continue
                        if sub.get("kind") == "pattern":
                            ctrl_q.put(("punsubscribe", sub.get("name", "")))
                        else:
                            ctrl_q.put(("unsubscribe", sub.get("name", "")))
                    continue

                if command == "DISCONNECT":
                    receipt = headers.get("receipt")
                    if receipt:
                        await ws.send_text(_serialize_stomp_frame("RECEIPT", headers={"receipt-id": receipt}))
                    await ws.close()
                    return

                if command == "SEND":
                    # Optional: allow publishing to Redis from UI for debugging.
                    destination = headers.get("destination", "")
                    if destination.startswith("/app/redis/publish"):
                        redis_channel = headers.get("redis-channel")
                        if redis_channel:
                            await redis_client.publish(redis_channel, body)
                    continue

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error (%s): %s", conn_id, e)
    finally:
        try:
            stop_event.set()
        except Exception:
            pass
        try:
            pubsub.close()
        except Exception:
            pass
        try:
            redis_client.close()
        except Exception:
            pass

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """Test page for debugging"""
    test_page_path = Path(__file__).parent / "test_page.html"
    return HTMLResponse(test_page_path.read_text())

@app.get("/test/redis")
async def test_redis():
    """Test Redis connection"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        instrument_pattern = DEFAULT_INSTRUMENT or "*"
        keys = r.keys(f"*{instrument_pattern}*")
        return {
            "connected": True,
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "total_keys": len(keys),
            "sample_keys": keys[:10] if keys else []
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}

@app.get("/test/ltp/{instrument}")
async def test_ltp(instrument: str):
    """Test LTP direct from Redis"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        ltp_raw = r.get(f"ltp:{instrument}")
        if ltp_raw:
            import json
            return json.loads(ltp_raw)
        return {"error": "No LTP data found"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/test/ohlc/{instrument}")
async def test_ohlc(instrument: str):
    """Test OHLC direct from Redis"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        import json
        
        # Try different keys
        keys_to_try = [
            f"live:ohlc_sorted:{instrument}:5min",
            f"ohlc_sorted:{instrument}:5min",
            f"live:ohlc_sorted:{instrument}:5m",
        ]
        
        for key in keys_to_try:
            entries = r.zrange(key, -5, -1)  # Last 5 bars
            if entries:
                bars = [json.loads(e) for e in entries]
                return {"key": key, "count": len(bars), "bars": bars}
        
        return {"error": "No OHLC data found", "tried_keys": keys_to_try}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "market-data-dashboard",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

@app.get("/api/market-data/health")
async def market_data_health():
    """Get market data API health"""
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/health", timeout=5)
        return _normalize_timestamp_fields(response.json())
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

@app.get("/api/v1/system/mode")
async def get_system_mode():
    """Proxy system mode request to market data API"""
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/api/v1/system/mode", timeout=5)
        if response.status_code == 200:
            return _normalize_timestamp_fields(response.json())
        else:
            return {
                "mode": "unknown",
                "error": f"API returned status {response.status_code}",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
    except Exception as e:
        return {
            "mode": "unknown",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }


def _canonical_contract_timeframe(value: Optional[str]) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"1m", "1min", "minute"}:
        return "1m"
    if raw in {"5m", "5min"}:
        return "5m"
    if raw in {"15m", "15min"}:
        return "15m"
    return "1m"


def _timeframe_aliases_for_contract(tf: str) -> List[str]:
    return PUBLIC_TIMEFRAME_ALIASES.get(_canonical_contract_timeframe(tf), [_canonical_contract_timeframe(tf)])


def _mode_priority(mode_hint: Optional[str]) -> List[str]:
    modes = ["live", "historical", "paper"]
    mode = str(mode_hint or "").strip().lower()
    if mode in modes:
        return [mode] + [m for m in modes if m != mode]
    return modes


def _scan_keys_limited(
    r: redis.Redis,
    pattern: str,
    *,
    max_keys: int = 200,
    max_pages: int = 20,
) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    cursor = 0
    pages = 0
    while True:
        try:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=500)
        except Exception:
            break
        pages += 1
        for key in keys or []:
            sk = str(key)
            if sk in seen:
                continue
            seen.add(sk)
            out.append(sk)
            if len(out) >= max_keys:
                return out
        if cursor == 0 or pages >= max_pages:
            break
    return out


def _safe_json_loads(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None


async def _load_runtime_instruments(max_instruments: int = 50) -> List[str]:
    default_instruments: List[str] = [DEFAULT_INSTRUMENT] if DEFAULT_INSTRUMENT else []
    instruments: List[str] = []
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/api/v1/market/instruments", timeout=2)
        if response.status_code == 200:
            payload = response.json()
            items = payload.get("instruments") if isinstance(payload, dict) else payload
            if isinstance(items, list):
                instruments = [str(x) for x in items if not _is_placeholder_instrument(x)]
    except Exception:
        pass

    discovered: List[str] = []
    if not instruments or instruments == default_instruments:
        discovered = await asyncio.to_thread(_discover_instruments_from_redis, max_instruments)
        if discovered:
            instruments = discovered + [inst for inst in instruments if inst not in discovered]

    if not instruments and default_instruments:
        instruments = default_instruments[:]

    deduped: List[str] = []
    seen: set[str] = set()
    for inst in instruments:
        val = str(inst).strip()
        if not val or val in seen or _is_placeholder_instrument(val):
            continue
        seen.add(val)
        deduped.append(val)
        if len(deduped) >= max_instruments:
            break
    return deduped


def _public_topic_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "mode": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "System Mode",
            "type": "object",
            "required": ["mode", "timestamp"],
            "properties": {
                "mode": {"type": "string", "enum": ["live", "historical", "paper", "unknown"]},
                "timestamp": {"type": "string", "format": "date-time"},
                "error": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "tick": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Tick Snapshot",
            "type": "object",
            "properties": {
                "instrument": {"type": "string"},
                "last_price": {"type": ["number", "null"]},
                "volume": {"type": ["number", "null"]},
                "timestamp": {"type": ["string", "null"], "format": "date-time"},
            },
            "additionalProperties": True,
        },
        "ohlc": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "OHLC Bars",
            "type": "array",
            "items": {
                "type": "object",
                "required": ["open", "high", "low", "close"],
                "properties": {
                    "start_at": {"type": ["string", "null"], "format": "date-time"},
                    "open": {"type": "number"},
                    "high": {"type": "number"},
                    "low": {"type": "number"},
                    "close": {"type": "number"},
                    "volume": {"type": ["number", "null"]},
                    "oi": {"type": ["number", "null"]},
                },
                "additionalProperties": True,
            },
        },
        "indicators": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Indicators Payload",
            "type": "object",
            "required": ["instrument", "timeframe", "status"],
            "properties": {
                "instrument": {"type": "string"},
                "timeframe": {"type": "string"},
                "status": {"type": "string"},
                "timestamp": {"type": ["string", "null"], "format": "date-time"},
                "bars_available": {"type": ["integer", "number"]},
                "indicators": {"type": "object"},
            },
            "additionalProperties": True,
        },
        "depth": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Market Depth",
            "type": "object",
            "required": ["status", "source", "timestamp", "instrument", "buy", "sell"],
            "properties": {
                "status": {"type": "string"},
                "source": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "instrument": {"type": "string"},
                "underlying_price": {"type": ["number", "null"]},
                "buy": {"type": "array"},
                "sell": {"type": "array"},
            },
            "additionalProperties": True,
        },
        "options": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Options Chain",
            "type": "object",
            "required": ["status", "source", "timestamp", "instrument", "strikes"],
            "properties": {
                "status": {"type": "string"},
                "source": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "instrument": {"type": "string"},
                "expiry": {"type": ["string", "null"]},
                "underlying_price": {"type": ["number", "null"]},
                "futures_price": {"type": ["number", "null"]},
                "pcr": {"type": ["number", "null"]},
                "max_pain": {"type": ["number", "integer", "null"]},
                "strikes": {"type": "array"},
            },
            "additionalProperties": True,
        },
    }


async def _build_runtime_catalog(instrument: Optional[str] = None) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    instruments = await _load_runtime_instruments(max_instruments=50)
    selected_instrument = str(instrument or "").strip() or (instruments[0] if instruments else (DEFAULT_INSTRUMENT or ""))
    mode_hint = _get_current_mode_hint(timeout_seconds=1.0)
    mode_candidates = _mode_priority(mode_hint)

    dashboard_port = os.getenv("DASHBOARD_PORT") or os.getenv("MARKET_DATA_DASHBOARD_PORT") or "8002"
    dashboard_base = f"http://127.0.0.1:{dashboard_port}"

    catalog: Dict[str, Any] = {
        "status": "ok",
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "timestamp": now_iso,
        "mode": mode_hint or "unknown",
        "mode_candidates": mode_candidates,
        "instrument": selected_instrument or None,
        "instruments": instruments,
        "timeframes": list(PUBLIC_TIMEFRAMES),
        "redis": {
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "db": 0,
            "mode_prefix": mode_hint or "unknown",
            "keys": {},
        },
        "apis": {
            "mode_info": f"{MARKET_DATA_API_URL}/api/v1/system/mode",
            "tick": f"{MARKET_DATA_API_URL}/api/v1/market/tick/{selected_instrument}" if selected_instrument else None,
            "ohlc": f"{dashboard_base}/api/market-data/ohlc/{selected_instrument}?timeframe=1m&limit=20" if selected_instrument else None,
            "indicators": f"{dashboard_base}/api/market-data/indicators/{selected_instrument}?timeframe=1m" if selected_instrument else None,
            "options": f"{dashboard_base}/api/market-data/options/{selected_instrument}" if selected_instrument else None,
            "depth": f"{dashboard_base}/api/market-data/depth/{selected_instrument}" if selected_instrument else None,
        },
        "ws_topics": {
            "ohlc_all_tf": f"/topic/market/ohlc/{selected_instrument}" if selected_instrument else None,
            "ohlc_tf": f"/topic/market/ohlc/{selected_instrument}/1m" if selected_instrument else None,
            "indicators": f"/topic/indicators/{selected_instrument}" if selected_instrument else None,
            "ticks": f"/topic/market/tick/{selected_instrument}" if selected_instrument else None,
        },
        "availability": {},
    }

    if not selected_instrument:
        catalog["status"] = "no_instrument"
        return _normalize_timestamp_fields(catalog)

    try:
        r = _redis_sync_client()
        r.ping()
    except Exception as e:
        catalog["status"] = "degraded"
        catalog["redis"]["error"] = str(e)
        catalog["availability"] = {
            "tick": False,
            "price": False,
            "volume": False,
            "ohlc": False,
            "indicators": False,
            "depth": False,
            "options": False,
        }
        return _normalize_timestamp_fields(catalog)

    def pick_string_value(suffixes: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        for m in mode_candidates:
            for suffix in suffixes:
                key = f"{m}:{suffix}"
                try:
                    value = r.get(key)
                    if value is not None:
                        return key, value, m
                except Exception:
                    continue
        return None, None, None

    def pick_zset_key(suffixes: List[str]) -> Tuple[Optional[str], int, Optional[str]]:
        for m in mode_candidates:
            for suffix in suffixes:
                key = f"{m}:{suffix}"
                try:
                    count = int(r.zcard(key) or 0)
                except Exception:
                    continue
                if count > 0:
                    return key, count, m
        return None, 0, None

    # Tick / Price / Volume snapshots
    tick_key, tick_raw, tick_mode = pick_string_value([
        f"websocket:tick:{selected_instrument}:latest",
        f"tick:{selected_instrument}:latest",
        f"tick:{selected_instrument}",
    ])
    price_key, price_raw, price_mode = pick_string_value([
        f"price:{selected_instrument}:latest",
        f"ltp:{selected_instrument}",
    ])
    volume_key, volume_raw, volume_mode = pick_string_value([
        f"volume:{selected_instrument}:latest",
    ])

    tick_obj = _safe_json_loads(tick_raw) if tick_raw else None
    price_obj = _safe_json_loads(price_raw) if price_raw else None
    tick_timestamp = None
    if isinstance(tick_obj, dict):
        tick_timestamp = _normalize_timestamp_string(tick_obj.get("timestamp") or tick_obj.get("exchange_timestamp"))

    catalog["redis"]["keys"]["tick_latest"] = {
        "key": tick_key,
        "mode": tick_mode,
        "present": bool(tick_key),
        "timestamp": tick_timestamp,
    }
    catalog["redis"]["keys"]["price_latest"] = {
        "key": price_key,
        "mode": price_mode,
        "present": bool(price_key),
        "value": price_obj if isinstance(price_obj, dict) else price_raw,
    }
    catalog["redis"]["keys"]["volume_latest"] = {
        "key": volume_key,
        "mode": volume_mode,
        "present": bool(volume_key),
        "value": volume_raw,
    }

    # OHLC sorted sets
    ohlc_info: Dict[str, Any] = {}
    for tf in PUBLIC_TIMEFRAMES:
        aliases = _timeframe_aliases_for_contract(tf)
        suffixes = [f"ohlc_sorted:{selected_instrument}:{alias}" for alias in aliases]
        ohlc_key, ohlc_count, ohlc_mode = pick_zset_key(suffixes)
        latest_ts = None
        latest_close = None
        if ohlc_key and ohlc_count > 0:
            try:
                row = r.zrange(ohlc_key, -1, -1)
                if row:
                    obj = _safe_json_loads(row[0])
                    if isinstance(obj, dict):
                        latest_ts = _normalize_timestamp_string(obj.get("start_at") or obj.get("timestamp"))
                        latest_close = obj.get("close")
            except Exception:
                pass
        ohlc_info[tf] = {
            "key": ohlc_key,
            "mode": ohlc_mode,
            "aliases_checked": aliases,
            "present": bool(ohlc_key),
            "count": int(ohlc_count),
            "latest_timestamp": latest_ts,
            "latest_close": latest_close,
        }
    catalog["redis"]["keys"]["ohlc_sorted"] = ohlc_info

    # Indicators keys by timeframe
    indicators_info: Dict[str, Any] = {}
    for tf in PUBLIC_TIMEFRAMES:
        aliases = _timeframe_aliases_for_contract(tf)
        found_mode: Optional[str] = None
        sample_keys: List[str] = []
        for m in mode_candidates:
            tf_keys: List[str] = []
            for alias in aliases:
                tf_keys.extend(
                    _scan_keys_limited(
                        r,
                        f"{m}:indicators:{selected_instrument}:{alias}:*",
                        max_keys=120,
                        max_pages=20,
                    )
                )
            if tf_keys:
                found_mode = m
                sample_keys = sorted(list(dict.fromkeys(tf_keys)))
                break
        indicators_info[tf] = {
            "pattern": f"{{mode}}:indicators:{selected_instrument}:{tf}:*",
            "aliases_checked": aliases,
            "mode": found_mode,
            "present": bool(sample_keys),
            "count": len(sample_keys),
            "sample_keys": sample_keys[:5],
        }
    catalog["redis"]["keys"]["indicators"] = indicators_info

    # Depth keys
    depth_latest_key, depth_latest_raw, depth_mode = pick_string_value([
        f"depth:{selected_instrument}:latest",
    ])
    depth_buy_key, depth_buy_raw, depth_buy_mode = pick_string_value([
        f"depth:{selected_instrument}:buy",
    ])
    depth_sell_key, depth_sell_raw, depth_sell_mode = pick_string_value([
        f"depth:{selected_instrument}:sell",
    ])
    depth_ts_key, depth_ts_raw, depth_ts_mode = pick_string_value([
        f"depth:{selected_instrument}:timestamp",
    ])
    catalog["redis"]["keys"]["depth"] = {
        "mode": depth_mode or depth_buy_mode or depth_sell_mode or depth_ts_mode,
        "latest_key": depth_latest_key,
        "buy_key": depth_buy_key,
        "sell_key": depth_sell_key,
        "timestamp_key": depth_ts_key,
        "present": bool(depth_latest_key or (depth_buy_key and depth_sell_key)),
        "timestamp": _normalize_timestamp_string(depth_ts_raw),
        "top_buy_levels": len(_safe_json_loads(depth_buy_raw) or []) if depth_buy_raw else 0,
        "top_sell_levels": len(_safe_json_loads(depth_sell_raw) or []) if depth_sell_raw else 0,
    }

    # Options chain key (with and without expiry component)
    options_key: Optional[str] = None
    options_mode: Optional[str] = None
    options_payload: Optional[Dict[str, Any]] = None
    for m in mode_candidates:
        direct_key = f"{m}:options:{selected_instrument}:chain"
        try:
            direct_val = r.get(direct_key)
            if direct_val:
                options_key = direct_key
                options_mode = m
                parsed = _safe_json_loads(direct_val)
                options_payload = parsed if isinstance(parsed, dict) else None
                break
        except Exception:
            pass
        expiry_keys = _scan_keys_limited(
            r,
            f"{m}:options:{selected_instrument}:*:chain",
            max_keys=1,
            max_pages=8,
        )
        if expiry_keys:
            options_key = expiry_keys[0]
            options_mode = m
            try:
                raw = r.get(options_key)
                parsed = _safe_json_loads(raw)
                options_payload = parsed if isinstance(parsed, dict) else None
            except Exception:
                options_payload = None
            break
    catalog["redis"]["keys"]["options_chain"] = {
        "key": options_key,
        "mode": options_mode,
        "present": bool(options_key),
        "expiry": (options_payload or {}).get("expiry") if isinstance(options_payload, dict) else None,
        "strikes_count": len((options_payload or {}).get("strikes") or []) if isinstance(options_payload, dict) else 0,
    }

    # API-level probes to support scenarios where data is served via API fallback
    # even when canonical Redis keys are not populated yet.
    api_probes: Dict[str, Any] = {}
    probe_targets = {
        "tick": f"{MARKET_DATA_API_URL}/api/v1/market/tick/{selected_instrument}",
        "ohlc": f"{MARKET_DATA_API_URL}/api/v1/market/ohlc/{selected_instrument}?timeframe=1m&limit=2",
        "indicators": f"{MARKET_DATA_API_URL}/api/v1/technical/indicators/{selected_instrument}?timeframe=minute",
        "depth": f"{MARKET_DATA_API_URL}/api/v1/market/depth/{selected_instrument}",
        "options": f"{MARKET_DATA_API_URL}/api/v1/options/chain/{selected_instrument}",
    }
    for probe_name, probe_url in probe_targets.items():
        probe_status = {"ok": False, "http_status": None}
        try:
            resp = requests.get(probe_url, timeout=(1.5, 3))
            probe_status["http_status"] = resp.status_code
            if resp.status_code == 200:
                payload = resp.json()
                if probe_name == "ohlc":
                    probe_status["ok"] = isinstance(payload, list) and len(payload) > 0
                elif probe_name == "indicators":
                    if isinstance(payload, dict):
                        indicators_obj = payload.get("indicators")
                        probe_status["ok"] = bool(
                            payload.get("status") in {"ok", "stale"}
                            or isinstance(indicators_obj, dict)
                            or ("data" in payload and isinstance(payload.get("data"), dict))
                        )
                elif probe_name == "depth":
                    if isinstance(payload, dict):
                        probe_status["ok"] = bool(
                            payload.get("status") in {"ok", "stale"}
                            or isinstance(payload.get("buy"), list)
                            or isinstance(payload.get("sell"), list)
                        )
                elif probe_name == "options":
                    if isinstance(payload, dict):
                        probe_status["ok"] = bool(
                            payload.get("status") in {"ok", "stale", "synthetic"}
                            or isinstance(payload.get("strikes"), list)
                        )
                else:
                    probe_status["ok"] = True
        except Exception as e:
            probe_status["error"] = str(e)
        api_probes[probe_name] = probe_status
    catalog["api_probes"] = api_probes

    redis_tick = bool(catalog["redis"]["keys"]["tick_latest"].get("present"))
    redis_price = bool(catalog["redis"]["keys"]["price_latest"].get("present"))
    redis_volume = bool(catalog["redis"]["keys"]["volume_latest"].get("present"))
    redis_ohlc = any(bool(v.get("present")) for v in ohlc_info.values())
    redis_indicators = any(bool(v.get("present")) for v in indicators_info.values())
    redis_depth = bool(catalog["redis"]["keys"]["depth"].get("present"))
    redis_options = bool(catalog["redis"]["keys"]["options_chain"].get("present"))

    catalog["availability"] = {
        "tick": redis_tick or bool(api_probes.get("tick", {}).get("ok")),
        "price": redis_price,
        "volume": redis_volume,
        "ohlc": redis_ohlc or bool(api_probes.get("ohlc", {}).get("ok")),
        "indicators": redis_indicators or bool(api_probes.get("indicators", {}).get("ok")),
        "depth": redis_depth or bool(api_probes.get("depth", {}).get("ok")),
        "options": redis_options or bool(api_probes.get("options", {}).get("ok")),
    }
    catalog["availability_detail"] = {
        "redis": {
            "tick": redis_tick,
            "price": redis_price,
            "volume": redis_volume,
            "ohlc": redis_ohlc,
            "indicators": redis_indicators,
            "depth": redis_depth,
            "options": redis_options,
        },
        "api": {k: bool(v.get("ok")) for k, v in api_probes.items()},
    }

    return _normalize_timestamp_fields(catalog)


@app.get("/api/schema")
async def get_public_schema_index():
    """Versioned schema index for external consumers."""
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    schemas = _public_topic_schemas()
    topics = [
        {
            "topic": topic,
            "version": PUBLIC_SCHEMA_VERSION,
            "schema_url": f"/api/schema/{topic}",
            "example_url": f"/api/examples/{topic}",
        }
        for topic in PUBLIC_TOPICS
        if topic in schemas
    ]
    return _normalize_timestamp_fields(
        {
            "status": "ok",
            "schema_version": PUBLIC_SCHEMA_VERSION,
            "timestamp": now_iso,
            "topics": topics,
        }
    )


@app.get("/api/schema/{topic}")
async def get_public_topic_schema(topic: str):
    """Return JSON Schema for a single topic."""
    topic_key = str(topic or "").strip().lower()
    schemas = _public_topic_schemas()
    if topic_key not in schemas:
        raise HTTPException(status_code=404, detail=f"Unknown topic '{topic_key}'. Supported: {', '.join(PUBLIC_TOPICS)}")
    return _normalize_timestamp_fields(
        {
            "status": "ok",
            "topic": topic_key,
            "schema_version": PUBLIC_SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "schema": schemas[topic_key],
        }
    )


@app.get("/api/capabilities")
async def get_public_capabilities(instrument: str = None):
    """Dynamic runtime capabilities for current mode/instrument set."""
    catalog = await _build_runtime_catalog(instrument=instrument)
    selected_instrument = catalog.get("instrument")
    return _normalize_timestamp_fields(
        {
            "status": catalog.get("status", "ok"),
            "schema_version": PUBLIC_SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mode": catalog.get("mode"),
            "instruments": catalog.get("instruments", []),
            "default_instrument": selected_instrument,
            "timeframes": list(PUBLIC_TIMEFRAMES),
            "topics": list(PUBLIC_TOPICS),
            "availability": catalog.get("availability", {}),
            "apis": catalog.get("apis", {}),
            "ws_topics": catalog.get("ws_topics", {}),
            "schema_index": "/api/schema",
        }
    )


@app.get("/api/catalog")
async def get_public_catalog(instrument: str = None):
    """Dynamic key/API catalog resolved at runtime for one instrument."""
    return await _build_runtime_catalog(instrument=instrument)


@app.get("/api/examples/{topic}")
async def get_public_topic_example(topic: str, instrument: str = None, timeframe: str = "1m"):
    """Return a current runtime sample payload for a topic."""
    topic_key = str(topic or "").strip().lower()
    if topic_key not in PUBLIC_TOPICS:
        raise HTTPException(status_code=404, detail=f"Unknown topic '{topic_key}'. Supported: {', '.join(PUBLIC_TOPICS)}")

    instruments = await _load_runtime_instruments(max_instruments=20)
    selected_instrument = str(instrument or "").strip() or (instruments[0] if instruments else DEFAULT_INSTRUMENT)
    tf = _canonical_contract_timeframe(timeframe)
    tf_for_endpoint = tf if tf != "1m" else "1min"

    sample: Any = None
    if topic_key != "mode" and not selected_instrument:
        sample = {"status": "no_data", "message": "No instrument available"}
    elif topic_key == "mode":
        sample = await get_system_mode()
    elif topic_key == "tick":
        try:
            resp = requests.get(
                f"{MARKET_DATA_API_URL}/api/v1/market/tick/{selected_instrument}",
                timeout=3,
            )
            if resp.status_code == 200:
                sample = _normalize_timestamp_fields(resp.json())
            else:
                sample = {"status": "no_data", "error": f"Upstream tick API returned {resp.status_code}"}
        except Exception as e:
            sample = {"status": "error", "error": str(e)}
    elif topic_key == "ohlc":
        sample = await get_ohlc_data(
            instrument=selected_instrument,
            timeframe=tf_for_endpoint,
            limit=3,
            order="desc",
        )
    elif topic_key == "indicators":
        sample = await get_technical_indicators(
            instrument=selected_instrument,
            timeframe=tf_for_endpoint,
        )
    elif topic_key == "depth":
        sample = await get_market_depth(selected_instrument)
    elif topic_key == "options":
        sample = await get_options_chain(selected_instrument)

    return _normalize_timestamp_fields(
        {
            "status": "ok",
            "topic": topic_key,
            "schema_version": PUBLIC_SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mode": _get_current_mode_hint(timeout_seconds=1.0) or "unknown",
            "instrument": selected_instrument,
            "timeframe": tf,
            "sample": sample,
        }
    )


@app.get("/api/market-data/status")
async def market_data_status():
    """Get comprehensive market data status"""
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "market_data_api": {"status": "unknown"},
        "redis": {"status": "unknown"},
        "instruments": {},
        "data_validation": {}
    }

    # Check market data API health
    try:
        health_response = requests.get(f"{MARKET_DATA_API_URL}/health", timeout=5)
        status["market_data_api"] = health_response.json()
    except Exception as e:
        status["market_data_api"] = {
            "status": "unreachable",
            "error": str(e)
        }

    # Prefer Redis for instrument/data availability (fast, avoids API key-prefix mismatches).
    default_instruments: List[str] = [DEFAULT_INSTRUMENT] if DEFAULT_INSTRUMENT else []
    instruments: List[str] = default_instruments[:]
    try:
        resp = requests.get(f"{MARKET_DATA_API_URL}/api/v1/market/instruments", timeout=2)
        if resp.status_code == 200:
            api_instruments = resp.json()
            if isinstance(api_instruments, dict) and "instruments" in api_instruments:
                api_instruments = api_instruments["instruments"]
            if isinstance(api_instruments, list) and api_instruments:
                instruments = [str(x) for x in api_instruments if not _is_placeholder_instrument(x)]
    except Exception:
        pass

    try:
        r = _redis_sync_client()
        r.ping()
        status["redis"] = {"status": "healthy", "host": REDIS_HOST, "port": REDIS_PORT}
    except Exception as e:
        status["redis"] = {"status": "unhealthy", "error": str(e), "host": REDIS_HOST, "port": REDIS_PORT}
        r = None

    # If API instruments endpoint is missing/unhelpful, auto-discover instruments from Redis.
    if r is not None and (not instruments or instruments == default_instruments):
        try:
            discovered = await asyncio.to_thread(_discover_instruments_from_redis, 25)
            if discovered:
                instruments = discovered
        except Exception:
            pass

    api_mode = str(status.get("market_data_api", {}).get("mode") or "").strip().lower()
    if api_mode not in {"live", "historical", "paper"}:
        api_mode = None

    for instrument in instruments:
        try:
            if not r:
                status["instruments"][instrument] = {"status": "unreachable", "error": "Redis unavailable"}
                continue

            # Prefer keys from current execution mode, then fall back to any mode.
            # This avoids showing historical namespace as green/available during live runs.
            best_key = None
            best_count = 0
            best_mode_key = None
            best_mode_count = 0

            for key in _ohlc_sorted_keys_to_try(
                instrument,
                "1min",
                preferred_mode=api_mode,
                strict_mode=bool(api_mode),
            ):
                try:
                    c = r.zcard(key)
                    if not c:
                        continue
                    key_mode = _extract_key_mode(key)
                    if api_mode and key_mode == api_mode:
                        if c > best_mode_count:
                            best_mode_key = key
                            best_mode_count = c
                    elif c > best_count:
                        best_key = key
                        best_count = c
                except Exception:
                    continue

            if best_mode_key:
                best_key = best_mode_key
                best_count = best_mode_count

            if not best_key or best_count == 0:
                status["instruments"][instrument] = {
                    "status": "no_data",
                    "data_points": 0,
                    "first_timestamp": None,
                    "latest_timestamp": None,
                    "latest_price": None,
                }
                continue

            first_row = r.zrange(best_key, 0, 0)
            last_row = r.zrange(best_key, -1, -1)
            first_bar = json.loads(first_row[0]) if first_row else {}
            last_bar = json.loads(last_row[0]) if last_row else {}

            data_mode = _extract_key_mode(best_key)
            mode_mismatch = bool(api_mode and data_mode and data_mode != api_mode)

            status["instruments"][instrument] = {
                "status": "mode_mismatch" if mode_mismatch else "available",
                "data_points": int(best_count),
                "first_timestamp": _normalize_timestamp_string(_extract_bar_timestamp(first_bar)),
                "latest_timestamp": _normalize_timestamp_string(_extract_bar_timestamp(last_bar)),
                "latest_price": last_bar.get("close") or last_bar.get("last_price"),
                "redis_key": best_key,
                "data_mode": data_mode,
                "expected_mode": api_mode,
                "mode_mismatch": mode_mismatch,
            }
        except Exception as e:
            status["instruments"][instrument] = {"status": "error", "error": str(e)}

    # Data validation checks
    status["data_validation"] = validate_data_availability(status)

    return _normalize_timestamp_fields(status)

def validate_data_availability(status: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data availability and freshness"""
    validation = {
        "overall_status": "unknown",
        "checks": {}
    }

    # Check if API is healthy
    api_healthy = status.get("market_data_api", {}).get("status") == "healthy"
    validation["checks"]["api_health"] = api_healthy

    # Check data availability
    instruments_available = 0
    instruments_with_data = 0
    for instrument, info in status.get("instruments", {}).items():
        if info.get("status") == "available":
            instruments_available += 1
            if info.get("data_points", 0) > 0:
                instruments_with_data += 1

    validation["checks"]["instruments_available"] = instruments_available
    validation["checks"]["instruments_with_data"] = instruments_with_data
    validation["checks"]["total_instruments"] = len(status.get("instruments", {}))

    # Overall status
    # IMPORTANT: In historical mode, Redis-backed data can be valid even if the
    # upstream Market Data API health check is temporarily red.
    if instruments_with_data == 0:
        validation["overall_status"] = "critical" if not api_healthy else "warning"
    elif not api_healthy:
        validation["overall_status"] = "degraded"
    elif instruments_with_data >= 2:
        validation["overall_status"] = "healthy"
    else:
        validation["overall_status"] = "partial"

    return validation

@app.get("/api/market-data/ohlc/{instrument}")
async def get_ohlc_data(
    instrument: str,
    timeframe: str = "1min",
    limit: int = 100,
    order: str = "asc",
):
    """Get OHLC data for an instrument with specified timeframe, filtered by virtual time in historical mode."""
    try:
        mode_hint = _get_current_mode_hint(timeout_seconds=1.0)

        # Fast path: read directly from Redis (handles live:/historical:/paper: prefixes).
        redis_bars, redis_key = await asyncio.to_thread(
            _read_ohlc_from_redis, instrument, timeframe, limit, order, mode_hint, bool(mode_hint)
        )
        if redis_bars:
            filtered = filter_data_by_virtual_time(redis_bars, "start_at")
            canonical_filtered = _merge_ohlc_bars_by_timeframe(filtered, timeframe)

            # Higher-timeframe sorted sets may exist without OI even when 1-min has OI.
            # In that case, rebuild from 1-min so chart OI series remains available.
            if timeframe != "1min" and canonical_filtered and not _has_any_oi(canonical_filtered):
                base_limit = _determine_base_limit(timeframe, limit)
                base_bars, _ = await asyncio.to_thread(
                    _read_ohlc_from_redis, instrument, "1min", base_limit, "asc", mode_hint, bool(mode_hint)
                )
                if base_bars:
                    base_filtered = filter_data_by_virtual_time(base_bars, "start_at")
                    aggregated = aggregate_ohlc(base_filtered, timeframe)
                    out = aggregated[-limit:] if limit and len(aggregated) > limit else aggregated
                    return _normalize_timestamp_fields(out)

            out = canonical_filtered[-limit:] if limit and len(canonical_filtered) > limit else canonical_filtered
            return _normalize_timestamp_fields(out)

        # If requested TF isn't present, aggregate from 1-min bars from Redis.
        if timeframe != "1min":
            base_limit = _determine_base_limit(timeframe, limit)
            base_bars, _ = await asyncio.to_thread(
                _read_ohlc_from_redis, instrument, "1min", base_limit, "asc", mode_hint, bool(mode_hint)
            )
            if base_bars:
                base_filtered = filter_data_by_virtual_time(base_bars, "start_at")
                aggregated = aggregate_ohlc(base_filtered, timeframe)
                out = aggregated[-limit:] if limit and len(aggregated) > limit else aggregated
                return _normalize_timestamp_fields(out)

        # Fallback to API (useful if Redis is empty or running remotely)
        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/market/ohlc/{instrument}?timeframe={timeframe}&limit={limit}&order={order}",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            filtered_data = filter_data_by_virtual_time(data, "start_at")
            canonical_filtered = _merge_ohlc_bars_by_timeframe(filtered_data, timeframe)
            out = canonical_filtered[-limit:] if limit and len(canonical_filtered) > limit else canonical_filtered
            return _normalize_timestamp_fields(out)

        if response.status_code == 404 and timeframe != "1min":
            base_limit = _determine_base_limit(timeframe, limit)
            fallback = requests.get(
                f"{MARKET_DATA_API_URL}/api/v1/market/ohlc/{instrument}?timeframe=1min&limit={base_limit}&order=asc",
                timeout=10,
            )
            if fallback.status_code != 200:
                raise HTTPException(status_code=fallback.status_code, detail="Failed to fetch OHLC data for aggregation")

            base_data = filter_data_by_virtual_time(fallback.json(), "start_at")
            filtered_data = aggregate_ohlc(base_data, timeframe)
            out = filtered_data[-limit:] if limit and len(filtered_data) > limit else filtered_data
            return _normalize_timestamp_fields(out)

        raise HTTPException(status_code=response.status_code, detail=response.text or "Failed to fetch OHLC data")

    except HTTPException as http_exc:
        logger.warning(
            "OHLC fetch failed for %s %s (limit=%s): %s",
            instrument,
            timeframe,
            limit,
            http_exc.detail,
        )
        raise
    except Exception as e:
        logger.exception("Unexpected error fetching OHLC for %s %s", instrument, timeframe)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market-data/charts/{instrument}")
async def get_chart_data(
    instrument: str,
    timeframe: str = "1min",
    limit: int = 200,
):
    """Return chart-ready payload (price + indicators) for thin frontend rendering."""
    try:
        tf = str(timeframe or "1min")
        limit_by_tf = {
            "1min": 1500,
            "5min": 500,
            "15min": 200,
            "1h": 150,
            "4h": 150,
            "1d": 150,
        }
        req_limit = max(1, int(limit or 0))
        req_limit = limit_by_tf.get(tf, req_limit)
        indicators_bars_needed = 120
        combined_limit = max(req_limit, indicators_bars_needed)

        ohlc_data = await get_ohlc_data(
            instrument=instrument,
            timeframe=tf,
            limit=combined_limit,
            order="asc",
        )
        if not isinstance(ohlc_data, list):
            ohlc_data = []

        payload = _build_chart_payload_from_ohlc(
            instrument=instrument,
            timeframe=tf,
            ohlc_data=ohlc_data,
            req_limit=req_limit,
            indicators_bars_needed=indicators_bars_needed,
        )
        payload["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload["status"] = "ok"
        return _normalize_timestamp_fields(payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error building chart data for %s %s", instrument, timeframe)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market-data/indicators/{instrument}")
async def get_technical_indicators(instrument: str, timeframe: str = "1min"):
    """Get technical indicators for an instrument"""
    cache_key = f"{instrument}:{timeframe}"
    try:
        # Normalize timeframe for API call
        tf = timeframe
        if tf == "1min":
            tf = "minute"  # API expects "minute" for 1min

        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/technical/indicators/{instrument}?timeframe={tf}",
            timeout=(1.5, 4)
        )
        if response.status_code == 200:
            payload = _normalize_timestamp_fields(response.json())
            if isinstance(payload, dict):
                payload.setdefault("instrument", instrument)
                payload.setdefault("timeframe", timeframe)
                payload.setdefault("status", "ok")
                indicators_payload = payload.get("indicators") if isinstance(payload.get("indicators"), dict) else {}
                payload.setdefault(
                    "indicator_timestamp",
                    payload.get("timestamp")
                    or indicators_payload.get("indicator_timestamp")
                    or indicators_payload.get("timestamp")
                )
                payload.setdefault(
                    "indicator_source",
                    indicators_payload.get("source") or "market_data_api"
                )
                payload.setdefault(
                    "indicator_stream",
                    payload.get("stream") or indicators_payload.get("indicator_stream") or "Y2"
                )
                payload.setdefault(
                    "indicator_update_type",
                    indicators_payload.get("indicator_update_type") or indicators_payload.get("update_type") or "batch_recalculate"
                )
                payload.setdefault("bars_available", indicators_payload.get("bars_available", 0))
                payload.setdefault(
                    "warmup_requirements",
                    payload.get("warmup_requirements") or indicators_payload.get("warmup_requirements") or {}
                )
                _LAST_GOOD_INDICATORS[cache_key] = payload
            return payload

        # Upstream returned non-200: serve stale cache if present.
        cached = _LAST_GOOD_INDICATORS.get(cache_key)
        if cached:
            out = dict(cached)
            out["status"] = "stale"
            out["warning"] = f"Upstream indicators API returned {response.status_code}"
            out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            out.setdefault("indicator_timestamp", out.get("timestamp"))
            out.setdefault("indicator_source", "cache")
            out.setdefault("indicator_stream", out.get("indicator_stream") or "Y2")
            out.setdefault("indicator_update_type", out.get("indicator_update_type") or "cache")
            out.setdefault("bars_available", out.get("bars_available", 0))
            out.setdefault("warmup_requirements", out.get("warmup_requirements", {}))
            return _normalize_timestamp_fields(out)

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "indicators": {},
            "status": "no_data",
            "error": f"Upstream indicators API returned {response.status_code}",
            "indicator_timestamp": None,
            "indicator_source": "no_data",
            "indicator_stream": "Y2",
            "indicator_update_type": "no_data",
            "bars_available": 0,
            "warmup_requirements": {},
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    except Exception as e:
        cached = _LAST_GOOD_INDICATORS.get(cache_key)
        if cached:
            out = dict(cached)
            out["status"] = "stale"
            out["warning"] = f"Using cached indicators due to upstream error: {e}"
            out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            out.setdefault("indicator_timestamp", out.get("timestamp"))
            out.setdefault("indicator_source", "cache")
            out.setdefault("indicator_stream", out.get("indicator_stream") or "Y2")
            out.setdefault("indicator_update_type", out.get("indicator_update_type") or "cache")
            out.setdefault("bars_available", out.get("bars_available", 0))
            out.setdefault("warmup_requirements", out.get("warmup_requirements", {}))
            return _normalize_timestamp_fields(out)

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "indicators": {},
            "status": "error",
            "error": str(e),
            "indicator_timestamp": None,
            "indicator_source": "error",
            "indicator_stream": "Y2",
            "indicator_update_type": "error",
            "bars_available": 0,
            "warmup_requirements": {},
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

@app.get("/api/market-data/instruments")
async def get_available_instruments():
    """Get list of available instruments"""
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/api/v1/market/instruments", timeout=5)
        if response.status_code == 200:
            payload = response.json()
            instruments = payload.get("instruments") if isinstance(payload, dict) else []
            if isinstance(instruments, list):
                instruments = [str(x) for x in instruments if not _is_placeholder_instrument(x)]
            return _normalize_timestamp_fields(
                {
                    "instruments": instruments,
                    "count": len(instruments),
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )
        else:
            # fallback to Redis discovery
            discovered = await asyncio.to_thread(_discover_instruments_from_redis, 50)
            return {"instruments": discovered or ([DEFAULT_INSTRUMENT] if DEFAULT_INSTRUMENT else [])}
    except Exception as e:
        discovered = await asyncio.to_thread(_discover_instruments_from_redis, 50)
        return {"instruments": discovered or ([DEFAULT_INSTRUMENT] if DEFAULT_INSTRUMENT else [])}

@app.get("/api/market-data/depth/{instrument}")
async def get_market_depth(instrument: str):
    """Get market depth (order book) for an instrument"""
    cache_key = instrument
    upstream_error: Optional[str] = None
    mode_hint = _get_current_mode_hint()
    try:
        # First try the Market Data API
        try:
            response = requests.get(
                f"{MARKET_DATA_API_URL}/api/v1/market/depth/{instrument}",
                timeout=(1.5, 3)
            )
            if response.status_code == 200:
                payload = _normalize_depth_contract(
                    instrument,
                    _normalize_timestamp_fields(response.json()),
                    mode_hint=mode_hint,
                    default_status="ok",
                )
                if isinstance(payload, dict):
                    payload.setdefault("status", "ok")
                    _LAST_GOOD_DEPTH[cache_key] = payload
                return payload
            upstream_error = f"Upstream depth API returned {response.status_code}"
        except Exception as api_err:
            upstream_error = str(api_err)
        
        # If API doesn't have endpoint, read directly from Redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        buy_data = r.get(get_redis_key(f"depth:{instrument}:buy"))
        sell_data = r.get(get_redis_key(f"depth:{instrument}:sell"))
        timestamp = r.get(get_redis_key(f"depth:{instrument}:timestamp"))
        
        if not buy_data or not sell_data:
            cached = _LAST_GOOD_DEPTH.get(cache_key)
            if cached:
                out = dict(cached)
                out["status"] = "stale"
                out["warning"] = upstream_error or "No fresh depth data available"
                out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                return _normalize_depth_contract(
                    instrument,
                    out,
                    mode_hint=mode_hint,
                    default_status="stale",
                )
            return _normalize_depth_contract(instrument, {
                "instrument": instrument,
                "buy": [],
                "sell": [],
                "timestamp": _normalize_timestamp_string(timestamp) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "no_data",
                "warning": upstream_error,
            }, mode_hint=mode_hint, default_status="no_data")
        
        buy_levels = json.loads(buy_data)
        sell_levels = json.loads(sell_data)
        
        out = {
            "instrument": instrument,
            "buy": buy_levels[:5],  # Top 5 bids
            "sell": sell_levels[:5],  # Top 5 asks
            "timestamp": _normalize_timestamp_string(timestamp) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "ok"
        }
        out = _normalize_depth_contract(
            instrument,
            out,
            mode_hint=mode_hint,
            default_status="ok",
        )
        _LAST_GOOD_DEPTH[cache_key] = out
        return out
        
    except Exception as e:
        logger.error(f"Error fetching depth for {instrument}: {e}")
        cached = _LAST_GOOD_DEPTH.get(cache_key)
        if cached:
            out = dict(cached)
            out["status"] = "stale"
            out["warning"] = str(e)
            out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return _normalize_depth_contract(
                instrument,
                out,
                mode_hint=mode_hint,
                default_status="stale",
            )
        return _normalize_depth_contract(instrument, {
            "instrument": instrument,
            "buy": [],
            "sell": [],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": str(e),
            "status": "error"
        }, mode_hint=mode_hint, default_status="error")

@app.get("/api/market-data/options/{instrument}")
async def get_options_chain(instrument: str, expiry: str = None):
    """Get options chain for an instrument"""
    cache_key = f"{instrument}:{expiry or 'default'}"
    upstream_error: Optional[str] = None
    mode_hint = _get_current_mode_hint()
    try:
        # First try the Market Data API
        params = {"expiry": expiry} if expiry else {}
        try:
            response = requests.get(
                f"{MARKET_DATA_API_URL}/api/v1/options/chain/{instrument}",
                params=params,
                timeout=(2, 25)
            )
            if response.status_code == 200:
                payload = _normalize_options_contract(
                    instrument,
                    _normalize_timestamp_fields(response.json()),
                    expiry=expiry,
                    mode_hint=mode_hint,
                    default_status="ok",
                )
                if isinstance(payload, dict):
                    payload_strikes = payload.get("strikes")
                    has_strikes = bool(payload_strikes)
                    mode_hint = str(payload.get("mode_hint") or mode_hint or "").lower()
                    non_informative_historical = (
                        mode_hint == "historical"
                        and has_strikes
                        and not _options_chain_has_liquidity(payload_strikes)
                    )

                    if (not has_strikes) or non_informative_historical:
                        mode_hint = str(payload.get("mode_hint") or mode_hint or "").lower()
                        synthetic_chain = None
                        if _allow_synthetic_fallback(mode_hint):
                            synthetic_chain = _build_synthetic_options_chain_black_scholes(instrument, mode_hint=mode_hint)
                        if synthetic_chain:
                            if non_informative_historical:
                                synthetic_chain["warning"] = "Historical options chain had zero OI/volume; showing synthetic fallback."
                            else:
                                synthetic_chain["warning"] = "Upstream options chain was empty; showing synthetic fallback."
                            synthetic_chain = _normalize_options_contract(
                                instrument,
                                synthetic_chain,
                                expiry=expiry,
                                mode_hint=mode_hint,
                                default_status="synthetic",
                            )
                            _LAST_GOOD_OPTIONS[cache_key] = synthetic_chain
                            return synthetic_chain

                        payload["status"] = "no_data"
                        payload["mode_hint"] = mode_hint or "unknown"
                        payload.setdefault(
                            "message",
                            f"Options chain data is currently unavailable in {(mode_hint or 'unknown').upper()} mode for this instrument."
                        )
                        payload["warning"] = payload.get("warning") or "Upstream options API returned empty options chain."
                        return _normalize_options_contract(
                            instrument,
                            payload,
                            expiry=expiry,
                            mode_hint=mode_hint,
                            default_status="no_data",
                        )

                    payload.setdefault("status", "ok")
                    _LAST_GOOD_OPTIONS[cache_key] = payload
                return payload
            upstream_error = f"Upstream options API returned {response.status_code}"
            try:
                payload = response.json()
                detail = payload.get("detail") if isinstance(payload, dict) else None
                if detail:
                    upstream_error = f"{upstream_error}: {detail}"
            except Exception:
                pass
        except Exception as api_err:
            upstream_error = str(api_err)
        
        # If API doesn't have endpoint, read directly from Redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        instrument_upper = instrument.upper()
        keys_to_try: List[str] = []
        if expiry:
            keys_to_try.extend(
                [
                    get_redis_key(f"options:{instrument_upper}:{expiry}:chain"),
                    f"options:{instrument_upper}:{expiry}:chain",
                    f"options:{instrument}:{expiry}:chain",
                ]
            )
        else:
            keys_to_try.extend(
                [
                    get_redis_key(f"options:{instrument_upper}:chain"),
                    f"options:{instrument_upper}:chain",
                    f"options:{instrument}:chain",
                ]
            )

        options_data = None
        for options_key in keys_to_try:
            if not options_key:
                continue
            try:
                options_data = r.get(options_key)
                if options_data:
                    break
            except Exception:
                continue
        
        if not options_data:
            cached = _LAST_GOOD_OPTIONS.get(cache_key)
            if cached:
                out = dict(cached)
                out["status"] = "stale"
                out["warning"] = upstream_error or "No fresh options chain data available"
                out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                return _normalize_options_contract(
                    instrument,
                    out,
                    expiry=expiry,
                    mode_hint=mode_hint,
                    default_status="stale",
                )

            synthetic_chain = None
            if _allow_synthetic_fallback(mode_hint):
                synthetic_chain = _build_synthetic_options_chain_black_scholes(instrument, mode_hint=mode_hint)
            if synthetic_chain:
                synthetic_chain = _normalize_options_contract(
                    instrument,
                    synthetic_chain,
                    expiry=expiry,
                    mode_hint=mode_hint,
                    default_status="synthetic",
                )
                _LAST_GOOD_OPTIONS[cache_key] = synthetic_chain
                return synthetic_chain

            if mode_hint == "historical":
                message = "Options chain data not available. This is normal for historical mode."
            elif mode_hint == "live":
                message = "Options chain data is temporarily unavailable in live mode (upstream timeout or no published chain for this instrument)."
            elif mode_hint == "paper":
                message = "Options chain data is currently unavailable in paper mode for this instrument."
            else:
                message = "Options chain data is currently unavailable for this instrument."

            # Return minimal structure for UI
            return _normalize_options_contract(instrument, {
                "instrument": instrument,
                "expiry": expiry,
                "strikes": [],
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "no_data",
                "mode_hint": mode_hint,
                "message": message,
                "warning": upstream_error,
            }, expiry=expiry, mode_hint=mode_hint, default_status="no_data")
        
        out = _normalize_options_contract(
            instrument,
            _normalize_timestamp_fields(json.loads(options_data)),
            expiry=expiry,
            mode_hint=mode_hint,
            default_status="ok",
        )
        if isinstance(out, dict):
            out.setdefault("status", "ok")
            _LAST_GOOD_OPTIONS[cache_key] = out
        return out
        
    except Exception as e:
        logger.error(f"Error fetching options for {instrument}: {e}")
        cached = _LAST_GOOD_OPTIONS.get(cache_key)
        if cached:
            out = dict(cached)
            out["status"] = "stale"
            out["warning"] = str(e)
            out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return _normalize_options_contract(
                instrument,
                out,
                expiry=expiry,
                mode_hint=mode_hint,
                default_status="stale",
            )
        return _normalize_options_contract(instrument, {
            "instrument": instrument,
            "expiry": expiry,
            "strikes": [],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": str(e),
            "status": "error"
        }, expiry=expiry, mode_hint=mode_hint, default_status="error")


# ============================================================================
# SIMPLE/FAST ENDPOINTS - Direct Redis Access (No Complex Processing)
# ============================================================================

@app.get("/simple")
async def simple_dashboard(request: Request):
    """Serve simple fast-loading dashboard."""
    from pathlib import Path
    html_path = Path(__file__).parent / "simple.html"
    with open(html_path, 'r') as f:
        content = f.read()
    return HTMLResponse(content=content)


@app.get("/api/simple/ohlc/{instrument}")
def simple_ohlc(instrument: str):
    """Get OHLC data directly from Redis - tries multiple key patterns."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        # Try multiple key patterns (live:, historical:, paper:, unprefixed)
        patterns = [
            f"live:ohlc_sorted:{instrument}:1m",
            f"ohlc_sorted:{instrument}:1m",
            f"historical:ohlc_sorted:{instrument}:1m",
            f"paper:ohlc_sorted:{instrument}:1m",
        ]
        
        for key in patterns:
            try:
                results = r.zrange(key, -50, -1)  # Last 50 bars
                if results:
                    bars = []
                    for json_data in results:
                        try:
                            bar = json.loads(json_data)
                            bars.append(bar)
                        except:
                            continue
                    if bars:
                        return JSONResponse(content=bars)
            except Exception as e:
                logger.warning(f"Failed to read {key}: {e}")
                continue
        
        # No data found
        return JSONResponse(content=[])
        
    except Exception as e:
        logger.error(f"Simple OHLC error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/simple/ltp/{instrument}")
async def simple_ltp(instrument: str):
    """Get LTP directly from Redis."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        # Try multiple patterns
        patterns = [f"ltp:{instrument}", f"live:ltp:{instrument}"]
        
        for key in patterns:
            try:
                data = r.get(key)
                if data:
                    return JSONResponse(content=json.loads(data))
            except:
                continue
        
        return JSONResponse(content={})
        
    except Exception as e:
        logger.error(f"Simple LTP error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/simple/redis-stats")
async def simple_redis_stats():
    """Get Redis connection stats."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        # Get total keys
        total_keys = r.dbsize()
        
        # Count OHLC keys
        ohlc_keys = len(list(r.scan_iter(match="*ohlc*", count=1000)))
        
        return JSONResponse(content={
            "connected": True,
            "total_keys": total_keys,
            "ohlc_keys": ohlc_keys,
            "server": f"{REDIS_HOST}:{REDIS_PORT}"
        })
        
    except Exception as e:
        logger.error(f"Redis stats error: {e}")
        return JSONResponse(content={
            "connected": False,
            "error": str(e)
        }, status_code=500)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MARKET_DATA_DASHBOARD_PORT", "8008"))
    uvicorn.run(app, host="0.0.0.0", port=port)
