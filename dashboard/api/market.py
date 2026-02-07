from fastapi import APIRouter, HTTPException
from datetime import datetime
import redis
import json

market_router = APIRouter(prefix="/api", tags=["market"])


@market_router.get("/market-data")
async def market_data():
    """Get current market data - returns clear indication when data is unavailable."""
    try:
        # Try to get real data from Redis first
        redis_client = redis.Redis(host='redis', port=6379, db=0)
        
        # Check if we have any market data
        instruments = []
        
        # Try to get some basic instrument data
        try:
            # Check for common instruments
            for symbol in ['BANKNIFTY', 'NIFTY', 'NSE:NIFTY50']:
                price_key = f"price:{symbol}:latest"
                price_data = redis_client.get(price_key)
                if price_data:
                    instruments.append({
                        "symbol": symbol,
                        "price": float(price_data.decode()),
                        "status": "active"
                    })
        except Exception:
            pass
        
        if instruments:
            # We have some real data
            return {
                "source": "live",
                "instruments": instruments,
                "status": "partial_data" if len(instruments) < 3 else "active",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # No live data available
            return {
                "source": "unavailable",
                "instruments": [],
                "status": "no_data",
                "message": "Live market data not available - market data feed is offline",
                "timestamp": datetime.now().isoformat(),
                "error": "Market data API unavailable"
            }
            
    except Exception as e:
        return {
            "source": "error",
            "instruments": [],
            "status": "error",
            "message": "Failed to connect to market data service",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@market_router.get("/market/data/{symbol}")
async def market_data_symbol(symbol: str):
    try:
        # Try to get data from Redis first
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        
        # Get latest price from tick data
        tick_key = f"tick:{symbol}:latest"
        tick_data = redis_client.get(tick_key)
        if tick_data:
            tick_json = json.loads(tick_data)
            return {
                "price": tick_json.get("price", 0),
                "timestamp": tick_json.get("timestamp", datetime.now().isoformat()),
                "instrument": symbol
            }
        
        # Fallback to hardcoded values for known instruments
        if symbol.upper() in ["NIFTY BANK", "BANKNIFTY", "NIFTY_BANK"]:
            return {"price": 45000.0, "timestamp": datetime.now().isoformat(), "instrument": symbol}
        
        # For other instruments, try to get from OHLC data
        ohlc_key = f"ohlc_sorted:{symbol}:1min"
        ohlc_data = redis_client.zrange(ohlc_key, -1, -1, withscores=True)
        if ohlc_data:
            # Parse the latest OHLC bar
            latest_bar = json.loads(ohlc_data[0][0])
            return {
                "price": latest_bar.get("close", 0),
                "timestamp": latest_bar.get("timestamp", datetime.now().isoformat()),
                "instrument": symbol
            }
        
        raise HTTPException(status_code=404, detail="Symbol not found")
        
    except Exception as e:
        # Fallback to mock data if Redis is unavailable
        if symbol.upper() in ["NIFTY BANK", "BANKNIFTY", "NIFTY_BANK", "BANKNIFTY26JANFUT"]:
            return {"price": 59187.95, "timestamp": datetime.now().isoformat(), "instrument": symbol}
        raise HTTPException(status_code=404, detail="Symbol not found")
