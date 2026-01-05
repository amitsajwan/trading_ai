"""Redis-based market memory system for hot data storage."""

import redis
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from config.settings import settings

logger = logging.getLogger(__name__)


class MarketMemory:
    """
    Redis wrapper for storing hot market data (24-hour window).
    Provides fast lookup for agents.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize Redis connection."""
        self.redis_client = None
        self._redis_available = False
        
        if redis_client is None:
            try:
                self.redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                # Test connection
                self.redis_client.ping()
                self._redis_available = True
                logger.info("Redis connection established")
            except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
                logger.warning(f"Redis not available: {e}. System will work in fallback mode.")
                self._redis_available = False
        else:
            self.redis_client = redis_client
            try:
                self.redis_client.ping()
                self._redis_available = True
            except:
                self._redis_available = False
    
    def store_tick(self, instrument: str, tick_data: Dict[str, Any]) -> None:
        """Store a single tick data point - FIXED: ensures latest price key is always set."""
        if not self._redis_available:
            logger.warning("Redis not available - tick not stored")
            return
        
        try:
            # Store tick with timestamp
            timestamp = tick_data.get('timestamp', datetime.now().isoformat())
            key = f"tick:{instrument}:{timestamp}"
            # Convert to int for Redis setex
            ttl_seconds = int(timedelta(hours=24).total_seconds())
            self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(tick_data)
            )
            
            # CRITICAL: Always store latest price in a simple key for quick access
            # This is used by agents and dashboard
            price = tick_data.get("last_price") or tick_data.get("price")
            if price:
                try:
                    price_float = float(price)
                    latest_key = f"price:{instrument}:latest"
                    ttl_seconds_latest = int(timedelta(minutes=5).total_seconds())
                    self.redis_client.setex(
                        latest_key,
                        ttl_seconds_latest,
                        str(price_float)  # Ensure it's a valid number string
                    )
                    # Also store timestamp of last update
                    latest_ts_key = f"price:{instrument}:latest_ts"
                    self.redis_client.setex(
                        latest_ts_key,
                        ttl_seconds_latest,
                        timestamp
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid price value in tick data: {price} ({e})")
            else:
                logger.warning(f"No price found in tick data: {tick_data}")
        except Exception as e:
            logger.error(f"Error storing tick: {e}", exc_info=True)
    
    def store_ohlc(self, instrument: str, timeframe: str, ohlc_data: Dict[str, Any]) -> None:
        """Store OHLC candle data."""
        if not self._redis_available:
            return  # Silently skip if Redis not available
        
        try:
            # Remove MongoDB _id if present (not JSON serializable)
            ohlc_clean = {k: v for k, v in ohlc_data.items() if k != '_id'}
            
            key = f"ohlc:{instrument}:{timeframe}:{ohlc_clean.get('timestamp', datetime.now().isoformat())}"
            ttl_seconds = int(timedelta(hours=24).total_seconds())
            self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(ohlc_clean)
            )
            
            # Also maintain a sorted set for time-series queries
            sorted_set_key = f"ohlc_sorted:{instrument}:{timeframe}"
            timestamp = ohlc_clean.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if isinstance(timestamp, datetime):
                timestamp = timestamp.timestamp()
            else:
                timestamp = datetime.now().timestamp()
            
            # Use float for timestamp in zadd
            self.redis_client.zadd(
                sorted_set_key,
                {json.dumps(ohlc_clean): float(timestamp)}
            )
            
            # Keep only last 24 hours
            cutoff = float((datetime.now() - timedelta(hours=24)).timestamp())
            self.redis_client.zremrangebyscore(sorted_set_key, 0, cutoff)
        except Exception as e:
            logger.error(f"Error storing OHLC in Redis: {e}", exc_info=True)
    
    def get_recent_ohlc(self, instrument: str, timeframe: str, count: int = 60) -> List[Dict[str, Any]]:
        """Get recent OHLC candles (most recent first)."""
        if not self._redis_available:
            return []  # Return empty list if Redis not available
        
        sorted_set_key = f"ohlc_sorted:{instrument}:{timeframe}"
        
        # Get most recent candles
        results = self.redis_client.zrange(
            sorted_set_key,
            -count,
            -1,
            withscores=False
        )
        
        candles = []
        for result in results:
            try:
                candles.append(json.loads(result))
            except json.JSONDecodeError:
                continue
        
        return candles
    
    def store_sentiment_score(self, score: float, source: str = "aggregate") -> None:
        """Store sentiment score."""
        if not self._redis_available:
            return  # Silently skip if Redis not available
        
        key = f"sentiment:{source}:{datetime.now().isoformat()}"
        data = {
            "score": score,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        self.redis_client.setex(
            key,
            int(timedelta(hours=24).total_seconds()),
            json.dumps(data)
        )
    
    def get_latest_sentiment(self, source: str = "aggregate") -> Optional[float]:
        """Get latest sentiment score."""
        if not self._redis_available:
            return None  # Return None if Redis not available
        
        pattern = f"sentiment:{source}:*"
        keys = self.redis_client.keys(pattern)
        
        if not keys:
            return None
        
        # Get most recent
        latest_key = sorted(keys)[-1]
        data = self.redis_client.get(latest_key)
        
        if data:
            try:
                return json.loads(data).get("score")
            except json.JSONDecodeError:
                return None
        
        return None
    
    def store_strategy_metric(self, metric_name: str, value: float) -> None:
        """Store strategy performance metric."""
        if not self._redis_available:
            return  # Silently skip if Redis not available
        
        key = f"metric:{metric_name}:{datetime.now().isoformat()}"
        data = {
            "metric": metric_name,
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        self.redis_client.setex(
            key,
            int(timedelta(hours=24).total_seconds()),
            json.dumps(data)
        )
    
    def store_futures_data(self, instrument: str, futures_data: Dict[str, Any]) -> None:
        """
        Store futures data (funding rate, OI, etc.) in Redis.
        
        Args:
            instrument: Instrument key (e.g., "BTCUSD")
            futures_data: Dictionary with futures_price, funding_rate, open_interest, etc.
        """
        if not self._redis_available:
            return
        
        try:
            key = f"futures:{instrument}:latest"
            ttl_seconds = int(timedelta(minutes=5).total_seconds())
            self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(futures_data)
            )
        except Exception as e:
            logger.warning(f"Could not store futures data: {e}")
    
    def get_futures_data(self, instrument: str) -> Optional[Dict[str, Any]]:
        """
        Get latest futures data from Redis.
        
        Args:
            instrument: Instrument key (e.g., "BTCUSD")
        
        Returns:
            Dictionary with futures data or None if not available
        """
        if not self._redis_available:
            return None
        
        try:
            key = f"futures:{instrument}:latest"
            data_str = self.redis_client.get(key)
            if data_str:
                return json.loads(data_str)
        except Exception as e:
            logger.debug(f"Could not get futures data: {e}")
        
        return None
    
    def get_current_price(self, instrument: str) -> Optional[float]:
        """Get current price from latest tick or OHLC data."""
        if not self._redis_available:
            return None
        
        # First try quick lookup from latest price key
        try:
            latest_key = f"price:{instrument}:latest"
            price_str = self.redis_client.get(latest_key)
            if price_str:
                return float(price_str)
        except Exception:
            pass
        
        # Try to get from latest OHLC (more reliable)
        try:
            ohlc_data = self.get_recent_ohlc(instrument, "1min", 1)
            if ohlc_data and len(ohlc_data) > 0:
                latest_candle = ohlc_data[-1]
                price = latest_candle.get("close") or latest_candle.get("last_price")
                if price:
                    return float(price)
        except Exception:
            pass
        
        # Fallback: try to get from tick data
        try:
            pattern = f"tick:{instrument}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                # Get most recent tick (sort by key name which includes timestamp)
                latest_key = sorted(keys)[-1]
                data = self.redis_client.get(latest_key)
                
                if data:
                    try:
                        tick = json.loads(data)
                        return float(tick.get("last_price") or tick.get("price") or 0)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        pass
        except Exception as e:
            logger.debug(f"Error getting current price from ticks: {e}")
        
        return None
    
    def clear_old_data(self) -> None:
        """Clear data older than 24 hours (cleanup)."""
        if not self._redis_available:
            return  # Skip if Redis not available
        
        # Redis TTL handles this automatically, but we can force cleanup
        cutoff = (datetime.now() - timedelta(hours=24)).timestamp()
        
        # Clean sorted sets
        for key in self.redis_client.keys("ohlc_sorted:*"):
            self.redis_client.zremrangebyscore(key, 0, cutoff)

