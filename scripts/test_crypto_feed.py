"""Test CryptoDataFeed connection and data storage."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.crypto_data_feed import CryptoDataFeed
from data.market_memory import MarketMemory
import redis
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_crypto_feed():
    """Test CryptoDataFeed connection and data storage."""
    logger.info("=" * 60)
    logger.info("Testing CryptoDataFeed")
    logger.info("=" * 60)
    
    mm = MarketMemory()
    feed = CryptoDataFeed(mm)
    
    logger.info("Starting crypto feed...")
    feed_task = asyncio.create_task(feed.start())
    
    # Wait for connection
    logger.info("Waiting for WebSocket connection...")
    for i in range(15):
        await asyncio.sleep(1)
        if feed.connected:
            logger.info(f"✅ Connected after {i+1} seconds!")
            break
        logger.info(f"  Waiting... ({i+1}/15)")
    else:
        logger.error("❌ Connection timeout!")
        feed.stop()
        feed_task.cancel()
        return False
    
    # Wait for data to be stored
    logger.info("Waiting for data to be stored in Redis...")
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)
    
    for i in range(10):
        await asyncio.sleep(1)
        
        # Check for price key
        price_key = "price:BTCUSD:latest"
        price = r.get(price_key)
        if price:
            logger.info(f"✅ Found price key: {price_key} = {price.decode()}")
            break
        
        # Check for tick keys
        tick_keys = r.keys("tick:BTCUSD:*")
        if tick_keys:
            logger.info(f"✅ Found {len(tick_keys)} tick keys")
            break
        
        logger.info(f"  Waiting for data... ({i+1}/10)")
    else:
        logger.error("❌ No data stored in Redis!")
        feed.stop()
        feed_task.cancel()
        return False
    
    # Check what we have
    logger.info("=" * 60)
    logger.info("Checking Redis keys...")
    logger.info("=" * 60)
    
    price_key = "price:BTCUSD:latest"
    price = r.get(price_key)
    if price:
        logger.info(f"✅ Price key: {price_key} = {price.decode()}")
    else:
        logger.warning(f"❌ No price key: {price_key}")
    
    tick_keys = r.keys("tick:BTCUSD:*")
    logger.info(f"✅ Tick keys: {len(tick_keys)} found")
    if tick_keys:
        logger.info(f"   Latest: {tick_keys[-1].decode() if isinstance(tick_keys[-1], bytes) else tick_keys[-1]}")
    
    logger.info("=" * 60)
    logger.info("✅ CryptoDataFeed test completed!")
    logger.info("=" * 60)
    
    # Stop feed
    feed.stop()
    feed_task.cancel()
    try:
        await feed_task
    except asyncio.CancelledError:
        pass
    
    return True


if __name__ == "__main__":
    result = asyncio.run(test_crypto_feed())
    exit(0 if result else 1)


