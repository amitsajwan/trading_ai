"""Standalone data ingestion service runner."""

import logging
import json
import signal
import sys
import os
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kiteconnect import KiteConnect
from data.ingestion_service import DataIngestionService
from data.market_memory import MarketMemory
from data.news_collector import NewsCollector
import asyncio
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_kite_credentials() -> dict:
    """Load Kite credentials from credentials.json."""
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        raise FileNotFoundError("credentials.json not found. Run auto_login.py first.")
    
    with open(cred_path) as f:
        return json.load(f)


def main():
    """Main entry point for data ingestion service."""
    ingestion_service = None
    news_collector = None
    
    try:
        logger.info("=" * 60)
        logger.info("Starting Data Ingestion Service")
        logger.info("=" * 60)
        
        # Load credentials
        creds = load_kite_credentials()
        logger.info("✅ Credentials loaded")
        
        # Initialize Kite Connect
        kite = KiteConnect(api_key=creds["api_key"])
        kite.set_access_token(creds["access_token"])
        logger.info("✅ Kite Connect initialized")
        
        # Test connection
        try:
            profile = kite.profile()
            logger.info(f"✅ Connected as: {profile.get('user_name', 'Unknown')}")
        except Exception as e:
            logger.warning(f"Could not fetch profile: {e}")
        
        # Initialize market memory
        market_memory = MarketMemory()
        logger.info("✅ Market memory initialized")
        
        # Initialize data ingestion service
        ingestion_service = DataIngestionService(kite, market_memory)
        logger.info("✅ Data ingestion service initialized")
        
        # Initialize news collector
        news_collector = NewsCollector(market_memory)
        logger.info("✅ News collector initialized")
        
        # Start data ingestion
        logger.info("Starting WebSocket connection to Zerodha Kite...")
        ingestion_service.start()
        
        # Start news collection in background
        async def run_news_collector():
            await news_collector.run_continuous()
        
        # Run news collector in background
        import threading
        news_thread = threading.Thread(target=lambda: asyncio.run(run_news_collector()), daemon=True)
        news_thread.start()
        logger.info("✅ News collector started in background")
        
        logger.info("=" * 60)
        logger.info("Data Ingestion Service Running")
        logger.info("Receiving live market data from Zerodha Kite...")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        # Keep running until interrupted
        tick_count = 0
        last_log_time = time.time()
        
        while ingestion_service.running:
            time.sleep(1)
            tick_count += 1
            
            # Log status every 30 seconds
            if time.time() - last_log_time > 30:
                logger.info(f"Service running... (tick count: {tick_count})")
                last_log_time = time.time()
                
                # Check if we're receiving data
                if market_memory._redis_available:
                    recent_ohlc = market_memory.get_recent_ohlc("BANKNIFTY", "1min", 1)
                    if recent_ohlc:
                        logger.info(f"Latest price: {recent_ohlc[-1].get('close', 'N/A')}")
        
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        if ingestion_service:
            ingestion_service.stop()
        if news_collector:
            news_collector.stop()
        logger.info("✅ Data ingestion service stopped")
    except Exception as e:
        logger.error(f"Error in data ingestion service: {e}", exc_info=True)
        if ingestion_service:
            ingestion_service.stop()
        raise


if __name__ == "__main__":
    main()
