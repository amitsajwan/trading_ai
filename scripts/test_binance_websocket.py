"""Test Binance WebSocket connection and data reception."""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_binance_websocket():
    """Test connecting to Binance WebSocket and receiving data."""
    ws_url = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
    
    logger.info(f"Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            logger.info("✅ Connected to Binance WebSocket!")
            logger.info("Waiting for ticker data...")
            
            # Wait for first message
            message = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(message)
            
            logger.info("=" * 60)
            logger.info("✅ RECEIVED DATA FROM BINANCE!")
            logger.info("=" * 60)
            logger.info(f"Symbol: {data.get('s')}")
            logger.info(f"Price: ${float(data.get('c', 0)):,.2f}")
            logger.info(f"Volume: {float(data.get('v', 0)):,.2f}")
            logger.info(f"Bid: ${float(data.get('b', 0)):,.2f}")
            logger.info(f"Ask: ${float(data.get('a', 0)):,.2f}")
            logger.info("=" * 60)
            
            # Receive a few more messages to confirm it's working
            logger.info("Receiving 3 more messages to confirm...")
            for i in range(3):
                message = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(message)
                logger.info(f"Message {i+1}: Price = ${float(data.get('c', 0)):,.2f}")
            
            logger.info("✅ Binance WebSocket is working correctly!")
            return True
            
    except asyncio.TimeoutError:
        logger.error("❌ Timeout waiting for data from Binance")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    result = asyncio.run(test_binance_websocket())
    exit(0 if result else 1)

