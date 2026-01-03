"""Strategy Manager - Handles strategy lifecycle and storage."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from config.settings import settings

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manages trading strategy lifecycle: create, store, update, retrieve."""
    
    def __init__(self):
        """Initialize strategy manager."""
        self.redis_client: Optional[redis.Redis] = None
        self.current_strategy: Optional[Dict[str, Any]] = None
        
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Strategy Manager Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    async def create_strategy(
        self,
        strategy_data: Dict[str, Any],
        valid_duration_minutes: int = 30
    ) -> Dict[str, Any]:
        """Create and store a new trading strategy."""
        if not self.redis_client:
            await self.initialize()
            if not self.redis_client:
                raise RuntimeError("Redis not available")
        
        try:
            strategy_id = strategy_data.get(
                "strategy_id",
                f"strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            # Set validity period
            created_at = datetime.now()
            valid_until = created_at + timedelta(minutes=valid_duration_minutes)
            
            strategy = {
                **strategy_data,
                "strategy_id": strategy_id,
                "created_at": created_at.isoformat(),
                "valid_until": valid_until.isoformat(),
                "status": "ACTIVE",
                "version": 1
            }
            
            # Store in Redis with TTL
            strategy_json = json.dumps(strategy)
            ttl_seconds = int(valid_duration_minutes * 60)
            await self.redis_client.setex(
                f"strategy:{strategy_id}",
                ttl_seconds,
                strategy_json
            )
            
            # Set as current active strategy
            await self.redis_client.setex(
                "current_strategy",
                ttl_seconds,
                strategy_json
            )
            
            self.current_strategy = strategy
            
            logger.info(f"Created strategy: {strategy_id} (valid until {valid_until.strftime('%H:%M:%S')})")
            return strategy
            
        except Exception as e:
            logger.error(f"Error creating strategy: {e}", exc_info=True)
            raise
    
    async def update_strategy(
        self,
        strategy_id: str,
        updates: Dict[str, Any],
        extend_validity: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Update existing strategy with new data."""
        if not self.redis_client:
            await self.initialize()
            if not self.redis_client:
                return None
        
        try:
            # Get current strategy
            strategy_json = await self.redis_client.get(f"strategy:{strategy_id}")
            if not strategy_json:
                logger.warning(f"Strategy {strategy_id} not found")
                return None
            
            strategy = json.loads(strategy_json)
            
            # Update fields
            strategy.update(updates)
            strategy["version"] = strategy.get("version", 1) + 1
            strategy["last_updated"] = datetime.now().isoformat()
            
            # Extend validity if requested
            if extend_validity:
                valid_until = datetime.fromisoformat(strategy["valid_until"])
                new_valid_until = valid_until + timedelta(minutes=30)
                strategy["valid_until"] = new_valid_until.isoformat()
                ttl_seconds = int((new_valid_until - datetime.now()).total_seconds())
            else:
                valid_until = datetime.fromisoformat(strategy["valid_until"])
                ttl_seconds = int((valid_until - datetime.now()).total_seconds())
            
            # Store updated strategy
            updated_json = json.dumps(strategy)
            await self.redis_client.setex(
                f"strategy:{strategy_id}",
                max(ttl_seconds, 60),  # At least 1 minute
                updated_json
            )
            
            # Update current strategy if it's the active one
            current_strategy_json = await self.redis_client.get("current_strategy")
            if current_strategy_json:
                current_strategy = json.loads(current_strategy_json)
                if current_strategy.get("strategy_id") == strategy_id:
                    await self.redis_client.setex(
                        "current_strategy",
                        max(ttl_seconds, 60),
                        updated_json
                    )
                    self.current_strategy = strategy
            
            logger.info(f"Updated strategy: {strategy_id} (version {strategy['version']})")
            return strategy
            
        except Exception as e:
            logger.error(f"Error updating strategy: {e}", exc_info=True)
            return None
    
    async def get_current_strategy(self) -> Optional[Dict[str, Any]]:
        """Get current active strategy."""
        if not self.redis_client:
            await self.initialize()
            if not self.redis_client:
                return self.current_strategy
        
        try:
            strategy_json = await self.redis_client.get("current_strategy")
            if strategy_json:
                strategy = json.loads(strategy_json)
                
                # Check if still valid
                valid_until = datetime.fromisoformat(strategy["valid_until"])
                if datetime.now() < valid_until:
                    self.current_strategy = strategy
                    return strategy
                else:
                    logger.warning("Current strategy has expired")
                    self.current_strategy = None
                    return None
            
            return self.current_strategy
            
        except Exception as e:
            logger.error(f"Error getting current strategy: {e}")
            return self.current_strategy
    
    async def is_strategy_valid(self, strategy_id: Optional[str] = None) -> bool:
        """Check if strategy is still valid."""
        strategy = await self.get_current_strategy()
        if not strategy:
            return False
        
        if strategy_id and strategy.get("strategy_id") != strategy_id:
            return False
        
        try:
            valid_until = datetime.fromisoformat(strategy["valid_until"])
            return datetime.now() < valid_until
        except Exception:
            return False
    
    async def get_strategy_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent strategy history."""
        if not self.redis_client:
            await self.initialize()
            if not self.redis_client:
                return []
        
        try:
            # Get all strategy keys
            keys = await self.redis_client.keys("strategy:*")
            strategies = []
            
            for key in keys[:limit]:
                strategy_json = await self.redis_client.get(key)
                if strategy_json:
                    strategies.append(json.loads(strategy_json))
            
            # Sort by created_at
            strategies.sort(
                key=lambda x: x.get("created_at", ""),
                reverse=True
            )
            
            return strategies[:limit]
            
        except Exception as e:
            logger.error(f"Error getting strategy history: {e}")
            return []

