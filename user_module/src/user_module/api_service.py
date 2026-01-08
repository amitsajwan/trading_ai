"""FastAPI REST API service for user_module.

This provides HTTP endpoints for:
- User account management
- Portfolio and position management
- Trade execution and history
- Risk management
- P&L analytics
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import motor.motor_asyncio
from decimal import Decimal

# Add parent directory to path for config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from config import get_config

from .api import build_user_module
from .contracts import Position, Trade, PortfolioSummary

# IST timezone for Indian financial markets
IST = timezone(timedelta(hours=5, minutes=30))

# Global variables for components
user_components = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global user_components

    # Startup
    try:
        # Get MongoDB connection
        config = get_config()
        mongo_client = motor.motor_asyncio.AsyncIOMotorClient(config.mongodb_uri)

        # Build user module components
        user_components = build_user_module(mongo_client)

        print("User API: Services initialized successfully")
        yield

    except Exception as e:
        print(f"User API: Failed to initialize services: {e}")
        raise
    finally:
        # Shutdown
        if user_components:
            print("User API: Services shutdown complete")


app = FastAPI(
    title="User Module API",
    description="User account and portfolio management API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware to allow requests from dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API responses
class PositionResponse(BaseModel):
    user_id: str
    instrument: str
    instrument_type: str
    quantity: int
    average_price: float
    current_price: Optional[float]
    market_value: Optional[float]
    unrealized_pnl: Optional[float]
    realized_pnl: float
    last_updated: datetime
    strike_price: Optional[float]
    expiry_date: Optional[datetime]
    option_type: Optional[str]


class PortfolioSummaryResponse(BaseModel):
    user_id: str
    total_value: float
    cash_balance: float
    margin_available: float
    margin_used: float
    day_pnl: float
    total_pnl: float
    positions_count: int
    last_updated: datetime


class TradeResponse(BaseModel):
    user_id: str
    trade_id: str
    order_id: str
    instrument: str
    side: str
    quantity: int
    price: float
    order_type: str
    timestamp: datetime
    status: str
    broker_fees: float
    exchange_fees: float


class UserStatsResponse(BaseModel):
    user_id: str
    total_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    total_pnl: float
    largest_win: float
    largest_loss: float
    last_updated: datetime


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not user_components:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Test MongoDB connection
    try:
        mongo_client = user_components["user_store"].db.client
        await mongo_client.admin.command('ping')
        mongo_status = "healthy"
    except Exception as e:
        mongo_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if mongo_status == "healthy" else "degraded",
        "module": "user",
        "timestamp": datetime.now(IST).isoformat(),
        "dependencies": {
            "mongodb": mongo_status
        }
    }


@app.get("/api/trading/positions", response_model=List[PositionResponse])
async def get_user_positions(user_id: str = "default_user"):
    """Get all positions for a user."""
    if not user_components:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        portfolio_store = user_components["portfolio_store"]
        positions = await portfolio_store.get_user_positions(user_id)

        return [
            PositionResponse(
                user_id=pos.user_id,
                instrument=pos.instrument,
                instrument_type=pos.instrument_type,
                quantity=pos.quantity,
                average_price=float(pos.average_price),
                current_price=float(pos.current_price) if pos.current_price else None,
                market_value=float(pos.market_value) if pos.market_value else None,
                unrealized_pnl=float(pos.unrealized_pnl) if pos.unrealized_pnl else None,
                realized_pnl=float(pos.realized_pnl),
                last_updated=pos.last_updated,
                strike_price=float(pos.strike_price) if pos.strike_price else None,
                expiry_date=pos.expiry_date,
                option_type=pos.option_type
            )
            for pos in positions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get positions: {str(e)}")


@app.get("/api/portfolio", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(user_id: str = "default_user"):
    """Get portfolio summary for a user."""
    if not user_components:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get positions to calculate summary
        portfolio_store = user_components["portfolio_store"]
        positions = await portfolio_store.get_user_positions(user_id)

        # Get user balance
        user_store = user_components["user_store"]
        balance_doc = await user_store.balances_collection.find_one({"user_id": user_id})

        if not balance_doc:
            # Return default balance if no balance found
            return PortfolioSummaryResponse(
                user_id=user_id,
                total_value=100000.0,
                cash_balance=100000.0,
                margin_available=50000.0,
                margin_used=0.0,
                day_pnl=0.0,
                total_pnl=0.0,
                positions_count=len(positions),
                last_updated=datetime.now(IST)
            )

        # Calculate total value from positions
        total_market_value = sum(
            float(pos.market_value) if pos.market_value else 0
            for pos in positions
        )

        total_value = float(balance_doc.get("cash_balance", 0)) + total_market_value

        return PortfolioSummaryResponse(
            user_id=user_id,
            total_value=total_value,
            cash_balance=float(balance_doc.get("cash_balance", 0)),
            margin_available=float(balance_doc.get("margin_available", 0)),
            margin_used=float(balance_doc.get("margin_used", 0)),
            day_pnl=float(balance_doc.get("day_pnl", 0)),
            total_pnl=float(balance_doc.get("total_pnl", 0)),
            positions_count=len(positions),
            last_updated=datetime.now(IST)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio: {str(e)}")


@app.get("/api/recent-trades", response_model=List[TradeResponse])
async def get_recent_trades(user_id: str = "default_user", limit: int = 20):
    """Get recent trades for a user."""
    if not user_components:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        trade_store = user_components["trade_store"]
        trades = await trade_store.get_user_trades(user_id, limit=limit)

        return [
            TradeResponse(
                user_id=trade.user_id,
                trade_id=trade.trade_id,
                order_id=trade.order_id,
                instrument=trade.instrument,
                side=trade.side,
                quantity=trade.quantity,
                price=float(trade.price),
                order_type=trade.order_type,
                timestamp=trade.timestamp,
                status=trade.status,
                broker_fees=float(trade.broker_fees),
                exchange_fees=float(trade.exchange_fees)
            )
            for trade in trades
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trades: {str(e)}")


@app.get("/api/trading/stats", response_model=UserStatsResponse)
async def get_trading_stats(user_id: str = "default_user"):
    """Get trading statistics for a user."""
    if not user_components:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        pnl_analytics = user_components["pnl_analytics"]

        # Get basic stats from analytics
        stats = await pnl_analytics.get_trade_statistics(user_id)

        return UserStatsResponse(
            user_id=user_id,
            total_trades=stats.get("total_trades", 0),
            win_rate=stats.get("win_rate", 0.0),
            avg_win=stats.get("avg_win", 0.0),
            avg_loss=stats.get("avg_loss", 0.0),
            total_pnl=stats.get("total_pnl", 0.0),
            largest_win=stats.get("largest_win", 0.0),
            largest_loss=stats.get("largest_loss", 0.0),
            last_updated=datetime.now(IST)
        )
    except Exception as e:
        # Return default stats if analytics fail
        return UserStatsResponse(
            user_id=user_id,
            total_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            total_pnl=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            last_updated=datetime.now(IST)
        )


@app.get("/api/agent-decisions")
async def get_agent_decisions(user_id: str = "default_user", limit: int = 10):
    """Get recent agent decisions (placeholder - would integrate with engine module)."""
    # This would typically fetch from engine module's decision history
    # For now, return placeholder data
    return {
        "user_id": user_id,
        "decisions": [],
        "message": "Agent decisions endpoint - integration with engine module needed",
        "timestamp": datetime.now(IST).isoformat()
    }


@app.get("/api/agent-status", response_model=Dict[str, Any])
async def get_agent_status():
    """Get agent status (placeholder - would integrate with engine module)."""
    # This would typically fetch from engine module's agent status
    # For now, return placeholder data
    return {
        "agents": {
            "TechnicalAgent": {"status": "active", "last_analysis": datetime.now(IST).isoformat()},
            "SentimentAgent": {"status": "active", "last_analysis": datetime.now(IST).isoformat()},
            "MacroAgent": {"status": "active", "last_analysis": datetime.now(IST).isoformat()},
            "ExecutionAgent": {"status": "active", "last_analysis": datetime.now(IST).isoformat()}
        },
        "timestamp": datetime.now(IST).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)