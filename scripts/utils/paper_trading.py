"""Paper trading utility for simulated trading."""

import logging
from datetime import datetime
from typing import Dict, Any, List
from core_kernel.mongodb_schema import get_mongo_client, get_collection
from core_kernel.config.settings import settings

logger = logging.getLogger(__name__)


class PaperTrading:
    """Paper trading simulator for testing without real money."""
    
    def __init__(self, initial_capital: float = 1000000):
        """Initialize paper trading with initial capital."""
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: List[Dict[str, Any]] = []
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.trades_collection = get_collection(self.db, "trades_executed")
    
    def place_order(
        self,
        signal: str,
        quantity: int,
        price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict[str, Any]:
        """Place a paper trade order."""
        # Include microseconds to ensure uniqueness across rapid test runs
        trade_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Calculate required capital
        required_capital = quantity * price
        
        if signal == "BUY" and required_capital > self.current_capital:
            logger.warning(f"Insufficient capital for paper trade. Required: {required_capital}, Available: {self.current_capital}")
            return {
                "order_id": trade_id,
                "status": "REJECTED",
                "reason": "INSUFFICIENT_CAPITAL"
            }
        
        # Create position
        position = {
            "trade_id": trade_id,
            "signal": signal,
            "quantity": quantity,
            "entry_price": price,
            "current_price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_timestamp": datetime.now().isoformat(),
            "status": "OPEN"
        }
        
        self.positions.append(position)
        
        # Deduct capital for BUY
        if signal == "BUY":
            self.current_capital -= required_capital
        
        logger.info(f"Paper trade placed: {signal} {quantity} @ {price}, Capital: {self.current_capital}")
        
        return {
            "order_id": trade_id,
            "filled_price": price,
            "filled_quantity": quantity,
            "execution_timestamp": datetime.now().isoformat(),
            "status": "COMPLETE",
            "paper_trading": True
        }
    
    def update_position(self, trade_id: str, current_price: float) -> Dict[str, Any]:
        """Update position with current price and check stop-loss/take-profit."""
        position = next((p for p in self.positions if p["trade_id"] == trade_id and p["status"] == "OPEN"), None)
        
        if not position:
            return {"status": "NOT_FOUND"}
        
        position["current_price"] = current_price
        
        # Check stop loss / take profit
        if position["signal"] == "BUY":
            if current_price <= position["stop_loss"]:
                return self.close_position(trade_id, current_price, "STOP_LOSS")
            elif current_price >= position["take_profit"]:
                return self.close_position(trade_id, current_price, "TAKE_PROFIT")
        elif position["signal"] == "SELL":
            if current_price >= position["stop_loss"]:
                return self.close_position(trade_id, current_price, "STOP_LOSS")
            elif current_price <= position["take_profit"]:
                return self.close_position(trade_id, current_price, "TAKE_PROFIT")
        
        return {"status": "OPEN", "unrealized_pnl": self._calculate_unrealized_pnl(position)}
    
    def close_position(self, trade_id: str, exit_price: float, reason: str = "MANUAL") -> Dict[str, Any]:
        """Close a position."""
        position = next((p for p in self.positions if p["trade_id"] == trade_id and p["status"] == "OPEN"), None)
        
        if not position:
            return {"status": "NOT_FOUND"}
        
        # Calculate P&L
        if position["signal"] == "BUY":
            pnl = (exit_price - position["entry_price"]) * position["quantity"]
        else:  # SELL
            pnl = (position["entry_price"] - exit_price) * position["quantity"]
        
        # Update capital
        self.current_capital += exit_price * position["quantity"] + pnl
        
        # Update position
        position["exit_price"] = exit_price
        position["exit_timestamp"] = datetime.now().isoformat()
        position["status"] = "CLOSED"
        position["pnl"] = pnl
        position["pnl_percent"] = (pnl / (position["entry_price"] * position["quantity"])) * 100
        position["exit_reason"] = reason
        
        logger.info(f"Position closed: {trade_id}, P&L: {pnl:.2f}, Capital: {self.current_capital}")
        
        return {
            "status": "CLOSED",
            "pnl": pnl,
            "pnl_percent": position["pnl_percent"],
            "current_capital": self.current_capital
        }
    
    def _calculate_unrealized_pnl(self, position: Dict[str, Any]) -> float:
        """Calculate unrealized P&L for a position."""
        if position["signal"] == "BUY":
            return (position["current_price"] - position["entry_price"]) * position["quantity"]
        else:  # SELL
            return (position["entry_price"] - position["current_price"]) * position["quantity"]
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        open_positions = [p for p in self.positions if p["status"] == "OPEN"]
        closed_positions = [p for p in self.positions if p["status"] == "CLOSED"]
        
        total_unrealized_pnl = sum(self._calculate_unrealized_pnl(p) for p in open_positions)
        total_realized_pnl = sum(p.get("pnl", 0) for p in closed_positions)
        
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "total_pnl": total_realized_pnl + total_unrealized_pnl,
            "realized_pnl": total_realized_pnl,
            "unrealized_pnl": total_unrealized_pnl,
            "return_pct": ((self.current_capital - self.initial_capital) / self.initial_capital) * 100,
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions)
        }


