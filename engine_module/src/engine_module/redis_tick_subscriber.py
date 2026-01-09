"""Redis Tick Subscriber - Listens to Redis tick updates and processes signals.

This service subscribes to Redis pub/sub channels where market data ticks are published,
and processes each tick through the real-time signal monitoring system.
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
import os

try:
    import redis.asyncio as redis_async
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

_tick_subscriber_task = None
_subscriber_running = False


async def start_tick_subscriber() -> None:
    """Start Redis tick subscriber to process ticks for signal monitoring.
    
    This subscribes to Redis channels where market data ticks are published
    and processes them through the real-time signal monitoring system.
    """
    global _tick_subscriber_task, _subscriber_running
    
    if not REDIS_AVAILABLE:
        logger.warning("Redis async not available - tick subscriber disabled")
        return
    
    if _subscriber_running:
        logger.info("Tick subscriber already running")
        return
    
    try:
        _subscriber_running = True
        _tick_subscriber_task = asyncio.create_task(_tick_subscriber_loop())
        logger.info("Redis tick subscriber started")
    except Exception as e:
        logger.error(f"Failed to start tick subscriber: {e}", exc_info=True)
        _subscriber_running = False


async def stop_tick_subscriber() -> None:
    """Stop the Redis tick subscriber."""
    global _tick_subscriber_task, _subscriber_running
    
    _subscriber_running = False
    if _tick_subscriber_task:
        _tick_subscriber_task.cancel()
        try:
            await _tick_subscriber_task
        except asyncio.CancelledError:
            pass
        logger.info("Redis tick subscriber stopped")


async def _tick_subscriber_loop() -> None:
    """Main loop for Redis tick subscriber."""
    global _subscriber_running
    
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    
    try:
        redis_client = redis_async.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True
        )
        
        pubsub = redis_client.pubsub()
        
        # Subscribe to tick channels (multiple patterns)
        await pubsub.psubscribe(
            "__keyspace@0__:tick:*",  # Keyspace notifications for tick keys
            "market:tick:*",  # Direct pub/sub channel (if used)
            "tick:*"  # Alternative tick channel
        )
        
        logger.info("Subscribed to Redis tick channels")
        
        # Also poll for latest tick data periodically (fallback if pub/sub not enabled)
        last_processed_keys = set()
        
        while _subscriber_running:
            try:
                # Try to get message from pub/sub
                message = await asyncio.wait_for(pubsub.get_message(timeout=1.0), timeout=1.0)
                
                if message and message['type'] in ['pmessage', 'message']:
                    # Process tick update notification
                    key = message['data'] if isinstance(message['data'], str) else message['data'].decode()
                    if 'tick' in key.lower() or 'price' in key.lower():
                        await _process_tick_from_redis(redis_client, key)
                
                # Fallback: Poll Redis for new tick data (every 2 seconds)
                if asyncio.get_event_loop().time() % 2 < 0.1:  # Approximate 2-second polling
                    await _poll_redis_for_ticks(redis_client, last_processed_keys)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in tick subscriber loop: {e}", exc_info=True)
                await asyncio.sleep(1)
        
    except Exception as e:
        logger.error(f"Tick subscriber loop error: {e}", exc_info=True)
        _subscriber_running = False
    finally:
        try:
            await pubsub.unsubscribe()
            await redis_client.close()
        except Exception:
            pass


async def _poll_redis_for_ticks(redis_client: Any, last_processed_keys: set) -> None:
    """Poll Redis for new tick data as fallback if pub/sub not available.
    
    Args:
        redis_client: Redis async client
        last_processed_keys: Set of keys already processed
    """
    try:
        # Scan for tick keys
        keys_pattern = "price:*:latest_ts"
        cursor = 0
        current_keys = set()
        
        while True:
            cursor, keys = await redis_client.scan(cursor, match=keys_pattern, count=100)
            current_keys.update(keys)
            if cursor == 0:
                break
        
        # Find new keys
        new_keys = current_keys - last_processed_keys
        
        for key in new_keys:
            await _process_tick_from_redis(redis_client, key)
        
        last_processed_keys.update(new_keys)
        
    except Exception as e:
        logger.debug(f"Error polling Redis for ticks: {e}")


async def _process_tick_from_redis(redis_client: Any, key: str) -> None:
    """Process a tick update from Redis.
    
    Args:
        redis_client: Redis async client
        key: Redis key (e.g., "price:BANKNIFTY:latest_ts")
    """
    try:
        # Extract instrument from key
        parts = key.split(":")
        if len(parts) >= 2:
            instrument = parts[1].upper()
        else:
            instrument = "BANKNIFTY"
        
        # Get latest tick data
        price_key = f"price:{instrument}:latest"
        price_ts_key = f"price:{instrument}:latest_ts"
        volume_key = f"volume:{instrument}:latest"
        
        price_str = await redis_client.get(price_key)
        timestamp_str = await redis_client.get(price_ts_key)
        volume_str = await redis_client.get(volume_key)
        
        if not price_str:
            return
        
        price = float(price_str)
        timestamp = timestamp_str or datetime.now().isoformat()
        volume = int(float(volume_str)) if volume_str else 0
        
        # Process tick through signal monitoring
        from .realtime_tick_integration import process_tick_for_signals
        
        tick_dict = {
            "last_price": price,
            "volume": volume,
            "timestamp": timestamp
        }
        
        result = await process_tick_for_signals(instrument, tick_dict)
        
        if result.get("signals_triggered", 0) > 0:
            logger.info(f"✅ {result['signals_triggered']} signal(s) triggered for {instrument} at price {price}")
        
    except Exception as e:
        logger.debug(f"Error processing tick from Redis key {key}: {e}")
