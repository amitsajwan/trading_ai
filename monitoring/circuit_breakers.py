"""Circuit breakers for automatic safety mechanisms."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for automatic trading halt on unsafe conditions."""
    
    def __init__(self):
        """Initialize circuit breaker."""
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.trades_collection = get_collection(self.db, "trades_executed")
        
        self.checks = {
            "daily_loss": False,
            "consecutive_losses": False,
            "data_feed_down": False,
            "api_rate_limit": False,
            "market_halted": False,
            "high_volatility": False,
            "portfolio_over_leveraged": False
        }
    
    def check_all(self, current_pnl: float = 0.0, consecutive_losses: int = 0, 
                  data_feed_healthy: bool = True, api_calls_per_minute: int = 0,
                  market_open: bool = True, current_vix: float = 0.0,
                  current_leverage: float = 1.0) -> Dict[str, Any]:
        """Check all circuit breaker conditions."""
        today = datetime.now().date()
        
        # Daily loss check
        daily_pnl = self._get_daily_pnl(today)
        self.checks["daily_loss"] = daily_pnl < -(settings.daily_loss_limit_pct / 100) * 1000000  # Assuming 10L capital
        
        # Consecutive losses check
        self.checks["consecutive_losses"] = consecutive_losses >= 5
        
        # Data feed check
        self.checks["data_feed_down"] = not data_feed_healthy
        
        # API rate limit check (assuming 60 calls/min limit)
        self.checks["api_rate_limit"] = api_calls_per_minute > 60
        
        # Market halted check
        self.checks["market_halted"] = not market_open
        
        # High volatility check (VIX > 25)
        self.checks["high_volatility"] = current_vix > 25
        
        # Leverage check
        self.checks["portfolio_over_leveraged"] = current_leverage > settings.max_leverage * 1.1
        
        # Check if any circuit breaker is triggered
        triggered = any(self.checks.values())
        
        result = {
            "triggered": triggered,
            "checks": self.checks.copy(),
            "should_halt_trading": triggered
        }
        
        if triggered:
            logger.warning(f"Circuit breaker triggered: {result}")
        
        return result
    
    def _get_daily_pnl(self, date: datetime.date) -> float:
        """Get daily P&L from trades."""
        try:
            start_of_day = datetime.combine(date, datetime.min.time())
            end_of_day = datetime.combine(date, datetime.max.time())
            
            trades = self.trades_collection.find({
                "entry_timestamp": {
                    "$gte": start_of_day.isoformat(),
                    "$lte": end_of_day.isoformat()
                },
                "status": "CLOSED"
            })
            
            total_pnl = sum(trade.get("pnl", 0) for trade in trades)
            return total_pnl
        except Exception as e:
            logger.error(f"Error calculating daily P&L: {e}")
            return 0.0
    
    def should_halt_trading(self, **kwargs) -> bool:
        """Check if trading should be halted."""
        result = self.check_all(**kwargs)
        return result["should_halt_trading"]
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "checks": self.checks.copy(),
            "any_triggered": any(self.checks.values())
        }

