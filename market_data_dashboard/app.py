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
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from redis_key_manager import get_redis_key
except Exception:
    def get_redis_key(key: str, *args, **kwargs):
        return key

# Redis configuration for virtual time
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

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


def _ohlc_sorted_keys_to_try(instrument: str, timeframe: str, preferred_mode: Optional[str] = None) -> List[str]:
    tfs = _timeframe_aliases(timeframe)
    prefixes = ["live", "historical", "paper", ""]
    if preferred_mode in {"live", "historical", "paper"}:
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


def _parse_ohlc_json_rows(rows: List[str]) -> List[Dict[str, Any]]:
    bars: List[Dict[str, Any]] = []
    for row in rows:
        if not row:
            continue
        try:
            bars.append(json.loads(row))
        except Exception:
            continue
    return bars


def _read_ohlc_from_redis(
    instrument: str,
    timeframe: str,
    limit: int = 100,
    order: str = "asc",
    preferred_mode: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Read OHLC bars from Redis sorted sets, trying multiple key patterns."""
    r = _redis_sync_client()

    keys = _ohlc_sorted_keys_to_try(instrument, timeframe, preferred_mode=preferred_mode)
    for key in keys:
        try:
            count = r.zcard(key)
            if not count:
                continue

            lim = max(int(limit or 0), 1)
            if (order or "asc").lower() == "desc":
                rows = r.zrevrange(key, 0, lim - 1)
                bars = _parse_ohlc_json_rows(rows)
                return bars, key

            # asc: return latest lim bars in ascending order
            start = -lim
            end = -1
            rows = r.zrange(key, start, end)
            bars = _parse_ohlc_json_rows(rows)
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
    if tf.endswith("min"):
        try:
            minutes = int(tf.replace("min", ""))
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
            buckets[bucket_key] = {
                "instrument": item.get("instrument"),
                "timeframe": timeframe,
                "open": float(item.get("open", item.get("last_price", 0))),
                "high": float(item.get("high", item.get("last_price", 0))),
                "low": float(item.get("low", item.get("last_price", 0))),
                "close": float(item.get("close", item.get("last_price", 0))),
                "volume": item.get("volume") or 0,
                "start_at": bucket_key
            }
        else:
            bucket = buckets[bucket_key]
            bucket["high"] = max(bucket["high"], float(item.get("high", bucket["high"])))
            bucket["low"] = min(bucket["low"], float(item.get("low", bucket["low"])))
            bucket["close"] = float(item.get("close", bucket["close"]))
            bucket["volume"] = (bucket.get("volume") or 0) + (item.get("volume") or 0)

    # Return buckets sorted by time
    ordered = [buckets[k] for k in sorted(buckets.keys())]
    return ordered

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
MARKET_DATA_API_URL = os.getenv("MARKET_DATA_API_URL", "http://localhost:8004")

# Lightweight in-memory caches to keep UI responsive when upstream API is slow.
_LAST_GOOD_INDICATORS: Dict[str, Dict[str, Any]] = {}
_LAST_GOOD_DEPTH: Dict[str, Dict[str, Any]] = {}
_LAST_GOOD_OPTIONS: Dict[str, Dict[str, Any]] = {}


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
        keys = r.keys("*BANKNIFTY*")
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
    instruments: List[str] = ["BANKNIFTY26FEBFUT"]
    try:
        resp = requests.get(f"{MARKET_DATA_API_URL}/api/v1/market/instruments", timeout=2)
        if resp.status_code == 200:
            api_instruments = resp.json()
            if isinstance(api_instruments, dict) and "instruments" in api_instruments:
                api_instruments = api_instruments["instruments"]
            if isinstance(api_instruments, list) and api_instruments:
                instruments = [str(x) for x in api_instruments]
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
    if r is not None and (not instruments or instruments == ["BANKNIFTY26FEBFUT"]):
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

            for key in _ohlc_sorted_keys_to_try(instrument, "1min", preferred_mode=api_mode):
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
        # Fast path: read directly from Redis (handles live:/historical:/paper: prefixes).
        redis_bars, redis_key = await asyncio.to_thread(
            _read_ohlc_from_redis, instrument, timeframe, limit, order
        )
        if redis_bars:
            filtered = filter_data_by_virtual_time(redis_bars, "start_at")
            out = filtered[-limit:] if limit and len(filtered) > limit else filtered
            return _normalize_timestamp_fields(out)

        # If requested TF isn't present, aggregate from 1-min bars from Redis.
        if timeframe != "1min":
            base_limit = _determine_base_limit(timeframe, limit)
            base_bars, _ = await asyncio.to_thread(
                _read_ohlc_from_redis, instrument, "1min", base_limit, "asc"
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
            out = filtered_data[-limit:] if limit and len(filtered_data) > limit else filtered_data
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
                _LAST_GOOD_INDICATORS[cache_key] = payload
            return payload

        # Upstream returned non-200: serve stale cache if present.
        cached = _LAST_GOOD_INDICATORS.get(cache_key)
        if cached:
            out = dict(cached)
            out["status"] = "stale"
            out["warning"] = f"Upstream indicators API returned {response.status_code}"
            out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return _normalize_timestamp_fields(out)

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "indicators": {},
            "status": "no_data",
            "error": f"Upstream indicators API returned {response.status_code}",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    except Exception as e:
        cached = _LAST_GOOD_INDICATORS.get(cache_key)
        if cached:
            out = dict(cached)
            out["status"] = "stale"
            out["warning"] = f"Using cached indicators due to upstream error: {e}"
            out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return _normalize_timestamp_fields(out)

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "indicators": {},
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

@app.get("/api/market-data/instruments")
async def get_available_instruments():
    """Get list of available instruments"""
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/api/v1/market/instruments", timeout=5)
        if response.status_code == 200:
            return _normalize_timestamp_fields(response.json())
        else:
            # fallback to Redis discovery
            discovered = await asyncio.to_thread(_discover_instruments_from_redis, 50)
            return {"instruments": discovered or ["BANKNIFTY26FEBFUT"]}
    except Exception as e:
        discovered = await asyncio.to_thread(_discover_instruments_from_redis, 50)
        return {"instruments": discovered or ["BANKNIFTY26FEBFUT"]}

@app.get("/api/market-data/depth/{instrument}")
async def get_market_depth(instrument: str):
    """Get market depth (order book) for an instrument"""
    cache_key = instrument
    upstream_error: Optional[str] = None
    try:
        # First try the Market Data API
        try:
            response = requests.get(
                f"{MARKET_DATA_API_URL}/api/v1/market/depth/{instrument}",
                timeout=(1.5, 3)
            )
            if response.status_code == 200:
                payload = _normalize_timestamp_fields(response.json())
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
                return _normalize_timestamp_fields(out)
            return {
                "instrument": instrument,
                "buy": [],
                "sell": [],
                "timestamp": _normalize_timestamp_string(timestamp) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "no_data",
                "warning": upstream_error,
            }
        
        buy_levels = json.loads(buy_data)
        sell_levels = json.loads(sell_data)
        
        out = {
            "instrument": instrument,
            "buy": buy_levels[:5],  # Top 5 bids
            "sell": sell_levels[:5],  # Top 5 asks
            "timestamp": _normalize_timestamp_string(timestamp) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "ok"
        }
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
            return _normalize_timestamp_fields(out)
        return {
            "instrument": instrument,
            "buy": [],
            "sell": [],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": str(e),
            "status": "error"
        }

@app.get("/api/market-data/options/{instrument}")
async def get_options_chain(instrument: str, expiry: str = None):
    """Get options chain for an instrument"""
    cache_key = f"{instrument}:{expiry or 'default'}"
    upstream_error: Optional[str] = None
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
                payload = _normalize_timestamp_fields(response.json())
                if isinstance(payload, dict):
                    payload.setdefault("status", "ok")
                    _LAST_GOOD_OPTIONS[cache_key] = payload
                return payload
            upstream_error = f"Upstream options API returned {response.status_code}"
        except Exception as api_err:
            upstream_error = str(api_err)
        
        # If API doesn't have endpoint, read directly from Redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        options_key = f"options:{instrument}:chain"
        if expiry:
            options_key = f"options:{instrument}:{expiry}:chain"
        
        options_data = r.get(options_key)
        
        if not options_data:
            cached = _LAST_GOOD_OPTIONS.get(cache_key)
            if cached:
                out = dict(cached)
                out["status"] = "stale"
                out["warning"] = upstream_error or "No fresh options chain data available"
                out["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                return _normalize_timestamp_fields(out)

            mode_hint = _get_current_mode_hint()
            if mode_hint == "historical":
                message = "Options chain data not available. This is normal for historical mode."
            elif mode_hint == "live":
                message = "Options chain data is temporarily unavailable in live mode (upstream timeout or no published chain for this instrument)."
            elif mode_hint == "paper":
                message = "Options chain data is currently unavailable in paper mode for this instrument."
            else:
                message = "Options chain data is currently unavailable for this instrument."

            # Return minimal structure for UI
            return {
                "instrument": instrument,
                "expiry": expiry,
                "strikes": [],
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "no_data",
                "mode_hint": mode_hint,
                "message": message,
                "warning": upstream_error,
            }
        
        out = _normalize_timestamp_fields(json.loads(options_data))
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
            return _normalize_timestamp_fields(out)
        return {
            "instrument": instrument,
            "expiry": expiry,
            "strikes": [],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": str(e),
            "status": "error"
        }


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
