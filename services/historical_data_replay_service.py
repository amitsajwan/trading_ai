"""Standalone historical data replay service for Docker.

This runs the actual historical replay logic from market_data module
to fetch real data from Zerodha API and load it into Redis.

⚡ IMPORTANT: Historical data loading is INSTANT (matches Zerodha API reality)
- historical_data() API returns all candles at once (REST, not streaming)
- All data loads instantly into Redis at startup
- Speed parameter is legacy/testing only, should always be 0.0

Configuration is provided via environment variables:

- HISTORICAL_DATE: YYYY-MM-DD (primary, from docker-compose.historical.yml)
- HISTORICAL_START_DATE: YYYY-MM-DD (fallback for backward compatibility)
- HISTORICAL_INTERVAL: candle interval (default: "minute")
- HISTORICAL_SPEED: Should always be 0.0 (instant load, matches reality)

For full Zerodha historical data, ensure Kite authentication is
completed and credentials are available in the container.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add market_data to path
sys.path.insert(0, '/app/market_data/src')

try:
    import redis
    from market_data.api import build_store
    from market_data.adapters.historical_tick_replayer import HistoricalTickReplayer
    from kiteconnect import KiteConnect
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)


def _parse_date(value: str | None) -> datetime | None:
    """Parse date string to datetime object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"Invalid date format: {value}. Expected YYYY-MM-DD")
        return None


def _load_kite_credentials() -> tuple[str | None, str | None]:
    """Load Kite API credentials from credentials.json."""
    try:
        cred_path = Path("/app/credentials.json")
        if not cred_path.exists():
            logger.warning("credentials.json not found")
            return None, None
        
        with open(cred_path, 'r', encoding='utf-8-sig') as f:
            creds = json.load(f)
        
        api_key = creds.get('api_key') or creds.get('KITE_API_KEY') or os.getenv('KITE_API_KEY')
        access_token = creds.get('access_token') or creds.get('data', {}).get('access_token') or os.getenv('KITE_ACCESS_TOKEN')
        
        return api_key, access_token
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        return None, None


def _normalize_timeframe(interval: str) -> str:
    """Normalize interval to storage timeframe (e.g., "minute" -> "1min")."""
    tf = (interval or "").lower()
    if tf == "minute":
        return "1min"
    if tf.endswith("minute"):
        minutes = tf.replace("minute", "").strip() or "1"
        return f"{minutes}min"
    return tf or "1min"


def _clear_existing_ohlc(redis_client: "redis.Redis", instrument: str, interval: str) -> None:
    """Remove existing OHLC data for the instrument/timeframe before replay.

    Without cleanup, repeated replays append duplicate entries to the sorted set,
    and ascending range queries (used by the dashboard/status cards) stop early
    on the first-day data. Clearing ensures a fresh dataset per run.
    """

    try:
        timeframe = _normalize_timeframe(interval)
        sorted_key = f"ohlc_sorted:{instrument}:{timeframe}"
        pattern = f"ohlc:{instrument}:{timeframe}:*"

        # Drop sorted set
        try:
            removed = redis_client.delete(sorted_key)
            if removed:
                logger.info(f"Cleared existing sorted set: {sorted_key} ({removed} keys)")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not clear sorted set {sorted_key}: {e}")

        # Drop legacy per-bar keys
        try:
            keys = list(redis_client.scan_iter(match=pattern))
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} legacy OHLC keys for {instrument}:{timeframe}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not clear legacy OHLC keys ({pattern}): {e}")

    except Exception as e:  # noqa: BLE001
        logger.warning(f"OHLC cleanup skipped due to error: {e}")


async def main() -> None:
    """Main historical replay service."""
    logger.info("Starting Historical Replay Service")
    
    # Get configuration from environment
    # HISTORICAL_DATE is primary (from docker-compose.historical.yml)
    # HISTORICAL_START_DATE is fallback for backward compatibility
    date_str = os.getenv("HISTORICAL_DATE") or os.getenv("HISTORICAL_START_DATE")
    source = os.getenv("HISTORICAL_SOURCE", "zerodha")
    speed = float(os.getenv("HISTORICAL_SPEED", "1.0"))
    interval = os.getenv("HISTORICAL_INTERVAL", "minute")
    
    if not date_str:
        logger.error("HISTORICAL_DATE or HISTORICAL_START_DATE environment variable required")
        sys.exit(1)
    
    start_date = _parse_date(date_str)
    if not start_date:
        logger.error(f"Invalid date: {date_str}")
        sys.exit(1)
    
    logger.info(f"Configuration: date={date_str}, source={source}, speed={speed}, interval={interval}")
    
    # Initialize Redis connection
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
    
    try:
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        sys.exit(1)
    
    # Build market store
    store = build_store(redis_client=redis_client)
    
    # Initialize KiteConnect for Zerodha historical data
    kite_instance = None
    if source == "zerodha":
        api_key, access_token = _load_kite_credentials()
        if api_key and access_token:
            try:
                kite_instance = KiteConnect(api_key=api_key)
                kite_instance.set_access_token(access_token)
                logger.info("✅ KiteConnect instance created")
            except Exception as e:
                logger.error(f"❌ Failed to create KiteConnect: {e}")
                sys.exit(1)
        else:
            logger.error("❌ Kite credentials not available")
            sys.exit(1)
    
    # Get instrument symbol from config
    instrument_symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26JANFUT")
    logger.info(f"Using instrument: {instrument_symbol}")

    # Clear any previous replay data to avoid duplicate sorted-set entries
    _clear_existing_ohlc(redis_client, instrument_symbol, interval)
    
    # Create historical tick replayer
    try:
        replayer = HistoricalTickReplayer(
            store=store,
            data_source=source,
            speed=speed,
            kite=kite_instance,
            instrument_symbol=instrument_symbol,
            from_date=start_date.date(),
            to_date=start_date.date(),  # Same day for now
            interval=interval,
            rebase=False
        )
        logger.info("✅ Historical replayer created")
    except Exception as e:
        logger.error(f"❌ Failed to create replayer: {e}")
        sys.exit(1)
    
    # Start the replay
    try:
        replayer.start()
        logger.info(f"✅ Historical replay started for {date_str}")
        
        # Mark service as running in Redis
        redis_client.set('system:historical:running', '1')
        
        # Keep service alive and monitor
        while True:
            await asyncio.sleep(10)
            
            # Check if replay is still running
            if hasattr(replayer, 'running') and not replayer.running:
                logger.warning("Replay stopped, restarting...")
                replayer.start()
                
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error during replay: {e}")
        raise
    finally:
        try:
            replayer.stop()
            redis_client.delete('system:historical:running')
            logger.info("Historical replay service stopped")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    asyncio.run(main())

