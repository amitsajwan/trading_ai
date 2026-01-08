#!/usr/bin/env python3
"""Inspect configured news collector and try a short collection."""
import sys
from pathlib import Path
import asyncio

# Ensure src is on path when running from repo root
repo_root = Path(__file__).resolve().parents[1]
src_path = str(repo_root / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from news_module.api_service import get_news_service


def print_collector_info(svc):
    collector = getattr(svc, 'collector', None)
    print("Collector class:", type(collector).__name__ if collector else None)
    print("Collector module:", collector.__class__.__module__ if collector else None)


async def main():
    try:
        svc = get_news_service()
        print_collector_info(svc)
        # Initialize collector
        await svc.__aenter__()
        # Try collect for NIFTY
        print("Collecting 3 items for NIFTY...")
        items = await svc.collector.collect_news_for_instrument('NIFTY', limit=3)
        print(f"Collected {len(items)} items")
        for it in items:
            print('-', repr(it.title)[:200], '| source:', it.source, '| published:', getattr(it, 'published_at', None))
    except Exception as e:
        print("Error during inspection:", e)
    finally:
        try:
            if svc:
                await svc.__aexit__(None, None, None)
        except Exception:
            pass

if __name__ == '__main__':
    asyncio.run(main())
