"""Health monitoring for trading system components."""

import asyncio
import logging
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitor health of system components."""
    
    def __init__(self, market_memory):
        """Initialize health monitor."""
        self.market_memory = market_memory
        self.running = False
        self._check_task: Optional[asyncio.Task] = None
    
    async def check_tick_data_freshness(self) -> Dict[str, Any]:
        """Check if tick data is fresh (received recently)."""
        try:
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            latest_price_key = f"price:{instrument_key}:latest"
            latest_ts_key = f"price:{instrument_key}:latest_ts"
            
            if not self.market_memory._redis_available:
                return {
                    "status": "error",
                    "message": "Redis not available",
                    "fresh": False
                }
            
            # Check latest price timestamp
            latest_ts_str = self.market_memory.redis_client.get(latest_ts_key)
            if not latest_ts_str:
                return {
                    "status": "warning",
                    "message": "No latest price timestamp found",
                    "fresh": False,
                    "age_seconds": None
                }
            
            try:
                latest_ts = datetime.fromisoformat(latest_ts_str.decode() if isinstance(latest_ts_str, bytes) else latest_ts_str)
                age = (datetime.now() - latest_ts).total_seconds()
                
                # Consider fresh if < 10 seconds old
                is_fresh = age < 10
                
                return {
                    "status": "ok" if is_fresh else "warning",
                    "message": f"Latest tick {age:.1f}s ago" if is_fresh else f"Latest tick {age:.1f}s ago (stale)",
                    "fresh": is_fresh,
                    "age_seconds": age,
                    "latest_timestamp": latest_ts.isoformat()
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error parsing timestamp: {e}",
                    "fresh": False
                }
        except Exception as e:
            logger.error(f"Error checking tick freshness: {e}")
            return {
                "status": "error",
                "message": str(e),
                "fresh": False
            }
    
    async def check_websocket_status(self, crypto_feed) -> Dict[str, Any]:
        """Check WebSocket connection status."""
        if not crypto_feed:
            return {
                "status": "unknown",
                "message": "Crypto feed not initialized",
                "connected": False
            }
        
        return {
            "status": "ok" if crypto_feed.connected else "error",
            "message": "Connected" if crypto_feed.connected else "Disconnected",
            "connected": crypto_feed.connected,
            "tick_count": getattr(crypto_feed, '_tick_count', 0)
        }
    
    async def run_health_checks(self, crypto_feed=None):
        """Run periodic health checks."""
        while self.running:
            try:
                # Check tick data freshness
                tick_status = await self.check_tick_data_freshness()
                
                if not tick_status.get("fresh"):
                    age = tick_status.get("age_seconds")
                    if age and age > 60:
                        logger.warning(f"⚠️ HEALTH CHECK: Tick data is stale ({age:.1f}s old)")
                    elif age and age > 10:
                        logger.warning(f"⚠️ HEALTH CHECK: Tick data may be stale ({age:.1f}s old)")
                
                # Check WebSocket status
                if crypto_feed:
                    ws_status = await self.check_websocket_status(crypto_feed)
                    if not ws_status.get("connected"):
                        logger.warning("⚠️ HEALTH CHECK: WebSocket disconnected")
                
                # Wait 30 seconds before next check
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error in health check: {e}")
                await asyncio.sleep(30)
    
    async def start(self, crypto_feed=None):
        """Start health monitoring."""
        if self.running:
            return
        
        self.running = True
        self._check_task = asyncio.create_task(self.run_health_checks(crypto_feed))
        logger.info("Health monitor started")
    
    async def stop(self):
        """Stop health monitoring."""
        self.running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor stopped")

