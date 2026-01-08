#!/usr/bin/env python3
"""Example: Integrating user module into existing backend services."""

# This would be added to the existing dashboard_pro.py or similar
# in the backend-btc, backend-banknifty, backend-nifty containers

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import os

# Import user module components
from user_module.api import (
    build_user_module, create_user_account, execute_user_trade
)
from user_module.contracts import TradeExecutionRequest

# Initialize user module (would be done once on startup)
mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")

# This would be initialized when the container starts
user_components = None

def get_user_components():
    """Dependency to get user module components."""
    global user_components
    if user_components is None:
        # Initialize with actual MongoDB client
        from pymongo import MongoClient
        mongo_client = MongoClient(mongo_uri)
        user_components = build_user_module(mongo_client)
    return user_components

# Pydantic models for API requests/responses
class CreateUserRequest(BaseModel):
    email: str
    full_name: str
    risk_profile: Optional[str] = "moderate"

class TradeRequest(BaseModel):
    instrument: str
    side: str  # "BUY" or "SELL"
    quantity: int
    order_type: str = "MARKET"  # "MARKET" or "LIMIT"
    price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    risk_profile: str

class TradeResponse(BaseModel):
    success: bool
    trade_id: Optional[str] = None
    executed_price: Optional[float] = None
    executed_quantity: Optional[int] = None
    message: str

# Example FastAPI integration
def create_user_routes(app: FastAPI):
    """Add user management routes to existing FastAPI app."""

    @app.post("/api/users", response_model=UserResponse)
    async def create_user(request: CreateUserRequest, components=Depends(get_user_components)):
        """Create a new user account."""
        try:
            # Get the actual MongoDB client from components
            mongo_client = None  # Would be extracted from components
            for key, value in components.items():
                if hasattr(value, 'db'):
                    mongo_client = value.db.client
                    break

            if not mongo_client:
                raise HTTPException(status_code=500, detail="Database connection error")

            user_id = await create_user_account(
                mongo_client=mongo_client,
                email=request.email,
                full_name=request.full_name,
                risk_profile=request.risk_profile
            )

            if user_id:
                return UserResponse(
                    user_id=user_id,
                    email=request.email,
                    full_name=request.full_name,
                    risk_profile=request.risk_profile
                )
            else:
                raise HTTPException(status_code=400, detail="User creation failed")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

    @app.get("/api/users/{user_id}")
    async def get_user(user_id: str, components=Depends(get_user_components)):
        """Get user account information."""
        try:
            user_store = components["user_store"]
            user = await user_store.get_user(user_id)

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            balance = await user_store.get_user_balance(user_id)

            return {
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "risk_profile": user.risk_profile,
                "balance": {
                    "cash": float(balance.cash_balance) if balance else 0,
                    "margin_available": float(balance.margin_available) if balance else 0,
                    "total_equity": float(balance.total_equity) if balance else 0,
                    "day_pnl": float(balance.day_pnl) if balance else 0,
                    "total_pnl": float(balance.total_pnl) if balance else 0
                } if balance else None
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting user: {str(e)}")

    @app.post("/api/users/{user_id}/trades", response_model=TradeResponse)
    async def execute_trade(user_id: str, request: TradeRequest, components=Depends(get_user_components)):
        """Execute a trade for a user."""
        try:
            # Get MongoDB client
            mongo_client = None
            for key, value in components.items():
                if hasattr(value, 'db'):
                    mongo_client = value.db.client
                    break

            if not mongo_client:
                raise HTTPException(status_code=500, detail="Database connection error")

            # Execute trade with risk management
            result = await execute_user_trade(
                mongo_client=mongo_client,
                user_id=user_id,
                instrument=request.instrument,
                side=request.side,
                quantity=request.quantity,
                order_type=request.order_type,
                price=request.price,
                stop_loss=request.stop_loss_price,
                take_profit=request.take_profit_price
            )

            return TradeResponse(
                success=result.success,
                trade_id=result.trade_id,
                executed_price=float(result.executed_price) if result.executed_price else None,
                executed_quantity=result.executed_quantity,
                message=result.message
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing trade: {str(e)}")

    @app.get("/api/users/{user_id}/portfolio")
    async def get_portfolio(user_id: str, components=Depends(get_user_components)):
        """Get user portfolio summary."""
        try:
            portfolio_store = components["portfolio_store"]
            summary = await portfolio_store.get_portfolio_summary(user_id)

            positions = await portfolio_store.get_user_positions(user_id)

            return {
                "user_id": summary.user_id,
                "total_value": float(summary.total_value),
                "cash_balance": float(summary.cash_balance),
                "margin_available": float(summary.margin_available),
                "day_pnl": float(summary.day_pnl),
                "total_pnl": float(summary.total_pnl),
                "positions_count": summary.positions_count,
                "winning_positions": summary.winning_positions,
                "losing_positions": summary.losing_positions,
                "positions": [
                    {
                        "instrument": p.instrument,
                        "quantity": p.quantity,
                        "average_price": float(p.average_price),
                        "current_price": float(p.current_price) if p.current_price else None,
                        "unrealized_pnl": float(p.unrealized_pnl) if p.unrealized_pnl else None,
                        "market_value": float(p.market_value) if p.market_value else None
                    } for p in positions
                ]
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting portfolio: {str(e)}")

    @app.get("/api/users/{user_id}/trades")
    async def get_trades(user_id: str, limit: int = 50, components=Depends(get_user_components)):
        """Get user trade history."""
        try:
            trade_store = components["trade_store"]
            trades = await trade_store.get_user_trades(user_id, limit=limit)

            return {
                "user_id": user_id,
                "trades": [
                    {
                        "trade_id": t.trade_id,
                        "instrument": t.instrument,
                        "side": t.side,
                        "quantity": t.quantity,
                        "price": float(t.price),
                        "order_type": t.order_type,
                        "timestamp": t.timestamp.isoformat(),
                        "status": t.status,
                        "broker_fees": float(t.broker_fees),
                        "exchange_fees": float(t.exchange_fees)
                    } for t in trades
                ]
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting trades: {str(e)}")

# Usage example:
# In your existing dashboard_pro.py:
#
# app = FastAPI()
# # ... existing routes ...
#
# # Add user management routes
# create_user_routes(app)
#
# # Now you have user APIs at:
# # POST /api/users - Create user
# # GET /api/users/{user_id} - Get user info
# # POST /api/users/{user_id}/trades - Execute trade
# # GET /api/users/{user_id}/portfolio - Get portfolio
# # GET /api/users/{user_id}/trades - Get trade history

if __name__ == "__main__":
    print("User API Integration Example")
    print("This shows how to integrate user module into existing backend services")
    print("No separate Docker container needed - just add routes to existing dashboards!")

