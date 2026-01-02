"""Start the complete trading system systematically."""

import sys
import asyncio
import logging
import json
import time
from pathlib import Path
from datetime import datetime

from kiteconnect import KiteConnect
from services.trading_service import TradingService, load_kite_credentials
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_prerequisites():
    """Check all prerequisites before starting."""
    logger.info("=" * 60)
    logger.info("Checking Prerequisites")
    logger.info("=" * 60)
    
    # Check credentials
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        logger.error("❌ credentials.json not found!")
        logger.error("Please run: python auto_login.py")
        return False
    logger.info("✅ Credentials file found")
    
    # Check Redis
    try:
        from data.market_memory import MarketMemory
        mm = MarketMemory()
        if mm._redis_available:
            logger.info("✅ Redis connected")
        else:
            logger.warning("⚠️  Redis not available (system will work in fallback mode)")
    except Exception as e:
        logger.warning(f"⚠️  Redis check failed: {e}")
    
    # Check MongoDB
    try:
        from mongodb_schema import get_mongo_client
        client = get_mongo_client()
        client.server_info()
        logger.info("✅ MongoDB connected")
    except Exception as e:
        logger.error(f"❌ MongoDB not available: {e}")
        return False
    
    # Check LLM
    if settings.groq_api_key or settings.openai_api_key:
        logger.info(f"✅ LLM configured ({settings.llm_provider})")
    else:
        logger.warning("⚠️  LLM not configured")
    
    logger.info("=" * 60)
    return True


async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Starting GenAI Trading System")
    logger.info("=" * 60)
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Paper Trading Mode: {settings.paper_trading_mode}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"LLM Model: {settings.llm_model}")
    logger.info("=" * 60)
    
    # Check prerequisites
    if not check_prerequisites():
        logger.error("Prerequisites check failed. Please fix the issues above.")
        return
    
    # Load Zerodha credentials
    kite = None
    try:
        creds = load_kite_credentials()
        kite = KiteConnect(api_key=creds["api_key"])
        kite.set_access_token(creds["access_token"])
        logger.info("✅ Zerodha Kite Connect initialized")
        
        # Test connection
        profile = kite.profile()
        logger.info(f"✅ Connected as: {profile.get('user_name', 'Unknown')}")
    except FileNotFoundError:
        logger.error("=" * 60)
        logger.error("ERROR: credentials.json not found!")
        logger.error("Please run: python auto_login.py")
        logger.error("=" * 60)
        return
    except Exception as e:
        logger.error(f"ERROR: Could not initialize Zerodha Kite: {e}")
        logger.error("Please check your credentials.json file")
        return
    
    # Initialize and start trading service
    trading_service = TradingService(kite=kite)
    
    try:
        logger.info("=" * 60)
        logger.info("Starting Trading Service...")
        logger.info("=" * 60)
        
        await trading_service.start()
        
    except KeyboardInterrupt:
        logger.info("\nShutting down trading system...")
    except Exception as e:
        logger.error(f"Error in trading system: {e}", exc_info=True)
    finally:
        await trading_service.stop()
        logger.info("Trading system stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("System shutdown complete")
