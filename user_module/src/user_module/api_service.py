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
import logging

logger = logging.getLogger(__name__)

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
    # Link to originating signal, if available
    signal_id: Optional[str] = None


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
                exchange_fees=float(trade.exchange_fees),
                signal_id=getattr(trade, "signal_id", None)
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


@app.get("/api/agent-status")
async def get_agent_status():
    """Get agent status as an array (for UI compatibility).
    
    Fetches latest agent decisions from MongoDB or falls back to Engine API.
    """
    try:
        # Try to fetch from MongoDB first
        from core_kernel.src.core_kernel.mongodb_schema import get_db_connection
        db = get_db_connection()
        agent_discussions = db["agent_discussions"]
        
        # Default agent list
        agent_names = [
            "TechnicalAgent", "SentimentAgent", "MacroAgent", "FundamentalAgent",
            "MomentumAgent", "TrendAgent", "VolumeAgent", "MeanReversionAgent",
            "BullResearcher", "BearResearcher", "NeutralRiskAgent", "ExecutionAgent"
        ]
        
        agents_info = []
        for agent_name in agent_names:
            latest_discussion = agent_discussions.find_one(
                {"agent_name": agent_name},
                sort=[("timestamp", -1)]
            )
            
            last_decision = None
            updated_at = datetime.now(IST).isoformat()
            
            if latest_discussion:
                last_decision = latest_discussion.get("signal") or latest_discussion.get("decision")
                updated_at = latest_discussion.get("timestamp", updated_at)
            
            agents_info.append({
                "name": agent_name,
                "state": "active",
                "status": "active",
                "last_decision": last_decision,
                "updated_at": updated_at
            })
        
        return agents_info
    except Exception as e:
        # Fallback: return basic agent list if MongoDB unavailable
        now = datetime.now(IST).isoformat()
        return [
            {"name": "TechnicalAgent", "state": "active", "status": "active", "last_decision": None, "updated_at": now},
            {"name": "SentimentAgent", "state": "active", "status": "active", "last_decision": None, "updated_at": now},
            {"name": "MacroAgent", "state": "active", "status": "active", "last_decision": None, "updated_at": now},
            {"name": "ExecutionAgent", "state": "active", "status": "active", "last_decision": None, "updated_at": now}
        ]


class TradeExecutionRequestModel(BaseModel):
    """Trade execution request model with Options support."""
    user_id: str = Field(default="default_user")
    instrument: str
    side: str  # "BUY", "SELL"
    quantity: int
    order_type: str = Field(default="MARKET")  # "MARKET", "LIMIT"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Options-specific fields
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None  # ISO format date string
    option_type: Optional[str] = None  # "CE", "PE"
    instrument_type: Optional[str] = Field(default="SPOT")  # "SPOT", "FUTURES", "OPTIONS", "STRATEGY"
    strategy_type: Optional[str] = None  # "IRON_CONDOR", "BULL_SPREAD", etc.
    # Optional link back to originating signal
    signal_id: Optional[str] = None


@app.post("/api/trading/execute")
async def execute_trade(request: TradeExecutionRequestModel):
    """Execute a trade (supports Spot, Futures, and Options).
    
    Supports:
    - Spot trades: Basic instrument, side, quantity
    - Futures trades: Instrument type = FUTURES
    - Options trades: Requires strike_price, expiry_date, option_type (CE/PE)
    - Strategy trades: Requires strategy_type (Iron Condor, Spreads, etc.)
    """
    if not user_components:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        from .api import execute_user_trade
        from .contracts import TradeExecutionRequest
        from datetime import datetime as dt
        
        # Parse expiry_date if provided
        expiry_dt = None
        if request.expiry_date:
            try:
                expiry_dt = dt.fromisoformat(request.expiry_date.replace('Z', '+00:00'))
            except Exception:
                # Try alternative formats
                try:
                    expiry_dt = dt.strptime(request.expiry_date, '%Y-%m-%d')
                except Exception:
                    pass
        
        # Get MongoDB client from components
        mongo_client = user_components["user_store"].db.client
        
        # Execute trade using user module API (with Options support)
        result = await execute_user_trade(
            mongo_client=mongo_client,
            user_id=request.user_id,
            instrument=request.instrument,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            # Options fields
            strike_price=request.strike_price,
            expiry_date=expiry_dt,
            option_type=request.option_type,
            # Pass through signal id if present
            signal_id=request.signal_id
        )
        
        if result.success:
            return {
                "success": True,
                "trade_id": result.trade_id,
                "order_id": result.order_id,
                "executed_price": float(result.executed_price) if result.executed_price else None,
                "signal_id": request.signal_id if request.signal_id else None,
                "executed_quantity": result.executed_quantity,
                "message": result.message or "Trade executed successfully",
                "instrument_type": request.instrument_type,
                "strike_price": request.strike_price,
                "expiry_date": request.expiry_date,
                "option_type": request.option_type
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.message or "Trade execution failed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute trade: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)