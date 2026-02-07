#!/usr/bin/env python3
"""
Market Data Dashboard - Standalone Status and Visualization

This provides a web interface for monitoring market data status and visualization,
completely decoupled from engine/trading functionality.
"""

from fastapi import FastAPI, Request, HTTPException
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
from typing import Dict, Any, List, Optional
import time
import redis

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

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("index.html", {"request": request})

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

    # Check data for key instruments
    instruments = ["BANKNIFTY26FEBFUT"]
    status_ohlc_limit = 1500  # fetch full-session coverage for summary cards
    for instrument in instruments:
        try:
            # Get OHLC data
            ohlc_response = requests.get(
                f"{MARKET_DATA_API_URL}/api/v1/market/ohlc/{instrument}?timeframe=1min&limit={status_ohlc_limit}&order=asc",
                timeout=5
            )
            if ohlc_response.status_code == 200:
                data = ohlc_response.json()
                
                # Filter data by virtual time in historical mode
                filtered_data = filter_data_by_virtual_time(data, "start_at")
                
                status["instruments"][instrument] = {
                    "status": "available",
                    "data_points": len(filtered_data),
                    "first_timestamp": filtered_data[0]["start_at"] if filtered_data else None,
                    "latest_timestamp": filtered_data[-1]["start_at"] if filtered_data else None,
                    "latest_price": filtered_data[-1]["close"] if filtered_data else None
                }
            else:
                status["instruments"][instrument] = {
                    "status": "error",
                    "error_code": ohlc_response.status_code
                }
        except Exception as e:
            status["instruments"][instrument] = {
                "status": "unreachable",
                "error": str(e)
            }

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
        # First attempt: requested timeframe directly
        response = requests.get(
            f"{MARKET_DATA_API_URL}/api/v1/market/ohlc/{instrument}?timeframe={timeframe}&limit={limit}&order={order}",
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            filtered_data = filter_data_by_virtual_time(data, "start_at")
        elif response.status_code == 404 and timeframe != "1min":
            # Fallback: fetch 1-min bars and aggregate locally
            base_limit = _determine_base_limit(timeframe, limit)
            fallback = requests.get(
                f"{MARKET_DATA_API_URL}/api/v1/market/ohlc/{instrument}?timeframe=1min&limit={base_limit}&order=asc",
                timeout=10
            )
            if fallback.status_code != 200:
                raise HTTPException(status_code=fallback.status_code, detail="Failed to fetch OHLC data for aggregation")

            base_data = filter_data_by_virtual_time(fallback.json(), "start_at")
            filtered_data = aggregate_ohlc(base_data, timeframe)
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text or "Failed to fetch OHLC data")

        # Return last 'limit' data points from filtered/aggregated data
        return filtered_data[-limit:] if limit and len(filtered_data) > limit else filtered_data

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
        
        buy_data = r.get(f"depth:{instrument}:buy")
        sell_data = r.get(f"depth:{instrument}:sell")
        timestamp = r.get(f"depth:{instrument}:timestamp")
        
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MARKET_DATA_DASHBOARD_PORT", "8008"))
    uvicorn.run(app, host="0.0.0.0", port=port)