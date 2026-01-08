#!/usr/bin/env python3
"""
Start market_data API server with historical replay.
Exposes all market data APIs for the UI shell integration.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, date, timedelta

# Add paths
sys.path.insert(0, './market_data/src')

from market_data.api import build_store
from market_data.providers.zerodha import ZerodhaProvider
from market_data.adapters.historical_tick_replayer import HistoricalTickReplayer, IST
from kiteconnect import KiteConnect
import json
from datetime import date, timedelta
from market_data.contracts import OHLCBar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start_market_data_server():
    """Start market data API server with historical replay."""
    print("Starting Market Data API Server with Zerodha Historical Data...")
    print("=" * 60)

    # Load Zerodha credentials using ZerodhaProvider
    zerodha_provider = ZerodhaProvider.from_credentials_file("credentials.json")
    kite = None

    # Setup Zerodha provider and Redis store
    zerodha_provider = ZerodhaProvider.from_credentials_file("credentials.json")
    kite = None

    if zerodha_provider:
        try:
            profile = zerodha_provider.profile()
            kite = zerodha_provider.kite
            print(f"Zerodha credentials verified for user: {profile.get('user_id')}")
        except Exception as e:
            print(f"Zerodha credentials invalid: {e}")
            zerodha_provider = None

    # Setup Redis-backed store
    from market_data.api_service import get_redis_client
    redis_client = get_redis_client()
    store = build_store(redis_client=redis_client)

    # Configure API services
    import market_data.api_service
    market_data.api_service.get_store = lambda: store
    market_data.api_service._store = store

    # Initialize technical indicators service with pandas-ta
    from market_data.technical_indicators_service import TechnicalIndicatorsService
    market_data.api_service._technical_service = TechnicalIndicatorsService(redis_client=redis_client)

    print("Market data services configured with Redis storage and pandas-ta indicators")

    # Start historical replay with real Zerodha data if available
    if zerodha_provider and kite:
        # Use real Zerodha historical data for the last 7 days
        to_date = date.today()
        from_date = to_date - timedelta(days=7)

        replay = HistoricalTickReplayer(
            store=store,
            data_source="zerodha",
            speed=0.0,  # Instant replay
            kite=kite,
            instrument_symbol="BANKNIFTY",
            from_date=from_date,
            to_date=to_date,
            interval="minute",
            rebase=True,
            rebase_to=datetime.now()
        )
        print(f"Using real Zerodha historical data ({from_date} to {to_date})")
    else:
        # Fallback to synthetic data
        from market_data.api import build_historical_replay
        start_date = datetime(2026, 1, 7, 9, 15, 0)
        replay = build_historical_replay(store, data_source="synthetic", start_date=start_date)
        replay.speed_multiplier = 1.0
        replay.rebase = True
        from datetime import timezone
        replay.rebase_to = datetime.now(timezone.utc)
        print(f"Using synthetic data from {start_date}")

    # Start API server first
    print("Starting API server...")

    # Skip data loading for now - start server first
    print("Starting server without data loading for debugging...")

    print("\nAvailable Market Data APIs:")
    print("   GET /health - Health check")
    print("   GET /api/v1/market/tick/{instrument} - Latest market tick")
    print("   GET /api/v1/market/ohlc/{instrument} - OHLC bars")
    print("   GET /api/v1/market/price/{instrument} - Current price data")
    print("   GET /api/v1/market/raw/{instrument} - Raw market data")
    print("   GET /api/v1/market/raw - Default raw market data")
    print("   GET /api/v1/market/depth/{instrument} - Market depth")
    print("   GET /api/v1/market/depth - Default market depth")
    print("   GET /api/v1/options/chain/{instrument} - Options chain")
    print("   GET /api/v1/technical/indicators/{instrument} - Technical indicators")
    print("\nServer starting on http://127.0.0.1:8006")
    print("Press Ctrl+C to stop\n")

    try:
        # Import and start API server
        from market_data.api_service import app

        # Start the server
        import uvicorn
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8006,
            log_level="info",
            reload=False
        )
        server = uvicorn.Server(config)
        await server.serve()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\nError starting server: {e}")
    finally:
        replay.stop()
        print("Historical replay stopped")
        print("Server shutdown complete")

if __name__ == "__main__":
    asyncio.run(start_market_data_server())