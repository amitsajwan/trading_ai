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
import redis.asyncio as aioredis

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
            try:
                # Handle both offset-naive and offset-aware timestamps
                if '+' in item_time_str or 'Z' in item_time_str:
                    # Already has timezone info
                    item_time = datetime.fromisoformat(item_time_str.replace('Z', '+00:00'))
                else:
                    # No timezone info, assume IST (+05:30) to match virtual time
                    item_time = datetime.fromisoformat(item_time_str).replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
                
                if item_time <= current_virtual_time:
                    filtered_data.append(item)
            except (ValueError, AttributeError):
                # If we can't parse the timestamp, include the item
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


def _ohlc_sorted_keys_to_try(instrument: str, timeframe: str) -> List[str]:
    tfs = _timeframe_aliases(timeframe)
    prefixes = ["live", "historical", "paper", ""]
    keys: List[str] = []
    for tf in tfs:
        for p in prefixes:
            if p:
                keys.append(f"{p}:ohlc_sorted:{instrument}:{tf}")
            else:
                keys.append(f"ohlc_sorted:{instrument}:{tf}")
    return keys


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
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Read OHLC bars from Redis sorted sets, trying multiple key patterns."""
    r = _redis_sync_client()

    keys = _ohlc_sorted_keys_to_try(instrument, timeframe)
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
    await ws.accept()

    conn_id = str(uuid.uuid4())
    mode: Optional[str] = None  # 'stomp' or 'legacy'
    stomp_connected = False
    message_seq = 0
    buffer = ""

    redis_client = aioredis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    pubsub = redis_client.pubsub()

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

    async def _redis_forwarder():
        """Forward messages from Redis pub/sub to this WebSocket."""
        try:
            async for msg in pubsub.listen():
                if not msg:
                    continue

                msg_type = msg.get("type")
                if msg_type in {"subscribe", "psubscribe", "unsubscribe", "punsubscribe"}:
                    continue

                channel = msg.get("channel")
                data = msg.get("data")
                pattern = msg.get("pattern")

                if not channel:
                    continue

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

                # Deliver to matching subscriptions
                if mode == "legacy":
                    for sub in list(legacy_subs.values()):
                        kind = sub.get("kind")
                        name = sub.get("name")
                        if kind == "channel" and name == channel:
                            await ws.send_text(json.dumps(payload, ensure_ascii=False))
                        elif kind == "pattern" and pattern and name == pattern:
                            await ws.send_text(json.dumps(payload, ensure_ascii=False))
                else:
                    for sub in list(stomp_subs.values()):
                        kind = sub.get("kind")
                        name = sub.get("name")
                        if kind == "channel" and name == channel:
                            await _send_stomp_message(sub.get("stomp_id", ""), sub.get("destination", ""), payload)
                        elif kind == "pattern" and pattern and name == pattern:
                            await _send_stomp_message(sub.get("stomp_id", ""), sub.get("destination", ""), payload)
        except Exception as e:
            logger.warning("WS Redis forwarder ended (%s): %s", conn_id, e)

    forward_task = asyncio.create_task(_redis_forwarder())

    async def _legacy_subscribe(channels: list[str]):
        # Best-effort mapping from old dashboard channel list to actual Redis channels.
        for ch in channels:
            # already includes timeframe?
            if ch.startswith("market:ohlc:") and ch.count(":") == 2:
                # old: market:ohlc:{instrument} -> subscribe to all TF
                await pubsub.psubscribe(f"{ch}:*")
                legacy_subs[ch] = {"destination": ch, "kind": "pattern", "name": f"{ch}:*"}
                continue
            if ch.startswith("indicators:") and ch.count(":") == 1:
                # old: indicators:{instrument} -> indicators:{instrument}:*
                pat = f"{ch}:*"
                await pubsub.psubscribe(pat)
                legacy_subs[ch] = {"destination": ch, "kind": "pattern", "name": pat}
                continue
            if ch.startswith("market:tick:") and ch.count(":") == 2:
                # old: market:tick:{instrument} -> market:tick:{instrument}:*
                pat = f"{ch}:*"
                await pubsub.psubscribe(pat)
                legacy_subs[ch] = {"destination": ch, "kind": "pattern", "name": pat}
                continue

            await pubsub.subscribe(ch)
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
                            await pubsub.psubscribe(name)
                        else:
                            await pubsub.subscribe(name)

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
                            await pubsub.punsubscribe(sub.get("name", ""))
                        else:
                            await pubsub.unsubscribe(sub.get("name", ""))
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
            forward_task.cancel()
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        try:
            await redis_client.close()
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
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/market-data/health")
async def market_data_health():
    """Get market data API health"""
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/health", timeout=5)
        return response.json()
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/v1/system/mode")
async def get_system_mode():
    """Proxy system mode request to market data API"""
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/api/v1/system/mode", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "mode": "unknown",
                "error": f"API returned status {response.status_code}",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "mode": "unknown",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/market-data/status")
async def market_data_status():
    """Get comprehensive market data status"""
    status = {
        "timestamp": datetime.now().isoformat(),
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

    for instrument in instruments:
        try:
            if not r:
                status["instruments"][instrument] = {"status": "unreachable", "error": "Redis unavailable"}
                continue

            # Find the first key with data (1min is a good baseline for status cards)
            best_key = None
            best_count = 0
            for key in _ohlc_sorted_keys_to_try(instrument, "1min"):
                try:
                    c = r.zcard(key)
                    if c and c > best_count:
                        best_key = key
                        best_count = c
                except Exception:
                    continue

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

            status["instruments"][instrument] = {
                "status": "available",
                "data_points": int(best_count),
                "first_timestamp": _extract_bar_timestamp(first_bar),
                "latest_timestamp": _extract_bar_timestamp(last_bar),
                "latest_price": last_bar.get("close") or last_bar.get("last_price"),
                "redis_key": best_key,
            }
        except Exception as e:
            status["instruments"][instrument] = {"status": "error", "error": str(e)}

    # Data validation checks
    status["data_validation"] = validate_data_availability(status)

    return status

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
    if not api_healthy:
        validation["overall_status"] = "critical"
    elif instruments_with_data == 0:
        validation["overall_status"] = "warning"
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
            return filtered[-limit:] if limit and len(filtered) > limit else filtered

        # If requested TF isn't present, aggregate from 1-min bars from Redis.
        if timeframe != "1min":
            base_limit = _determine_base_limit(timeframe, limit)
            base_bars, _ = await asyncio.to_thread(
                _read_ohlc_from_redis, instrument, "1min", base_limit, "asc"
            )
            if base_bars:
                base_filtered = filter_data_by_virtual_time(base_bars, "start_at")
                aggregated = aggregate_ohlc(base_filtered, timeframe)
                return aggregated[-limit:] if limit and len(aggregated) > limit else aggregated

        # Fallback to API (useful if Redis is empty or running remotely)
        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/market/ohlc/{instrument}?timeframe={timeframe}&limit={limit}&order={order}",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            filtered_data = filter_data_by_virtual_time(data, "start_at")
            return filtered_data[-limit:] if limit and len(filtered_data) > limit else filtered_data

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
            return filtered_data[-limit:] if limit and len(filtered_data) > limit else filtered_data

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
async def get_technical_indicators(instrument: str):
    """Get technical indicators for an instrument"""
    try:
        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/technical/indicators/{instrument}",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch technical indicators")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market-data/instruments")
async def get_available_instruments():
    """Get list of available instruments"""
    try:
        response = requests.get(f"{MARKET_DATA_API_URL}/api/v1/market/instruments", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"instruments": ["BANKNIFTY26FEBFUT"]}
    except Exception as e:
        return {"instruments": ["BANKNIFTY26FEBFUT"]}

@app.get("/api/market-data/depth/{instrument}")
async def get_market_depth(instrument: str):
    """Get market depth (order book) for an instrument"""
    try:
        # First try the Market Data API
        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/market/depth/{instrument}",
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        
        # If API doesn't have endpoint, read directly from Redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        buy_data = r.get(get_redis_key(f"depth:{instrument}:buy"))
        sell_data = r.get(get_redis_key(f"depth:{instrument}:sell"))
        timestamp = r.get(get_redis_key(f"depth:{instrument}:timestamp"))
        
        if not buy_data or not sell_data:
            return {
                "instrument": instrument,
                "buy": [],
                "sell": [],
                "timestamp": timestamp or datetime.now().isoformat(),
                "status": "no_data"
            }
        
        buy_levels = json.loads(buy_data)
        sell_levels = json.loads(sell_data)
        
        return {
            "instrument": instrument,
            "buy": buy_levels[:5],  # Top 5 bids
            "sell": sell_levels[:5],  # Top 5 asks
            "timestamp": timestamp or datetime.now().isoformat(),
            "status": "ok"
        }
        
    except Exception as e:
        logger.error(f"Error fetching depth for {instrument}: {e}")
        return {
            "instrument": instrument,
            "buy": [],
            "sell": [],
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "status": "error"
        }

@app.get("/api/market-data/options/{instrument}")
async def get_options_chain(instrument: str, expiry: str = None):
    """Get options chain for an instrument"""
    try:
        # First try the Market Data API
        params = {"expiry": expiry} if expiry else {}
        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/options/chain/{instrument}",
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        
        # If API doesn't have endpoint, read directly from Redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        options_key = f"options:{instrument}:chain"
        if expiry:
            options_key = f"options:{instrument}:{expiry}:chain"
        
        options_data = r.get(options_key)
        
        if not options_data:
            # Return minimal structure for UI
            return {
                "instrument": instrument,
                "expiry": expiry,
                "strikes": [],
                "timestamp": datetime.now().isoformat(),
                "status": "no_data",
                "message": "Options chain data not available. This is normal for historical mode."
            }
        
        return json.loads(options_data)
        
    except Exception as e:
        logger.error(f"Error fetching options for {instrument}: {e}")
        return {
            "instrument": instrument,
            "expiry": expiry,
            "strikes": [],
            "timestamp": datetime.now().isoformat(),
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