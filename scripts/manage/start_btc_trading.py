"""Start the Enhanced Trading Service for BTC."""

import asyncio
import logging
import sys
from pathlib import Path

# Set BTC configuration before importing settings
import os
os.environ["INSTRUMENT_SYMBOL"] = "BTC-USD"
os.environ["INSTRUMENT_EXCHANGE"] = "BINANCE"
os.environ["DATA_SOURCE"] = "BINANCE"

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.enhanced_trading_service import EnhancedTradingService
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for BTC trading."""
    logger.info("=" * 70)
    logger.info("Enhanced Trading Service - BTC Futures Trading")
    logger.info("=" * 70)
    logger.info(f"Instrument: {settings.instrument_symbol}")
    logger.info(f"Exchange: {settings.instrument_exchange}")
    logger.info(f"Data Source: {settings.data_source}")
    logger.info("")
    logger.info("Architecture: Three-Layer GenAI-Enhanced")
    logger.info("  Layer 1 (Strategic): Deep analysis every 10 min (optimal for crypto)")
    logger.info("  Layer 2 (Tactical): Quick validation every 3 min")
    logger.info("  Layer 3 (Execution): Continuous rule-based execution (<50ms per tick)")
    logger.info("")
    logger.info("Features:")
    logger.info("  - Real-time BTC futures data (Binance)")
    logger.info("  - Funding rate tracking")
    logger.info("  - Open interest monitoring")
    logger.info("  - LLM-powered rule generation")
    logger.info("  - Generic system (no hardcoding)")
    logger.info("=" * 70)
    
    # No Kite needed for BTC (Binance)
    service = EnhancedTradingService(kite=None)
    
    try:
        logger.info("\n[INFO] Starting BTC trading service...")
        logger.info("[INFO] Press Ctrl+C to stop gracefully\n")
        await service.start()
    except KeyboardInterrupt:
        logger.info("\n[INFO] Shutting down gracefully...")
        await service.stop()
    except Exception as e:
        logger.error(f"[ERROR] Service error: {e}", exc_info=True)
        await service.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        sys.exit(0)

