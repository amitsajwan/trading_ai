from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Dashboard (stub)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def add_camel_aliases(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    result = {}
    for key, value in data.items():
        result[key] = add_camel_aliases(value) if isinstance(value, dict) else value
        camel_key = ''.join(word.capitalize() if i > 0 else word.lower() for i, word in enumerate(key.split('_')))
        if camel_key != key:
            result[camel_key] = result[key]
    return result


@app.get("/")
async def root():
    return {"message": "OK"}


@app.get("/api/v1/technical/indicators/{instrument}")
async def get_technical_indicators_v1(instrument: str, timeframe: str = "1min"):
    now = datetime.now().isoformat()
    indicators = [
        {"name": "RSI_14", "value": 0.0, "signal": "neutral", "description": "Relative Strength Index (14)"},
        {"name": "MACD", "value": 0.0, "signal": "neutral", "description": "MACD Line"},
        {"name": "ADX_14", "value": 0.0, "signal": "neutral", "description": "Average Directional Index (14)"},
        {"name": "ATR_14", "value": 0.0, "signal": "neutral", "description": "Average True Range (14)"},
    ]
    return {"indicators": indicators, "trend": "unknown", "strength": "unknown", "timestamp": now}


@app.get("/api/technical-indicators")
async def technical_indicators():
    return await get_technical_indicators_v1(instrument=os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY"))


async def start_historical_replay(start_date=None, end_date=None, interval: str = "minute", kite=None):
    logger.info("Stub start_historical_replay called start_date=%s end_date=%s interval=%s", start_date, end_date, interval)
    await asyncio.sleep(0.1)
    return {"started": True, "start_date": str(start_date), "end_date": str(end_date), "interval": interval}


async def get_system_status():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "database": "unknown", "cache": "unknown"}


@app.get("/api/system-health")
async def system_health():
    return await get_system_status()


@app.get("/api/auth-status")
async def auth_status():
    """Get current authentication status."""
    try:
        import redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        
        # Try to get latest auth status from Redis
        auth_data = redis_client.get("auth:status:latest")
        if auth_data:
            import json
            return json.loads(auth_data)
        
        # Fallback: check if credentials exist
        cred_path = os.path.join(os.getcwd(), "credentials.json")
        if os.path.exists(cred_path):
            return {
                "status": "unknown",
                "message": "Credentials file exists but status unknown",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "failed",
                "message": "No credentials file found",
                "timestamp": datetime.now().isoformat(),
                "action_required": "manual_login",
                "url": "http://localhost:8000/auth"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error checking auth status: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


__all__ = ["app", "add_camel_aliases", "start_historical_replay", "technical_indicators"]
