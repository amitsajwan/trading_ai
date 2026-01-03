"""Start the rule-based execution engine."""

import asyncio
import logging
import json
import sys
from pathlib import Path
from kiteconnect import KiteConnect
from services.rule_execution_service import RuleExecutionService
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)


def load_kite_credentials() -> dict:
    """Load Kite credentials from credentials.json."""
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        raise FileNotFoundError("credentials.json not found. Run auto_login.py first.")
    
    with open(cred_path) as f:
        return json.load(f)


async def main():
    """Main entry point."""
    logger.info("=" * 70)
    logger.info("Rule-Based Execution Engine")
    logger.info("=" * 70)
    logger.info("Mode: Fast rule-based execution (<50ms per tick)")
    logger.info("Strategy Planner: Generates rules every 5 minutes")
    logger.info("Rule Engine: Evaluates rules on every tick")
    logger.info("=" * 70)
    
    kite = None
    
    # Load Zerodha credentials if needed
    if settings.data_source.upper() != "CRYPTO":
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
            logger.error("=" * 70)
            logger.error("ERROR: credentials.json not found!")
            logger.error("Please run: python auto_login.py")
            logger.error("=" * 70)
            return
        except Exception as e:
            logger.error(f"ERROR: Could not initialize Zerodha Kite: {e}")
            return
    
    # Create and start rule execution service
    service = RuleExecutionService(kite=kite)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        await service.stop()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await service.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)

