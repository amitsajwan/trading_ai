#!/usr/bin/env python3
"""Standalone historical replay runner for use by market_data.runner.

This module runs historical replay in a separate process, similar to the old start_historical.py.
It's called by market_data.runner when --mode historical is used.
"""
import asyncio
import sys
import os
import argparse

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from market_data.api import build_store, build_historical_replay
import redis


async def monitor_for_ticks(redis_client, timeout=60, interval=1):
    """Poll Redis for tick keys and set a readiness key when data appears."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            keys = redis_client.keys('tick:*:latest')
            if keys:
                # Mark data ready and exit
                redis_client.set('system:historical:data_ready', '1')
                return True
        except Exception:
            pass
        await asyncio.sleep(interval)
    return False


async def main(args):
    # Determine parameters (CLI > ENV > defaults)
    hist_source = args.historical_source or os.getenv('HISTORICAL_SOURCE') or 'synthetic'
    hist_speed = float(args.historical_speed or os.getenv('HISTORICAL_SPEED') or 1.0)
    hist_from = args.historical_from or os.getenv('HISTORICAL_FROM')
    hist_ticks = args.historical_ticks or (os.getenv('HISTORICAL_TICKS', '0') in ('1', 'true', 'yes'))

    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

    store = build_store(redis_client=redis_client)

    print(f"Starting historical replay (source={hist_source}, speed={hist_speed}, from={hist_from}, ticks={hist_ticks})")

    # Parse start_date from string to datetime if provided
    start_date_obj = None
    if hist_from:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(hist_from, '%Y-%m-%d')
            print(f"   [*] Starting from date: {hist_from}")
        except Exception:
            print(f"   [WARNING] Invalid date format '{hist_from}'. Expected YYYY-MM-DD. Using default.")
            start_date_obj = None

    # Get KiteConnect instance for Zerodha historical data
    kite_instance = None
    if hist_source == 'zerodha':
        try:
            from kiteconnect import KiteConnect
            from market_data.tools.kite_auth_service import KiteAuthService
            
            # Load credentials
            auth_service = KiteAuthService()
            creds = auth_service.load_credentials()
            
            if creds:
                api_key = creds.get('api_key') or creds.get('KITE_API_KEY') or os.getenv('KITE_API_KEY')
                access_token = creds.get('access_token') or creds.get('data', {}).get('access_token') or os.getenv('KITE_ACCESS_TOKEN')
                
                if api_key and access_token:
                    kite_instance = KiteConnect(api_key=api_key)
                    kite_instance.set_access_token(access_token)
                    print("   [OK] KiteConnect instance created for historical data")
                else:
                    print("   [WARNING] Missing API key or access token for Zerodha historical data")
            else:
                print("   [WARNING] No credentials found for Zerodha historical data")
        except ImportError:
            print("   [WARNING] KiteConnect not available - cannot fetch Zerodha historical data")
        except Exception as e:
            print(f"   [WARNING] Failed to create KiteConnect instance: {e}")

    # Use build_historical_replay for 'zerodha' or CSV file
    replay = None
    if hist_source == 'zerodha':
        if kite_instance:
            replay = build_historical_replay(store, data_source='zerodha', start_date=start_date_obj, kite=kite_instance)
        else:
            print("   [ERROR] Cannot use Zerodha source without KiteConnect instance")
            print("   [INFO] Provide credentials or use CSV file instead")
            return  # Exit early if no kite instance
    elif hist_source and hist_source.endswith('.csv'):
        # Use HistoricalTickReplayer directly for CSV
        from market_data.adapters.historical_tick_replayer import HistoricalTickReplayer
        replay = HistoricalTickReplayer(store=store, data_source=hist_source, rebase=False, speed=0.0, instrument_symbol='BANKNIFTY')  # Use BANKNIFTY for futures
    else:
        print("   [ERROR] Unknown or unsupported data source")
        print("   [INFO] Supported sources: 'zerodha' or path to CSV file")
        return  # Exit early if unsupported source

    if not replay:
        print("   [ERROR] Failed to create replay instance")
        return

    # Start the replay
    replay.start()
    print('Historical replay started')

    # Signal that the historical runner is running (supervisor may poll this)
    try:
        redis_client.set('system:historical:running', '1')
    except Exception:
        pass

    # Start background monitoring task that detects when ticks appear in Redis
    monitor_task = asyncio.create_task(monitor_for_ticks(redis_client))

    try:
        while True:
            # If monitor_task completed and found data ready, we just continue running
            if monitor_task.done():
                # keep running; supervisor can detect readiness via Redis key
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)
    finally:
        try:
            replay.stop()
        except Exception:
            pass
        # Clean up readiness keys
        try:
            redis_client.delete('system:historical:running')
            redis_client.delete('system:historical:data_ready')
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--historical-source', type=str, help='zerodha or path/to/file.csv')
    parser.add_argument('--historical-speed', type=float, help='Playback speed multiplier')
    parser.add_argument('--historical-from', type=str, help='YYYY-MM-DD')
    parser.add_argument('--historical-ticks', action='store_true', help='Use tick-level replay')
    args = parser.parse_args()
    asyncio.run(main(args))
