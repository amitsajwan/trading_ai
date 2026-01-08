#!/usr/bin/env python3
import asyncio
import sys
import os

# Add paths
sys.path.insert(0, './market_data/src')

async def main():
    from market_data.api import build_store, build_historical_replay
    store = build_store()
    replay = build_historical_replay(store, data_source='synthetic')
    replay.start()
    print('Historical replay started')
    # Keep running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())