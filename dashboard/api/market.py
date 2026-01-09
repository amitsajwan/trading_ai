from fastapi import APIRouter, HTTPException
from datetime import datetime

market_router = APIRouter(prefix="/api", tags=["market"])


@market_router.get("/market-data")
async def market_data():
    return {"source": "mock", "instruments": [{"symbol": "NIFTY BANK", "price": 45000.0}]}


@market_router.get("/market/data/{symbol}")
async def market_data_symbol(symbol: str):
    if symbol.upper() in ["NIFTY BANK", "BANKNIFTY", "NIFTY_BANK"]:
        return {"price": 45000.0, "timestamp": datetime.now().isoformat()}
    raise HTTPException(status_code=404, detail="Symbol not found")
