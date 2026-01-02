"""Start the complete trading system (data feed + trading service)."""

import sys
import os
import asyncio
import logging
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kiteconnect import KiteConnect
from services.trading_service import TradingService, load_kite_credentials
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Start the complete trading system."""
    logger.info("=" * 60)
    logger.info("Starting GenAI Trading System")
    logger.info("=" * 60)
    logger.info(f"Paper Trading Mode: {settings.paper_trading_mode}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"LLM Model: {settings.llm_model}")
    logger.info("=" * 60)
    
    # Load Zerodha credentials
    kite = None
    try:
        creds = load_kite_credentials()
        kite = KiteConnect(api_key=creds["api_key"])
        kite.set_access_token(creds["access_token"])
        logger.info("✅ Zerodha Kite Connect initialized")
        
        # Test connection
        try:
            profile = kite.profile()
            logger.info(f"✅ Connected as: {profile.get('user_name', 'Unknown')}")
        except Exception as e:
            logger.warning(f"Could not fetch profile: {e}")
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
    
    # Initialize trading service with Zerodha
    trading_service = TradingService(kite=kite)
    
    try:
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

